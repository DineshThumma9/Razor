import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv

from core.models import RecoveryState
from agent.nodes import AgentState, analyze, decide, execute, audit, should_continue

load_dotenv()

# Global checkpointer for persistence across script invocations
conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)

def build_agent(state: RecoveryState):
    """
    Builds the custom StateGraph for revenue recovery.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze", analyze)
    workflow.add_node("decide", decide)
    workflow.add_node("execute", execute)
    workflow.add_node("audit", audit)

    # Wire edges
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "decide")
    
    # Conditional edge from decide
    workflow.add_conditional_edges(
        "decide",
        should_continue,
        {
            "execute": "execute",
            "audit": "audit"
        }
    )
    
    from agent.nodes import after_execute
    # After executing tools, check if we should loop back or go to audit
    workflow.add_conditional_edges(
        "execute", 
        after_execute,
        {
            "decide": "decide",
            "audit": "audit"
        }
    )
    # Audit is the final step
    workflow.add_edge("audit", END)

    # Compile the graph
    app = workflow.compile(checkpointer=checkpointer)
    
    return app
