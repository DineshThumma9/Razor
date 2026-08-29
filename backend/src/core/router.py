from fastapi import APIRouter, Request, Form
from core.service import handle_payment_event, handle_inbound_email, handle_inbound_whatsapp

router = APIRouter()

@router.post("/listen-events")
async def events_receiver(request: Request):
    """Razorpay Webhook for Payment Events"""
    payload = await request.json()
    return handle_payment_event(payload)
    
@router.post("/listen-emails")
async def email_receiver(request: Request):
    """Resend Inbound Email Webhook"""
    payload = await request.json()
    return handle_inbound_email(payload)

@router.post("/listen-message")
async def whatsapp_receiver(From: str = Form(...), Body: str = Form(...)):
    """Twilio WhatsApp Webhook"""
    return handle_inbound_whatsapp(From, Body)
