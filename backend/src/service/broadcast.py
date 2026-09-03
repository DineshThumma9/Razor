import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.models import RecoveryState

logger = logging.getLogger("renvue.broadcast")

stream_router = APIRouter(prefix="/api", tags=["stream"])

# Active SSE client subscriber queues
_subscribers: Set[asyncio.Queue] = set()
_listener_task: asyncio.Task | None = None

def state_to_case_dict(state: RecoveryState) -> dict:
    return {
        "case_id": state.case_id,
        "source_id": state.source_id,
        "case_type": state.case_type,
        "decline_type": state.decline_type,
        "failure_reason": state.failure_reason,
        "amount_inr": state.amount_inr,
        "recovered_amount": state.recovered_amount,
        "customer": state.customer or {},
        "contact_preference": state.contact_preference,
        "language": state.language,
        "recovery_status": state.recovery_status,
        "attempt_count": state.attempt_count,
        "last_action_taken": state.last_action_taken,
        "first_seen_at": state.first_seen_at.isoformat() if state.first_seen_at else None,
        "next_retry_at": state.next_retry_at.isoformat() if state.next_retry_at else None,
        "audit_log": state.audit_log or [],
    }

async def _redis_listener():
    """Background task in web process to receive broadcasts from worker processes."""
    try:
        from config.clients import get_redis_client
        r = get_redis_client()
        pubsub = r.pubsub()
        await pubsub.subscribe("renvue:sse_channel")
        async for message in pubsub.listen():
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                for q in list(_subscribers):
                    try:
                        q.put_nowait(data)
                    except Exception:
                        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"[SSE Redis Listener] Error: {e}")

def _ensure_redis_listener():
    global _listener_task
    if _listener_task is None or _listener_task.done():
        try:
            loop = asyncio.get_running_loop()
            _listener_task = loop.create_task(_redis_listener())
        except RuntimeError:
            pass

async def broadcast_case_update(state: RecoveryState):
    try:
        case_data = state_to_case_dict(state)
        payload = json.dumps({"type": "CASE_UPDATED", "data": case_data})
        # 1. Deliver to local process subscribers
        for q in list(_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass
        # 2. Publish to Redis for other processes (e.g. Uvicorn web server)
        try:
            from config.clients import get_redis_client
            r = get_redis_client()
            await r.publish("renvue:sse_channel", payload)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[SSE] Error formatting broadcast: {e}")

async def broadcast_event(event_type: str, data: dict):
    try:
        payload = json.dumps({"type": event_type, "data": data})
        for q in list(_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass
        try:
            from config.clients import get_redis_client
            r = get_redis_client()
            await r.publish("renvue:sse_channel", payload)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[SSE] Error broadcasting event {event_type}: {e}")

@stream_router.get("/stream")
async def sse_endpoint():
    _ensure_redis_listener()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    logger.info(f"[SSE] Client connected. Active subscribers: {len(_subscribers)}")

    async def event_generator():
        # Initial handshake
        yield f"data: {json.dumps({'type': 'CONNECTED', 'subscribers': len(_subscribers)})}\n\n".encode("utf-8")
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {msg}\n\n".encode("utf-8")
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep HTTP connection active through reverse proxies
                    yield b": keep-alive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _subscribers.discard(queue)
            logger.info(f"[SSE] Client disconnected. Remaining subscribers: {len(_subscribers)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
