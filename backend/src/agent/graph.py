import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv

from core.models import RecoveryState
from agent.nodes import AgentState, analyze, decide_event, decide_reply, execute, audit, should_continue, after_execute

load_dotenv()

# Global checkpointer for persistence across script invocations
conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)

def route_entry(state: AgentState):
    if state.get("event_source", "").startswith("inbound."):
        return "decide_reply"
    else:
        # We go to analyze first for automated events to get the system prompt
        return "analyze"

def build_agent(state: RecoveryState):
    """
    Builds the custom StateGraph for revenue recovery.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze", analyze)
    workflow.add_node("decide_event", decide_event)
    workflow.add_node("decide_reply", decide_reply)
    workflow.add_node("execute", execute)
    workflow.add_node("audit", audit)

    # Conditional entry routing
    workflow.add_conditional_edges(
        START,
        route_entry,
        {
            "analyze": "analyze",
            "decide_reply": "decide_reply"
        }
    )
    
    # Analyze always goes to decide_event
    workflow.add_edge("analyze", "decide_event")
    
    # Conditional edge from decide_event
    workflow.add_conditional_edges(
        "decide_event",
        should_continue,
        {
            "execute": "execute",
            "audit": "audit"
        }
    )
    
    # Conditional edge from decide_reply
    workflow.add_conditional_edges(
        "decide_reply",
        should_continue,
        {
            "execute": "execute",
            "audit": "audit"
        }
    )
    
    # After executing tools, check if we should loop back or go to audit
    workflow.add_conditional_edges(
        "execute", 
        after_execute,
        {
            "decide_event": "decide_event",
            "decide_reply": "decide_reply",
            "audit": "audit"
        }
    )
    
    # Audit is the final step
    workflow.add_edge("audit", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    
    return app
