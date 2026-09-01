import logging
import os
from contextlib import asynccontextmanager

from config.db import _init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router.apis import api_router
from router.listeners import router
from config.config import settings


import uvicorn 


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "../logs")
os.makedirs(LOG_DIR, exist_ok=True)


logging.basicConfig(
    filename=os.path.join(LOG_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s[%(levelname)s]%(name)s:%(message)s",
)


from config.db import _init_db, init_checkpointer, close_checkpointer, close_db
from config.clients import cleanup_clients

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Renvue] Initializing Postgres Schema...")
    _init_db()
    await init_checkpointer()
    yield
    print("[Renvue] Shutting down...")
    await close_checkpointer()
    await close_db()
    await cleanup_clients()


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
app.include_router(api_router)


if __name__ == "main":
    uvicorn.run("src.main:app", port=settings.port, reload=True, log_level="info")
