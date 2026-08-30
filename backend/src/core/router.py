from fastapi import APIRouter, Request, Form, BackgroundTasks
from core.service import handle_payment_event, handle_inbound_email, handle_inbound_whatsapp

router = APIRouter()

@router.post("/listen-events")
async def events_receiver(request: Request, background_tasks: BackgroundTasks):
    """Razorpay Webhook for Payment Events"""
    payload = await request.json()
    background_tasks.add_task(handle_payment_event, payload)
    return {"status": "accepted"}
    
@router.post("/listen-emails")
async def email_receiver(request: Request, background_tasks: BackgroundTasks):
    """Resend Inbound Email Webhook"""
    payload = await request.json()
    background_tasks.add_task(handle_inbound_email, payload)
    return {"status": "accepted"}

@router.post("/listen-message")
async def whatsapp_receiver(background_tasks: BackgroundTasks, From: str = Form(...), Body: str = Form(...)):
    """Twilio WhatsApp Webhook"""
    background_tasks.add_task(handle_inbound_whatsapp, From, Body)
    return {"status": "accepted"}
