import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv

from core.models import RecoveryState
from agent.nodes import AgentState, decide_event, decide_reply, execute, audit, should_continue, escalate_gate, after_execute

load_dotenv()

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)

def route_entry(state: AgentState):
    event = state.get("event_source", "")
    if event.startswith("inbound.") or event.startswith("scheduled."):
        return "decide_reply"
    else:
        return "decide_event"

def build_agent(state: RecoveryState):
    """
    Builds the custom StateGraph for revenue recovery.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("decide_event", decide_event)
    workflow.add_node("decide_reply", decide_reply)
    workflow.add_node("escalate_gate", escalate_gate)
    workflow.add_node("execute", execute)
    workflow.add_node("audit", audit)

    workflow.add_conditional_edges(
        START,
        route_entry,
        {
            "decide_event": "decide_event",
            "decide_reply": "decide_reply"
        }
    )
    
    workflow.add_conditional_edges(
        "decide_event",
        should_continue,
        {
            "execute": "execute",
            "escalate_gate": "escalate_gate",
            "audit": "audit"
        }
    )
    
    workflow.add_conditional_edges(
        "decide_reply",
        should_continue,
        {
            "execute": "execute",
            "escalate_gate": "escalate_gate",
            "audit": "audit"
        }
    )
    
    workflow.add_edge("escalate_gate", "execute")
    
    workflow.add_conditional_edges(
        "execute", 
        after_execute,
        {
            "decide_event": "decide_event",
            "decide_reply": "decide_reply",
            "audit": "audit"
        }
    )
    
    workflow.add_edge("audit", END)

    # Compile the graph
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["escalate_gate"]
    )
    
    return app
