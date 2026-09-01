import uuid
import asyncio
from datetime import datetime
import redis.asyncio as redis
from taskiq_redis import ListQueueBroker
from service.states import load_state, save_state
from langchain_core.messages import HumanMessage
from config.clients import razorpay_client as client
from models.models import RecoveryState
import config.db as app_db
from sqlmodel import select
from agent.graph import build_agent

from config.config import settings
redis_url = settings.redis_url
broker = ListQueueBroker(
    redis_url,
    health_check_interval=15,
    retry_on_timeout=True,
    socket_timeout=10,
    socket_connect_timeout=10,
)

@broker.task(task_name='worker.invoke_agent_task')
async def invoke_agent_task(case_id: str):
    print(f"[TASKIQ] Waking up agent for case {case_id}...")
    
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        if not state or state.recovery_status in ["recovered", "closed", "escalated"]:
            print(f"[TASKIQ] Case {case_id} is no longer active. Aborting.")
            return "Aborted: Case inactive."
            
        new_message = HumanMessage(content="Scheduled Follow-up Triggered. Please check the current state and decide the next action.")
        
        agent = build_agent(state)
        config = {"configurable": {"thread_id": case_id}}
        
        # Now using asynchronous invocation!
        await agent.ainvoke(
            {"messages": [new_message], "recovery_state": state, "event_source": "scheduled.follow_up"}, 
            config=config
        )
    return f"Success: Agent invoked for case {case_id}."

async def revoke_active_task(task_id: str):
    """Cancel a pending Taskiq task by ID."""
    if task_id:
        print(f"[TASKIQ] Revoking task {task_id}")
        # Note: Taskiq doesn't natively have a global 'revoke' by ID without a state backend / Redis backend,
        # but you can ignore execution at runtime if state changed, or use a custom Redis revocation flag.
        # For now, we will mark it revoked in Redis so the task can short-circuit.
        r = redis.from_url(redis_url)
        await r.setex(f"revoked_task:{task_id}", 86400, "1")

@broker.task(task_name='worker.abandoned_cart_timer')
async def abandoned_cart_timer(order_id: str, customer_data: dict):
    print(f"[TASKIQ] Checking abandoned cart for order {order_id}...")
    
    try:
        # Client operations should be async. If razorpay client is sync, we should use asyncio.to_thread
        order = await asyncio.to_thread(client.order.fetch, order_id)
        if order.get("status") == "paid":
            print(f"[TASKIQ] Order {order_id} is already paid. Aborting abandoned cart flow.")
            return "Aborted: Order paid."
    except Exception as e:
        print(f"[TASKIQ] Error fetching order {order_id}: {e}")
        return
        
    async with app_db.AsyncSessionLocal() as db:
        # Check if a RecoveryState already exists for this order
        existing = (await db.execute(select(RecoveryState).where(RecoveryState.source_id == order_id))).scalars().first()
        if existing:
            print(f"[TASKIQ] RecoveryState already exists for order {order_id}. Aborting.")
            return "Aborted: RecoveryState exists."
            
        # Create an abandoned checkout case
        amount = float(order.get("amount", 0)) / 100.0
        rs = RecoveryState(
            case_id=str(uuid.uuid4()),
            source_id=order_id,
            case_type="abandoned_checkout",
            decline_type=None,
            failure_reason="Checkout abandoned after 15 minutes",
            error_details={},
            method=None,
            amount_inr=amount,
            recovered_amount=0.0,
            customer=customer_data,
            contact_preference="whatsapp",
            language="english",
            recovery_status="pending",
            attempt_count=0,
            last_action_taken=None,
            first_seen_at=datetime.now(),
            next_retry_at=None,
            audit_log=[]
        )
        await save_state(rs, db)
        
        agent = build_agent(rs)
        config = {"configurable": {"thread_id": rs.case_id}}
        await agent.ainvoke(
            {"messages": [], "recovery_state": rs, "event_source": "automated.abandoned_cart"}, 
            config=config
        )
    return f"Success: Abandoned cart flow initiated for {order_id}."
