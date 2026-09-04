import uuid
import asyncio
from datetime import datetime
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource
from taskiq import TaskiqScheduler
from service.states import load_state, save_state
from langchain_core.messages import HumanMessage
from config.clients import razorpay_client as client, get_redis_client
from models.models import RecoveryState
from config.db import AsyncSessionLocal, _init_db
from sqlmodel import select
from agent.graph import build_agent
from config.config import settings
from config.logger import get_logger

logger = get_logger(__name__)
redis_url = settings.redis_url


broker = ListQueueBroker(
    redis_url,
    socket_timeout=None,
)
schedule_source = ListRedisScheduleSource(redis_url)
scheduler = TaskiqScheduler(broker, [schedule_source])


async def init_scheduler():
    """Startup broker and schedule source during lifespan."""
    if not broker.is_worker_process:
        if broker.connection_pool is None:
            await broker.startup()
        if schedule_source._connection_pool is None:
            await schedule_source.startup()
        logger.info("[TASKIQ] Broker and schedule source initialized.")


async def shutdown_scheduler():
    """Shutdown broker and schedule source during lifespan."""
    if not broker.is_worker_process:
        if broker.connection_pool:
            await broker.shutdown()
        if hasattr(schedule_source, "shutdown") and schedule_source._connection_pool:
            try:
                await schedule_source.shutdown()
            except Exception:
                pass
        logger.info("[TASKIQ] Broker and schedule source shut down.")


@broker.task(task_name='worker.invoke_agent_task')
async def invoke_agent_task(case_id: str):
    logger.info(f"[TASKIQ] Waking up agent for case {case_id}...")
    _init_db()
    async with AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        if not state or state.recovery_status in ["recovered", "closed", "escalated"]:
            logger.info(f"[TASKIQ] Case {case_id} is no longer active ({state.recovery_status if state else 'not found'}). Aborting.")
            return "Aborted: Case inactive."
            
        if state.active_task_id:
            r = get_redis_client()
            is_revoked = await r.exists(f"revoked_task:{state.active_task_id}")
            if is_revoked:
                logger.info(f"[TASKIQ] Task {state.active_task_id} for case {case_id} was revoked. Aborting.")
                return "Aborted: Task revoked."
                
        if state.attempt_count == 0:
            messages = []
            event_source = "automated.webhook"
        else:
            messages = [HumanMessage(content="Scheduled Follow-up Triggered. Please check the current state and decide the next action.")]
            event_source = "scheduled.follow_up"
        
        agent = build_agent(state)
        config = {"configurable": {"thread_id": case_id}}
        
        await agent.ainvoke(
            {"messages": messages, "recovery_state": state, "event_source": event_source}, 
            config=config
        )
    return f"Success: Agent invoked for case {case_id}."

async def revoke_active_task(task_id: str):
    """Cancel a pending Taskiq task by ID from Redis schedule source and set revocation flag."""
    if task_id:
        logger.info(f"[TASKIQ] Revoking task {task_id}")
        try:
            if schedule_source._connection_pool is None:
                await schedule_source.startup()
            await schedule_source.delete_schedule(task_id)
        except Exception as e:
            logger.warning(f"[TASKIQ] Note deleting schedule from Redis: {e}")
        r = get_redis_client()
        await r.setex(f"revoked_task:{task_id}", 86400, "1")

@broker.task(task_name='worker.abandoned_cart_timer')
async def abandoned_cart_timer(order_id: str, customer_data: dict):
    logger.info(f"[TASKIQ] Checking abandoned cart for order {order_id}...")
    
    # Worker is a separate process — must initialize the DB session factory
    _init_db()
    
    try:
        # Client operations should be async. If razorpay client is sync, we should use asyncio.to_thread
        order = await asyncio.to_thread(client.order.fetch, order_id)
        if order.get("status") == "paid":
            logger.info(f"[TASKIQ] Order {order_id} is already paid. Aborting abandoned cart flow.")
            return "Aborted: Order paid."
    except Exception as e:
        logger.error(f"[TASKIQ] Error fetching order {order_id}: {e}")
        return
        
    async with AsyncSessionLocal() as db:
        # Check if a RecoveryState already exists for this order
        existing = (await db.execute(select(RecoveryState).where(RecoveryState.source_id == order_id))).scalars().first()
        if existing:
            logger.info(f"[TASKIQ] RecoveryState already exists for order {order_id}. Aborting.")
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
            case_metadata={},
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
