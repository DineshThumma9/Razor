from starlette.types import Lifespan
from core.models import RecoveryState
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from elevenlabs.client import ElevenLabs
import razorpay 
import os
from twilio.rest import Client
from config import settings

from core.router import router
from core.api_router import api_router

app = FastAPI(title="Renvue API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(api_router)
