from config import settings
from typing import Annotated, Sequence, TypedDict
import operator
from datetime import datetime, timedelta

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.prebuilt import ToolNode
from langchain_mistralai import ChatMistralAI
from core.models import RecoveryState, AuditEntry
from db import save_state
from agent.tools import tools
from langchain_core.messages import AIMessage
import uuid
from langchain_core.messages import SystemMessage
import time
import random
    


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    recovery_state: RecoveryState
    event_source: str




def customer_stats():
    pass 




def decide_event(state: AgentState):
    """
    Phase 1: Deterministic fast-path for standard automated cases.
    """
    rs = state["recovery_state"]
    tools_to_call = []
    
    if rs.attempt_count >= 3:
        tools_to_call.append({"name": "escalate_to_human", "args": {"reason": f"Max attempts ({rs.attempt_count}) reached"}})
        #Add context of this person what we have done till now case details and summary so its easy for humans to go through case and respond
    elif rs.case_type == 'dispute':
        tools_to_call.append({"name": "escalate_to_human", "args": {"reason": "Customer raised a dispute"}})
        
    elif rs.case_type in ['failed_payment', 'failed_subscription']:
        if rs.decline_type == "soft":
            tools_to_call.append({"name": "get_next_salary_date", "args": {}})
            #Personalize message on basis of their name,amount they should pay 
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": "Gentle reminder about your payment."}})
        else:
            tools_to_call.append({"name": "create_payment_link", "args": {}})
            if rs.amount_inr > 5000:
                #Personalize message on basis on name and amount and also language they use 
                tools_to_call.append({"name": "get_voice_call", "args": {"msg": "Namaste, your payment failed. Please check the link we sent."}})
            else:
                #Personalize message on basis of their name,amount they should pay 
                tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": "Your payment failed, please click the link to retry."}})
                
    elif rs.case_type == 'abandoned_checkout':
        #Personalize message on basis of their name,amount they should pay and also offer discount between min and max discount
        tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": "Complete your checkout with this 10% discount!"}})
    elif rs.case_type == 'overdue_invoice':
        #Personalize message on basis of their name,amount they should pay   
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


def decide_reply(state: AgentState):
    """
    Phase 2: LLM routing for conversational replies (WhatsApp, Email).
    """
    rs = state["recovery_state"]
    print(f"\n[ROUTER] LLM routing conversational reply for case: {rs.case_id}")
    
    system_prompt = f"""You are a revenue recovery agent for Renvue.
    
=== CURRENT CASE ===
Customer     : {rs.customer.get('name', 'Unknown')}
Amount owed  : ₹{rs.amount_inr}
Case type    : {rs.case_type}
Attempt Count: {rs.attempt_count}
Today's Date : {datetime.now().strftime('%Y-%m-%d')}

=== RULES ===
- If Attempt Count >= 3, you MUST call 'escalate_to_human' with a reason and stop. Do not schedule further follow-ups.
- Check user sentiment with log_promise_to_pay and if sentiment is postive and willing to pay at a certain date then 
-       Convert relative dates (like 'next monday') to YYYY-MM-DD using Today's Date.
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
    
    
    time.sleep(random.uniform(0.5, 3.0))
    
    for attempt in range(6):
        try:
            response = llm_with_tools.invoke(clean_messages)
            return {"messages": [response]}
        except Exception as e:
            if "429" in str(e) or "rate_limited" in str(e):
                backoff = random.uniform(3.0, 8.0) * (attempt + 1)
                print(f"[RATE LIMIT] Mistral 429 hit. Retrying in {backoff:.1f}s (Attempt {attempt+1}/6)...")
                time.sleep(backoff)
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


def audit(state: AgentState):
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
            
    save_state(rs)
    
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
