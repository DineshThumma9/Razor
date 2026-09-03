from celery.app.builtins import logger
import asyncio
from typing import Optional

import httpx
import razorpay
import resend
from config.config import settings
from config.constants import email_messages
from elevenlabs.client import AsyncBaseElevenLabs
from redis.asyncio import Redis
from twilio.http.async_http_client import AsyncTwilioHttpClient
from twilio.rest import Client

resend.api_key = settings.resend_api_key
elevenlabs_client = AsyncBaseElevenLabs(api_key=settings.eleven_api_key)
twilo_http_client = None
twilo_client = None
http_client = None
redis_client = None

razorpay_client = razorpay.Client(
    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
)

def get_twilio_client():
    global twilo_http_client, twilo_client
    if twilo_client is None:
        twilo_http_client = AsyncTwilioHttpClient()
        twilo_client = Client(
            settings.twilo_account_sid,
            settings.twilo_auth_token,
            http_client=twilo_http_client,
        )
    return twilo_client

def get_http_client():
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient()
    return http_client

def get_redis_client():
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return redis_client


async def send_resend_email(
    urgency: str, customer_name: str, customer_email: str, amount_inr: float, extra_context: Optional[dict] = None
):
    extra = extra_context or {}
    template = email_messages.get(urgency, email_messages["gentle"])
    try:
        html_content = template.format(
            name=customer_name,
            amount=f"{amount_inr:,.0f}",
            invoice_number=extra.get("invoice_number", "INV-2026-001"),
            link=extra.get("link", f"https://rzp.io/l/inv-{customer_email.split('@')[0] if customer_email else 'corp'}")
        )
    except Exception:
        html_content = template.format(name=customer_name, amount=f"{amount_inr:,.0f}")

    try:
        if settings.demo_mode:
            logger.info(f"[DEMO SANDBOX] Email to {customer_email} ({urgency}): amount ₹{amount_inr:,.0f} (credits preserved)")
            return True 

        response = await resend.Emails.send_async(
            {
                "from": "Acme <onboarding@resend.dev>",
                "to": [customer_email],
                "subject": f"Action Required: Payment Recovery ({urgency.capitalize()})",
                "html": html_content,
            }
        )

        print(f"    → Email sent successfully: {response}")
        return True
    except Exception as e:
        print(f"    → (Simulated email due to missing Resend API key: {e})")
        return False


async def create_rzp_payment_link(
    customer_name: str, customer_email: str, customer_contact: str, amount_inr: float
) -> str:
    amount_paise = round(amount_inr * 100)

    def _create():
        return razorpay_client.payment_link.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "description": "Payment Recovery",
                "customer": {
                    "name": customer_name,
                    "email": customer_email,
                    "contact": customer_contact,
                },
                "notify": {"sms": False, "email": False},
            }
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_create), timeout=3.5)
        return response.get("short_url", "URL_NOT_FOUND")
    except Exception as e:
        print(f"    → Razorpay API error / timeout: {e}")
        return f"https://rzp.io/l/simulated-recovery-{customer_email.split('@')[0]}"


async def send_twilio_whatsapp(
    contact_number: str, msg: str, media_url: Optional[str] = None
) -> str:
    if not contact_number.startswith("+"):
        contact_number = "+91" + contact_number

    if "9876543210" in contact_number or "1234567890" in contact_number or settings.demo_mode:
        print(f"    → [DEMO SANDBOX] WhatsApp to {contact_number}: '{msg[:75]}...' (Safe dispatch, credits preserved)")
        return "SMdemo" + "0" * 26

    kwargs = {
        "from_": f"whatsapp:{settings.twilo_whatsapp_number}",
        "body": msg,
        "to": f"whatsapp:{contact_number}",
    }
    if media_url:
        kwargs["media_url"] = [media_url]

    client = get_twilio_client()
    try:
    
        res = await client.messages.create_async(**kwargs)
        if isinstance(res, tuple):
            message = res[0]
        else:
            message = res
        sid = getattr(message, "sid", str(message))
        print(f"    → Twilio WhatsApp message dispatched! SID: {sid}")
        return sid
    except Exception as e:
        print(f"    → Twilio WhatsApp Error: {e}")
        return f"ERROR: {e}"


async def cleanup_clients():
    if twilo_http_client and hasattr(twilo_http_client, 'session') and twilo_http_client.session:
        await twilo_http_client.session.close()
    if http_client:
        await http_client.aclose()
    if redis_client:
        await redis_client.aclose()


async def generate_and_send_voice_note(contact_number: str, msg: str) -> str:
    print(f"  [CLIENT] Generating ElevenLabs Voice...")
    media_url = None
    try:


        if settings.demo_mode:
            print(f"  [CLIENT] Audio URL: {media_url}")
            print(f"  [CLIENT] Dispatching Twilio WhatsApp Message...")
            return "Mesage sent succefully"


            
        audio_generator = elevenlabs_client.text_to_speech.convert(
            text=msg,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_v3",
        )

        chunks = []
        if hasattr(audio_generator, "__aiter__"):
            async for chunk in audio_generator:
                chunks.append(chunk)
        else:
            for chunk in audio_generator:
                chunks.append(chunk)
        audio_bytes = b"".join(chunks)

        print(f"  [CLIENT] Uploading to catbox.moe...")
        client = get_http_client()
        response = await client.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": ("voice.mp3", audio_bytes, "audio/mpeg")},
            timeout=10,
        )
        media_url = response.text.strip()
    except Exception as e:
        print(f"  [CLIENT] Voice Note generation skipped/fallback ({e})")
        media_url = "https://files.catbox.moe/voice_sample_recovery.mp3"

    print(f"  [CLIENT] Audio URL: {media_url}")
    print(f"  [CLIENT] Dispatching Twilio WhatsApp Message...")

    body = "🎙️ (Voice Note attached) " + msg
    sid = await send_twilio_whatsapp(contact_number, body, media_url)

    return sid
