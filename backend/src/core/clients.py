from elevenlabs.client import ElevenLabs
import razorpay 
from twilio.rest import Client
from config import settings
import resend

resend.api_key = settings.resend_api_key

elevenlabs_client = ElevenLabs(api_key=settings.eleven_api_key)
razorpay_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
twilo_client = Client(settings.twilo_account_sid, settings.twilo_auth_token)
