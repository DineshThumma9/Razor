import os
from langgraph.graph import StateGraph, START, END
from config.db import get_checkpointer
from models.models import RecoveryState
from agent.nodes import AgentState, decide_event, decide_reply, execute, audit, should_continue, escalate_gate, after_execute

def route_entry(state: AgentState):
    event = state.get("event_source", "")
    if event.startswith("inbound."):
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
        checkpointer=get_checkpointer()
    )
    
    if not os.path.exists("agent_workflow.png"):
        try:
            png = app.get_graph().draw_mermaid_png()
            with open("agent_workflow.png", "wb") as f:
                f.write(png)
        except Exception:
            pass
    
    return app
