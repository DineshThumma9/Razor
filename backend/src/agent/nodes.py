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
- HARD decline (card expired, card lost, stolen, do not honour, invalid CVV):
    → create_payment_link so customer can re-enter card details

- SOFT decline (insufficient funds, limit exceeded):
    → get_next_salary_date to find the best retry date
    → send_email_reminder with urgency='gentle' (for 1st attempt) or 'urgent' (for 2nd)

- If attempt_count >= 3: escalate_to_human immediately

- If case_type is 'dispute': escalate_to_human immediately

- Abandoned checkout: send_email_reminder with urgency='gentle'

- Overdue invoice: send_email_reminder with urgency='urgent'

If you need to take action, select and execute exactly ONE tool. 
If you have already executed all necessary tools for this case based on the rules, call the 'complete_case' tool to finish. Do NOT call audit tools."""

    return {"messages": [SystemMessage(content=system_prompt)]}


def decide(state: AgentState):
    """
    Calls the LLM to decide on the next tool to execute.
    """
    llm = ChatMistralAI(model="ministral-14b-2512", temperature=0)
    llm_with_tools = llm.bind_tools(tools, tool_choice="any")
    
    import time
    time.sleep(2) # Prevent Mistral API rate limit
    
    # We pass the conversation history to the LLM
    response = llm_with_tools.invoke(state["messages"])
    
    return {"messages": [response]}


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
    if last_message.name == "complete_case":
        return "audit"
    return "decide"
