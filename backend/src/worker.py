from celery import Celery
from celery.schedules import crontab
from db import load_state
from langchain_core.messages import HumanMessage



app = Celery('periodic_tasks', broker='redis://localhost:6379/0')

@app.task(name='worker.invoke_agent_task')
def invoke_agent_task(case_id: str):
    print(f"[CELERY] Waking up agent for case {case_id}...")
    state = load_state(case_id)
    if not state or state.recovery_status in ["recovered", "closed", "escalated"]:
        print(f"[CELERY] Case {case_id} is no longer active. Aborting.")
        return "Aborted: Case inactive."
        
    new_message = HumanMessage(content="Scheduled Follow-up Triggered. Please check the current state and decide the next action.")
    
    from agent.graph import build_agent
    agent = build_agent(state)
    config = {"configurable": {"thread_id": case_id}}
    
    agent.invoke(
        {"messages": [new_message], "recovery_state": state, "event_source": "scheduled.follow_up"}, 
        config=config
    )
    return f"Success: Agent invoked for case {case_id}."


