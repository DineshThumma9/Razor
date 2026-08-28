from agent.nodes import audit, classify, decide, diagonse, execute, is_resolved
from agent.tools import tools
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from models import RecoveryState


def build_agent(state: RecoveryState):
    checkpointer = InMemorySaver()
    system_prompt = f"""
    You are a revenue recovery agent. Here is the current case:

    Customer: {state.customer['name']} ({state.customer['email']})
    Amount owed: ₹{state.amount_inr}
    Case type: {state.case_type}
    Failure reason: {state.failure_reason}
    Attempts made: {state.attempt_count}
    Last action: {state.last_action_taken}
    Preferred contact: {state.contact_preference}
    Audit log: {state.audit_log}

    Decide the next recovery action.
    """

    return create_agent(
        tools=tools,
        model="mistral:ministral-14b",
        checkpointer=checkpointer,
        system_prompt=system_prompt,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "escalate_to_human": {
                        "allowed_decisions": ["approve", "reject", "edit"]
                    }
                }
            )
        ],
    )


def start_graph():

    graph = StateGraph(RecoveryState)

    graph.add_node(START)
    graph.add_node(classify)
    graph.add_node(decide)
    graph.add_node(diagonse)
    graph.add_edge(execute)
    graph.add_node(audit)
    graph.add_node(is_resolved)
    graph.add_edge(START, classify)
    graph.add_edge(classify, decide)
    graph.add_edge(decide, diagonse)
    graph.add_edge(diagonse, execute)
    graph.add_edge(execute, audit)
    graph.add_edge(audit, is_resolved)
    graph.add_edge(is_resolved, END)

    return graph.compile()
