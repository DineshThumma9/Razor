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


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    recovery_state: RecoveryState
    event_source: str


def analyze(state: AgentState):
    """
    Analyzes the current RecoveryState and formats the system prompt.
    """
    rs = state["recovery_state"]
    
    system_prompt = f"""You are a revenue recovery agent for Renvue, an Indian SaaS platform.

Your job is to decide the best recovery action for a failed payment case.

=== CURRENT CASE ===
Customer     : {rs.customer.get('name', 'Unknown')} ({rs.customer.get('email', '')})
Contact      : {rs.customer.get('contact', '')}
Amount owed  : ₹{rs.amount_inr}
Case type    : {rs.case_type}
Decline type : {rs.decline_type or 'N/A'}
Failure      : {rs.failure_reason or 'Unknown'}
Attempts     : {rs.attempt_count}
Last action  : {rs.last_action_taken or 'None'}
Audit log    : {rs.audit_log if rs.audit_log else 'Empty'}

=== DECISION RULES ===
- If the customer replies via email or WhatsApp and specifies a date they will pay, use 'log_promise_to_pay' AND 'send_whatsapp_msg'.

- If Case type is 'failed_payment' or 'failed_subscription':
    → If Failure contains "Insufficient funds" or "limit": 
         Call BOTH 'get_next_salary_date' AND 'send_whatsapp_msg' in your first response.
    → Otherwise (Hard decline): 
         If Amount > 5000: Call BOTH 'create_payment_link' AND 'get_voice_call' in your first response.
         If Amount <= 5000: Call BOTH 'create_payment_link' AND 'send_whatsapp_msg' in your first response.
         DO NOT use send_email_reminder for failed payments!

- If Case type is 'abandoned_checkout':
    → Use 'send_whatsapp_msg' immediately with a discount or gentle nudge.

- If Case type is 'overdue_invoice' (B2B):
    → Use 'send_email_reminder' with urgency='urgent'.

- If attempt_count >= 3 or Case type is 'dispute':
    → Use 'escalate_to_human' immediately.

CRITICAL INSTRUCTION: You MUST take action on EVERY new case. 
Rule 1: For failed_payment > 5000, you MUST call BOTH `create_payment_link` AND `get_voice_call` simultaneously.
Rule 2: NEVER call `send_email_reminder` for failed_payment.
Rule 3: Only call `complete_case` AFTER you have successfully executed the required action tools. Do NOT call `complete_case` as your first action."""

    return {"messages": [SystemMessage(content=system_prompt)]}


def decide_event(state: AgentState):
    """
    Phase 1: Deterministic fast-path for standard automated cases.
    """
    rs = state["recovery_state"]
    tools_to_call = []
    
    if rs.attempt_count >= 3 or rs.case_type == 'dispute':
        tools_to_call.append({"name": "escalate_to_human", "args": {}})
        
    elif rs.case_type in ['failed_payment', 'failed_subscription']:
        fail_reason = rs.failure_reason or ""
        if "Insufficient funds" in fail_reason or "limit" in fail_reason.lower():
            tools_to_call.append({"name": "get_next_salary_date", "args": {}})
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": "Gentle reminder about your payment."}})
        else:
            tools_to_call.append({"name": "create_payment_link", "args": {}})
            if rs.amount_inr > 5000:
                tools_to_call.append({"name": "get_voice_call", "args": {"msg": "Namaste, your payment failed. Please check the link we sent."}})
            else:
                tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": "Your payment failed, please click the link to retry."}})
                
    elif rs.case_type == 'abandoned_checkout':
        tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": "Complete your checkout with this 10% discount!"}})
        
    elif rs.case_type == 'overdue_invoice':
        tools_to_call.append({"name": "send_email_reminder", "args": {"urgency": "urgent"}})

    if tools_to_call:
        tools_to_call.append({"name": "complete_case", "args": {"summary": "Deterministic routing completed."}})
        
        from langchain_core.messages import AIMessage
        import uuid
        
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

    # Fallback if deterministic rules don't match an automated event (shouldn't happen)
    print(f"\n[ROUTER] Warning: No deterministic rules matched for automated event in case {rs.case_id}")
    return {"messages": []}


def decide_reply(state: AgentState):
    """
    Phase 2: LLM routing for conversational replies (WhatsApp, Email).
    """
    rs = state["recovery_state"]
    print(f"\n[ROUTER] LLM routing conversational reply for case: {rs.case_id}")
    
    # We provide a clean context to the LLM to avoid Mistral strict-ordering API errors
    # caused by synthetic deterministic logs in the history.
    system_prompt = f"""You are a revenue recovery agent for Renvue.
    
=== CURRENT CASE ===
Customer     : {rs.customer.get('name', 'Unknown')}
Amount owed  : ₹{rs.amount_inr}
Case type    : {rs.case_type}
Today's Date : {datetime.now().strftime('%Y-%m-%d')}

=== RULES ===
- If the customer specifies a date they will pay, use 'log_promise_to_pay'. Convert relative dates (like 'next monday') to YYYY-MM-DD using Today's Date.
- If the customer asks a question, use 'send_whatsapp_msg' to reply.
- ALWAYS call 'complete_case' after taking your action to end the workflow.
"""
    from langchain_core.messages import SystemMessage
    
    # We want to keep all messages starting from the FIRST HumanMessage.
    # This strips away the old deterministic automated logs, but crucially preserves 
    # the LLM's recent tool calls and responses so it doesn't get stuck in an infinite loop!
    first_human_idx = next((i for i, m in enumerate(state["messages"]) if getattr(m, "type", "") == "human"), None)
    
    if first_human_idx is not None:
        recent_messages = state["messages"][first_human_idx:]
    else:
        recent_messages = []
        
    clean_messages = [SystemMessage(content=system_prompt)] + recent_messages
    
    llm = ChatMistralAI(model=settings.model, temperature=0, max_retries=3)
    llm_with_tools = llm.bind_tools(tools, tool_choice="any")
    
    import time
    import random
    
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


# The execute node is simply a ToolNode wrapper that will run the tools requested by the LLM
execute = ToolNode(tools)


def audit(state: AgentState):
    """
    Saves the final outcome to the SQLite database.
    This is deterministic and happens unconditionally after tools are executed.
    """
    rs = state["recovery_state"]
    messages = state["messages"]
    
    # Find the most recent AI message that called tools
    last_ai_msg = next((m for m in reversed(messages) if m.type == "ai" and getattr(m, "tool_calls", None)), None)
    
    if last_ai_msg and last_ai_msg.tool_calls:
        # We assume the primary action was the last tool called (or the only tool called)
        last_tool = last_ai_msg.tool_calls[-1]
        action = last_tool["name"]
        
        # Determine next retry based on action type
        next_contact = None
        if action == "send_email_reminder":
            next_contact = datetime.now() + timedelta(days=7) # Default 7 days if email
        elif action == "escalate_to_human":
            next_contact = None # Done
            rs.recovery_status = "escalated"
        
        entry = AuditEntry(
            event_triggered=action,
            amount=str(rs.amount_inr),
            recovery_status=rs.recovery_status,
            customer=rs.customer,
            next_contact=next_contact
        )
        rs.audit_log.append(entry.model_dump())
        rs.last_action_taken = action
        rs.attempt_count += 1
        if next_contact:
            rs.next_retry_at = next_contact
            
    # Persist the state using our db.py
    save_state(rs)
    
    # We return the mutated recovery_state
    return {"recovery_state": rs}


def should_continue(state: AgentState):
    """
    Decides whether to execute tools or go to the audit phase.
    """
    last_message = state["messages"][-1]
    
    if getattr(last_message, "tool_calls", None):
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
