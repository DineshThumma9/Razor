
from starlette.types import Lifespan
from core.models import RecoveryState
from fastapi import FastAPI

from elevenlabs.client import ElevenLabs
import razorpay 
import os
from twilio.rest import Client
from config import settings








from core.router import router

app = FastAPI()
app.include_router(router)
