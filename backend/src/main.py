from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.config import settings
from config.logger import setup_logging, get_logger
from config.db import _init_db, init_checkpointer, close_checkpointer, close_db
from config.clients import init_clients, cleanup_clients
from background.worker import init_scheduler, shutdown_scheduler
from service.broadcast import start_broadcast_listener, stop_broadcast_listener, stream_router
from agent.utils import get_llm
from agent.graph import get_compiled_agent
from router.apis import api_router
from router.listeners import router
from router.simulate import router as sim_router

# Initialize unified logging handlers
setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[Lifespan] Initializing all application services and clients...")
    # 1. Database & Checkpointer Pool
    _init_db()
    await init_checkpointer()

    # 2. Shared Network Clients (HTTP, Redis, Twilio)
    await init_clients()

    # 3. Background Taskiq Broker & ScheduleSource
    await init_scheduler()

    # 4. SSE Redis Broadcast Pub/Sub Listener
    await start_broadcast_listener()

    # 5. Agent Singletons Warmup (Compiled StateGraph & Tool-bound LLM)
    get_compiled_agent()
    get_llm()

    logger.info("[Lifespan] All services, connection pools, and client singletons ready.")

    yield

    logger.info("[Lifespan] Shutting down application services and clients...")
    # 1. Stop SSE Broadcast Listener
    await stop_broadcast_listener()

    # 2. Shutdown Taskiq Broker & ScheduleSource
    await shutdown_scheduler()

    # 3. Close Shared Network Clients (HTTP, Redis, Twilio)
    await cleanup_clients()

    # 4. Close Checkpointer Pool & Database Engines
    await close_checkpointer()
    await close_db()

    logger.info("[Lifespan] All services and connection pools closed cleanly.")


app = FastAPI(title="Renvue API", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        settings.frontend_url 
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(sim_router)
app.include_router(api_router)
app.include_router(stream_router)


if __name__ == "__main__":
    uvicorn.run("src.main:app", port=settings.port, reload=True, log_level="info")
