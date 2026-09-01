import uuid
import random
import asyncio
import operator
from datetime import datetime
from typing import Annotated, Sequence, TypedDict
import json
import logging
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
from langgraph.prebuilt import ToolNode
from langchain_mistralai import ChatMistralAI
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from config.config import settings
from config.clients import redis_client
from config.constants import hard_declines
import config.db
from models.models import RecoveryState
from service.states import save_state
from agent.tools import tools


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    recovery_state: RecoveryState
    event_source: str


def get_discount():    
    #Personalize message on basis of their name,amount they should pay and also offer discount between min and max discount
    prob = random.random()
    discounted = 0
    if prob <= 0.3:
        discounted = settings.max_discount 
    elif prob <= 0.7:
        discounted = random.randint(settings.min_discount, max(settings.min_discount, settings.max_discount-5))
    elif prob <= 1:
        discounted = settings.min_discount

    return discounted


def cant_resolve(rs: RecoveryState):
    details = rs.error_details or {}
    source = details.get("error_source")
    reason = details.get("error_reason")
    desc = details.get("error_description", "")
    
    unresolvable_reasons = ['fraud_suspected', 'card_lost_or_stolen', 'account_frozen', 'account_closed']
    
    if source == "internal":
        return True, "There is a temporary issue with our payment gateway. Please try again later."
    
    if reason in unresolvable_reasons:
        return True, "Your payment was blocked by your bank for security reasons. Please try a different payment method or contact your bank."
        
    if rs.method == "card" and desc in hard_declines.values():
        return True, f"Your card payment failed because: {desc}. Please try using a different payment method like UPI."
        
    return False, ""


async def decide_event(state: AgentState):
    """
    Phase 1: Deterministic fast-path for standard automated cases.
    """
    rs = state["recovery_state"]
    tools_to_call = []

    target_method = rs.method 
    through = rs.through

    if target_method and await redis_client.sismember("downtimes:method", target_method):
        if through and await redis_client.exists(f"downtimes:{target_method}:{through}"):
            ai_msg = AIMessage(content="User network is down we cant do much respond with empathic wait message if tried many times ")
            return {"messages": [ai_msg]}

    # Check if this error is fundamentally unrecoverable via automated retries
    is_unresolvable, empathetic_msg = cant_resolve(rs)
    if is_unresolvable:
        print(f"[ROUTER] Unresolvable error detected: {rs.error_details}")
        ai_msg = AIMessage(content="Unresolvable error.", tool_calls=[
            {"name": "send_whatsapp_msg", "args": {"msg": empathetic_msg}, "id": f"call_{uuid.uuid4().hex[:8]}", "type": "tool_call"},
            {"name": "complete_case", "args": {"summary": "Unresolvable error. Empathic message sent."}, "id": f"call_{uuid.uuid4().hex[:8]}", "type": "tool_call"}
        ])
        return {"messages": [ai_msg]}
        
    if rs.attempt_count >= 3:
        context_str = f"Context: Name={rs.customer.get('name', 'Unknown')}, Amount=₹{rs.amount_inr:,.0f}, Case={rs.case_type}, Last Action={rs.last_action_taken}"
        tools_to_call.append({"name": "escalate_to_human", "args": {"reason": f"Max attempts ({rs.attempt_count}) reached. {context_str}"}})
    elif rs.case_type == 'dispute':
        tools_to_call.append({"name": "escalate_to_human", "args": {"reason": "Customer raised a dispute"}})
        
    elif rs.case_type == 'subscription_cancelled':
        tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"Your auto-pay was cancelled, but your ₹{rs.amount_inr:,.0f} instalment is still due. Would you like to pay manually?"}})
        
    elif rs.case_type in ['failed_payment', 'failed_subscription']:
        if rs.amount_inr > 15000 and rs.case_type == "failed_subscription":
            # The Above ₹15,000 EMI Rule
            tools_to_call.append({"name": "create_payment_link", "args": {}})
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"Your auto-debit for ₹{rs.amount_inr:,.0f} failed. Under RBI rules, amounts over ₹15,000 require an OTP. Please click the link to authorize."}})
        elif rs.decline_type == "soft":
            tools_to_call.append({"name": "get_next_salary_date", "args": {}})
            customer_name = rs.customer.get('name', 'there')
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"Hi {customer_name}, just a gentle reminder regarding your pending payment of ₹{rs.amount_inr:,.0f}."}})
        else:
            tools_to_call.append({"name": "create_payment_link", "args": {}})
            if rs.amount_inr > 5000:
                customer_name = rs.customer.get('name', 'Customer')
                lang = getattr(rs, 'language', 'english')
                tools_to_call.append({"name": "get_voice_call", "args": {"msg": f"Namaste {customer_name}, your payment of ₹{rs.amount_inr:,.0f} failed. Please check the link we sent to retry in {lang}."}})
            else:
                customer_name = rs.customer.get('name', 'there')
                tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"Hi {customer_name}, your payment of ₹{rs.amount_inr:,.0f} failed. Please click the link to retry."}})
                
    elif rs.case_type == 'abandoned_checkout':
        tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"Complete your checkout with this ${get_discount()} discount!"}})
    elif rs.case_type == 'overdue_invoice':
        tools_to_call.append({"name": "send_email_reminder", "args": {"urgency": "urgent"}})

    if tools_to_call:
        tools_to_call.append({"name": "complete_case", "args": {"summary": "Deterministic routing completed."}})
        
        langchain_tool_calls = []
        for t in tools_to_call:
            langchain_tool_calls.append({
                "name": t["name"],
                "args": t["args"],
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "tool_call"
            })
            
        print(f"\n[ROUTER] Deterministic Fast-Path triggered for case: {rs.case_id}")
        ai_msg = AIMessage(content="Deterministic routing applied.", tool_calls=langchain_tool_calls)
        return {"messages": [ai_msg]}

    print(f"\n[ROUTER] Warning: No deterministic rules matched for automated event in case {rs.case_id}")
    return {"messages": []}


async def decide_reply(state: AgentState):
    """
    Phase 2: LLM routing for conversational replies (WhatsApp, Email).
    """
    rs = state["recovery_state"]
    print(f"\n[ROUTER] LLM routing conversational reply for case: {rs.case_id}")
    
    if rs.attempt_count >= 3:
        print(f"\n[ROUTER] Deterministic stop in decide_reply: attempt count {rs.attempt_count} >= 3")
        context_str = f"Context: Name={rs.customer.get('name', 'Unknown')}, Amount=₹{rs.amount_inr:,.0f}, Case={rs.case_type}, Last Action={rs.last_action_taken}"
        ai_msg = AIMessage(
            content="Max attempts reached.", 
            tool_calls=[{
                "name": "escalate_to_human", 
                "args": {"reason": f"Max attempts ({rs.attempt_count}) reached. {context_str}"},
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "tool_call"
            }]
        )
        return {"messages": [ai_msg]}
    
    system_prompt = f"""You are a revenue recovery agent for Renvue.
    
=== CURRENT CASE ===
Customer     : {rs.customer.get('name', 'Unknown')}
Amount owed  : ₹{rs.amount_inr}
Case type    : {rs.case_type}
Attempt Count: {rs.attempt_count}
Today's Date : {datetime.now().strftime('%Y-%m-%d')}
Max Discount : {settings.max_discount}%
Min Discount : {settings.min_discount}%

=== RULES ===
- If Attempt Count >= 3, you MUST call 'escalate_to_human' with a reason and stop. Do not schedule further follow-ups.
- Check user sentiment with log_promise_to_pay and if sentiment is postive and willing to pay at a certain date then 
-       Convert relative dates (like 'next monday') to YYYY-MM-DD using Today's Date.
- If it's an abandoned checkout, you can negotiate a discount between the Min Discount and Max Discount. Start low and only increase if they push back.
- Else reply them with some netural and generic message and escalare_to_human 
- If the customer asks a question, use 'send_whatsapp_msg' to reply.
- ALWAYS call 'complete_case' after taking your action to end the workflow.
"""
    
    first_human_idx = next((i for i, m in enumerate(state["messages"]) if getattr(m, "type", "") == "human"), None)
    
    if first_human_idx is not None:
        recent_messages = state["messages"][first_human_idx:]
    else:
        recent_messages = []
        
    clean_messages = [SystemMessage(content=system_prompt)] + recent_messages
    
    llm = ChatMistralAI(model=settings.model, temperature=0, max_retries=3)
    llm_with_tools = llm.bind_tools(tools, tool_choice="any")
    
    await asyncio.sleep(random.uniform(0.5, 3.0))
    
    for attempt in range(6):
        try:
            response = await llm_with_tools.ainvoke(clean_messages)
            return {"messages": [response]}
        except Exception as e:
            if "429" in str(e) or "rate_limited" in str(e):
                backoff = random.uniform(3.0, 8.0) * (attempt + 1)
                print(f"[RATE LIMIT] Mistral 429 hit. Retrying in {backoff:.1f}s (Attempt {attempt+1}/6)...")
                await asyncio.sleep(backoff)
            else:
                raise e
                
    raise Exception("Mistral API rate limit exceeded after maximum retries.")


execute = ToolNode(tools)

def escalate_gate(state: AgentState):
    """
    Dummy node that serves as a Human-in-the-Loop breakpoint.
    The graph will be configured to interrupt_before this node.
    """
    return state


async def audit(state: AgentState):
    """
    Saves the final outcome to the SQLite database.
    This is deterministic and happens unconditionally after tools are executed.
    """
    rs = state["recovery_state"]
    messages = state["messages"]
    
    last_ai_msg = next((m for m in reversed(messages) if m.type == "ai" and getattr(m, "tool_calls", None)), None)
    
    if last_ai_msg and last_ai_msg.tool_calls:
        rs.attempt_count += 1
        rs.last_action_taken = last_ai_msg.tool_calls[-1]["name"]
            
    async with config.db.AsyncSessionLocal() as db:
        await save_state(rs, db)
    
    return {"recovery_state": rs}


def should_continue(state: AgentState):
    """
    Decides whether to execute tools or go to the audit phase.
    """
    last_message = state["messages"][-1]
    
    if getattr(last_message, "tool_calls", None):
        if any(call["name"] == "escalate_to_human" for call in last_message.tool_calls):
            return "escalate_gate"
        return "execute"
        
    return "audit"

def after_execute(state: AgentState):
    """
    Decides where to go after executing tools. 
    If complete_case was just executed, we bypass the LLM and go straight to audit.
    """
    last_message = state["messages"][-1]
    if getattr(last_message, "name", None) == "complete_case":
        return "audit"
        
    if state.get("event_source", "").startswith("inbound."):
        return "decide_reply"
    return "decide_event"
