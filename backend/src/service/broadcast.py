import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from config.logger import get_logger
from config.clients import get_redis_client
from models.models import RecoveryState

logger = get_logger(__name__)

stream_router = APIRouter(prefix="/api", tags=["stream"])

# Active SSE client subscriber queues
_subscribers: Set[asyncio.Queue] = set()
_listener_task: asyncio.Task | None = None


async def _redis_listener():
    """Background task in web process to receive broadcasts from worker processes."""
    try:
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


async def start_broadcast_listener():
    """Starts the SSE Redis listener during FastAPI lifespan startup."""
    global _listener_task
    if _listener_task is None or _listener_task.done():
        loop = asyncio.get_running_loop()
        _listener_task = loop.create_task(_redis_listener())
        logger.info("[SSE] Redis broadcast listener started.")


async def stop_broadcast_listener():
    """Stops the SSE Redis listener during FastAPI lifespan shutdown."""
    global _listener_task
    if _listener_task and not _listener_task.done():
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
        logger.info("[SSE] Redis broadcast listener stopped.")


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
        case_data = state.model_dump(mode="json")
        payload = json.dumps({"type": "CASE_UPDATED", "data": case_data})
        published = False
        try:
            r = get_redis_client()
            await r.publish("renvue:sse_channel", payload)
            published = True
        except Exception:
            pass

        # Deliver directly to local process subscribers only if Redis was unavailable
        if not published:
            for q in list(_subscribers):
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"[SSE] Error formatting broadcast: {e}")

async def broadcast_event(event_type: str, data: dict):
    try:
        payload = json.dumps({"type": event_type, "data": data})
        published = False
        try:
            r = get_redis_client()
            await r.publish("renvue:sse_channel", payload)
            published = True
        except Exception:
            pass

        # Deliver directly to local process subscribers only if Redis was unavailable
        if not published:
            for q in list(_subscribers):
                try:
                    q.put_nowait(payload)
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
