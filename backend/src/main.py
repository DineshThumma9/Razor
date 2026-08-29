
from starlette.types import Lifespan
from core.models import RecoveryState
from fastapi import FastAPI

from elevenlabs.client import ElevenLabs
import razorpay 
import os
from twilio.rest import Client
from config import settings




app = FastAPI()


elevenlabs = ElevenLabs(api_key=settings.eleven_api_key)
client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
twilo_client = Client(settings.twilo_account_sid, settings.twilo_auth_token)

import resend
resend.api_key = settings.resend_api_key


