import json
from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException, Header
from config.db import AsyncSessionLocal
from config.config import settings
from config.clients import razorpay_client
from config.logger import get_logger
from razorpay.errors import SignatureVerificationError
from service.service import handle_payment_event, handle_inbound_email, handle_inbound_whatsapp

logger = get_logger(__name__)
router = APIRouter()

# We need wrappers for background tasks because they must manage their own DB sessions
# since the request's DB session might close before the task completes.
async def bg_payment_event(payload: dict):
    async with AsyncSessionLocal() as session:
        await handle_payment_event(payload, session)

async def bg_inbound_email(payload: dict):
    async with AsyncSessionLocal() as session:
        await handle_inbound_email(payload, session)
        
async def bg_inbound_whatsapp(from_number: str, body: str):
    async with AsyncSessionLocal() as session:
        await handle_inbound_whatsapp(from_number, body, session)


@router.post("/listen-events")
async def events_receiver(
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
):
    """
    Razorpay Webhook for Payment Events with cryptographic HMAC-SHA256 signature verification.
    If RAZORPAY_WEBHOOK_SECRET is set, signature validity is strictly verified.
    In DEMO_MODE or when secret is unconfigured, permits graceful fallback so local testing/curl is unaffected.
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8") if body_bytes else ""
    secret = settings.razorpay_webhook_secret

    if secret:
        if not x_razorpay_signature:
            if settings.demo_mode:
                logger.warning("[WEBHOOK] Missing X-Razorpay-Signature in DEMO_MODE; bypassing for local testing.")
            else:
                logger.error("[WEBHOOK] Missing X-Razorpay-Signature header in production mode.")
                raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")
        else:
            try:
                razorpay_client.utility.verify_webhook_signature(body_str, x_razorpay_signature, secret)
                logger.info("[WEBHOOK] Razorpay webhook signature verified successfully.")
            except SignatureVerificationError:
                logger.error("[WEBHOOK] Invalid Razorpay webhook signature.")
                raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")
    elif x_razorpay_signature:
        logger.info("[WEBHOOK] Received X-Razorpay-Signature but RAZORPAY_WEBHOOK_SECRET is not configured.")

    try:
        payload = json.loads(body_str) if body_str else {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    background_tasks.add_task(bg_payment_event, payload)
    return {"status": "accepted"}
    

@router.post("/listen-emails")
async def email_receiver(request: Request, background_tasks: BackgroundTasks):
    """Resend Inbound Email Webhook"""
    payload = await request.json()
    background_tasks.add_task(bg_inbound_email, payload)
    return {"status": "accepted"}


@router.post("/listen-message")
async def whatsapp_receiver(background_tasks: BackgroundTasks, From: str = Form(...), Body: str = Form(...)):
    """Twilio WhatsApp Webhook"""
    background_tasks.add_task(bg_inbound_whatsapp, From, Body)
    return {"status": "accepted"}
