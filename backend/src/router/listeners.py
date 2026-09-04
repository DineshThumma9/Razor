from fastapi import APIRouter, Request, Form, BackgroundTasks
from config.db import AsyncSessionLocal
from config.logger import get_logger
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
async def events_receiver(request: Request, background_tasks: BackgroundTasks):
    """Razorpay Webhook for Payment Events"""
    payload = await request.json()
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
