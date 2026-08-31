
from threading import settrace_all_threads
from ctypes.wintypes import PINT
from email import message
import calendar
from datetime import date, datetime, timedelta
import resend
import razorpay
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from config import settings
from db import load_state, save_state
from core.models import AuditEntry

from core.clients import razorpay_client as client

from worker import invoke_agent_task
from worker import app 

from pydantic import BaseModel,Field
from core.clients import twilo_client, elevenlabs_client as elevenlabs


import requests


email_messages = {
    'gentle': "Hi {name},<br><br>We noticed your recent payment of ₹{amount} failed. Please ensure your account has sufficient funds. We'll retry soon.<br><br>Thanks,<br>The Team",
    'urgent': "Hi {name},<br><br>Your payment of ₹{amount} has failed again. To avoid service interruption, please update your payment method immediately.<br><br>Thanks,<br>The Team",
    'final': "Dear {name},<br><br>This is our final notice regarding your outstanding payment of ₹{amount}. Your service will be paused if this is not resolved.<br><br>Thanks,<br>The Team"
}



class EmailReminderArgs(BaseModel):
    urgency: str = Field(description="MUST be one of: 'gentle', 'urgent', 'final'")


class PromiseToPayArgs(BaseModel):
    sentiment:str=Field(description="Sentiment of the reply user sent Gentle? Angry?")
    reason: str = Field(description="The reason the user gave for the delay.")
    date_str: str = Field(description="The ISO format date (YYYY-MM-DD) the user promised to pay by.")


class CompleteCaseArgs(BaseModel):
    summary: str = Field(default="Case completed.", description="Summary of actions taken to resolve the case.")

class PaymentLinkArgs(BaseModel):
    pass # No arguments needed!

class EscalateArgs(BaseModel):
    reason: str = Field(description="Detailed reason for why this case is being escalated.")

class SalaryDateArgs(BaseModel):
    pass



def _log_audit(state, tool_name: str, next_retry_at: datetime = None):
    entry = AuditEntry(
        event_triggered=tool_name,
        amount=str(state.amount_inr),
        recovery_status=state.recovery_status,
        customer=state.customer,
        next_contact=next_retry_at
    )
    state.audit_log.append(entry.model_dump(mode="json"))
    if next_retry_at:
        state.next_retry_at = next_retry_at
    save_state(state)



@tool(args_schema=EmailReminderArgs)
def send_email_reminder(urgency: str,config: RunnableConfig) -> str:
    """
    Send a recovery email to the customer.
    Use 'gentle' for first contact, 'urgent' for 2nd attempt, 'final' before escalation.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    state = load_state(case_id)
    customer_name = state.customer.get("name", "Customer")
    customer_email = state.customer.get("email", "")
    amount_inr = state.amount_inr

    print(f"\n  [TOOL] send_email_reminder")
    print(f"    → To      : {customer_name} <{customer_email}>")
    print(f"    → Amount  : ₹{amount_inr}")
    print(f"    → Urgency : {urgency}")

    html_content = email_messages.get(urgency, email_messages['gentle']).format(
        name=customer_name, amount=amount_inr
    )
        
    try:
        resend.api_key = settings.resend_api_key
        print(f"api key:{settings.resend_api_key}")
        response = resend.Emails.send({
            "from": "Acme <onboarding@resend.dev>",
            "to": [customer_email],
            "subject": f"Action Required: Payment Recovery ({urgency.capitalize()})",
            "html": html_content,
        })
        print(f"    → Email sent successfully: {response}")
        invoke_agent_task.apply_async(args=[case_id], countdown=3*86400)

    except Exception as e:
        print(f"    → (Simulated email due to missing Resend API key: {e})")
    
    next_contact = datetime.now() + timedelta(days=3)
    _log_audit(state, "send_email_reminder", next_contact)

    return f"Email ({urgency}) queued for {customer_email}"



@tool(args_schema=PaymentLinkArgs)
def create_payment_link(config: RunnableConfig) -> str:
    """
    Create a Razorpay payment link for the customer to complete payment.
    Use this for hard declines (expired card, lost card) where the customer must re-enter card details.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    state = load_state(case_id)
    customer_name = state.customer.get("name", "Customer")
    customer_email = state.customer.get("email", "")
    customer_contact = state.customer.get("contact", "")
    amount_inr = state.amount_inr
    
    amount_paise = round(amount_inr * 100)
    
    print(f"\n  [TOOL] create_payment_link")
    print(f"    → Customer : {customer_name} ({customer_email})")
    print(f"    → Amount   : ₹{amount_inr:.2f}")

    try:
        response = client.payment_link.create({
            "amount": amount_paise,
            "currency": "INR",
            "description": "Payment Recovery",
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contact": customer_contact
            },
            "notify": {
                "sms": False,
                "email": False
            }
        })
        short_url = response.get("short_url", "URL_NOT_FOUND")
    except Exception as e:
        print(f"    → Razorpay API error: {e}")
        short_url = f"https://rzp.io/l/simulated-recovery-{customer_email.split('@')[0]}"

    print(f"    → Link     : {short_url}")

    next_contact = datetime.now() + timedelta(days=1)
    invoke_agent_task.apply_async(args=[case_id], countdown=1*86400)
    
    _log_audit(state, "create_payment_link", next_contact)

    return short_url


@tool(args_schema=EscalateArgs)
def escalate_to_human(reason: str, config: RunnableConfig) -> str:
    """
    Escalate this case to a human agent.
    Use when: hard decline after payment link sent, dispute raised,
    3+ failed attempts, or legal action needed.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    state = load_state(case_id)
    customer_name = state.customer.get("name", "Customer")
    
    print(f"\n  [TOOL] escalate_to_human")
    print(f"    → Customer : {customer_name}")
    print(f"    → Reason   : {reason}")
    
    state.recovery_status = "escalated"
    _log_audit(state, "escalate_to_human", None)
    
    return f"Case for {customer_name} escalated to human. Reason: {reason}"


@tool(args_schema=SalaryDateArgs)
def get_next_salary_date() -> str:
    """
    Returns upcoming salary milestone dates (1st, 15th, last Friday of month).
    Use this to decide the best retry date for soft declines (insufficient funds).
    """
    ref = date.today()
    year, month = ref.year, ref.month

    milestones = []
    for day in [1, 15]:
        d = date(year, month, day)
        if d > ref:
            milestones.append(d)

    last_day = calendar.monthrange(year, month)[1]
    last_date = date(year, month, last_day)
    offset = (last_date.weekday() - 4) % 7
    last_friday = last_date - timedelta(days=offset)
    if last_friday > ref:
        milestones.append(last_friday)

    milestones = sorted(set(milestones))

    if not milestones:
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        milestones = [date(next_year, next_month, 1)]

    result = ", ".join(str(d) for d in milestones)
    print(f"\n  [TOOL] get_next_salary_date")
    print(f"    → Upcoming milestones: {result}")
    
    return result


@tool(args_schema=CompleteCaseArgs)
def complete_case(summary: str) -> str:
    """
    Call this tool when you have finished taking all necessary actions for this case.
    This tells the system to stop the workflow and move to the audit phase.
    """
    print(f"\n  [TOOL] complete_case")
    print(f"    → Summary : {summary}")
    return "Case workflow completed."


@tool 
def send_whatsapp_msg(msg:str, config: RunnableConfig):
    """
    Sends a WhatsApp message to the customer using Twilio.
    msg is the content of the message.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    state = load_state(case_id)
    contact_number = state.customer.get("contact", "")
    
    if not contact_number:
        return "Failed: Customer has no contact number."

    if not contact_number.startswith("+"):
        contact_number = "+91" + contact_number

    message = twilo_client.messages.create(
        from_=f"whatsapp:{settings.twilo_whatsapp_number}", 
        body=msg,
        to=f"whatsapp:{contact_number}"      
        )


    next_contact = datetime.now() + timedelta(days=3)
    invoke_agent_task.apply_async(args=[case_id], countdown=3*86400)

    _log_audit(state, "send_whatsapp_msg", next_contact)

    print(f"Message dispatched successfully! SID: {message.sid}")



@tool
def get_voice_call(msg:str, config: RunnableConfig):
    """
    Initiates an AI voice call using ElevenLabs to the customer, and sends it as a WhatsApp voice note.
    msg is the text to speak.
    """

    print(f"\n  [TOOL] get_voice_call -> Generating ElevenLabs Voice...")
    audio_stream = elevenlabs.text_to_speech.convert(
        text=msg,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_v3",
    )
    
    audio_bytes = b"".join(audio_stream)

    print(f"  [TOOL] get_voice_call -> Uploading to catbox.moe for Twilio...")
    response = requests.post(
        "https://catbox.moe/user/api.php", 
        data={"reqtype": "fileupload"}, 
        files={"fileToUpload": ("voice.mp3", audio_bytes, "audio/mpeg")}
    )
    media_url = response.text.strip()
    print(f"  [TOOL] get_voice_call -> Audio URL: {media_url}")

    case_id = config.get("configurable", {}).get("thread_id")
    state = load_state(case_id)
    contact_number = state.customer.get("contact", "")
    
    if not contact_number:
        return "Failed: Customer has no contact number."

    if not contact_number.startswith("+"):
        contact_number = "+91" + contact_number

    print(f"  [TOOL] get_voice_call -> Dispatching Twilio WhatsApp Message...")
    message = twilo_client.messages.create(
        from_=f"whatsapp:{settings.twilo_whatsapp_number}",
        body="🎙️ (Voice Note attached) " + msg,
        media_url=[media_url],
        to=f"whatsapp:{contact_number}"
    )

    next_contact = datetime.now() + timedelta(days=2)
    invoke_agent_task.apply_async(args=[case_id], countdown=2*86400)
    
    _log_audit(state, "get_voice_call", next_contact)

    return f"Voice note dispatched successfully to {contact_number}! SID: {message.sid}"

@tool(args_schema=PromiseToPayArgs)
def log_promise_to_pay(date_str: str, reason: str, config: RunnableConfig):
    """
    Call this tool when a customer replies via email or WhatsApp and promises to pay 
    on a specific future date. This will log their promise and pause all automated 
    reminders until that date.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    state = load_state(case_id)
    
    target_date = datetime.fromisoformat(date_str)
    _log_audit(state, "log_promise_to_pay", target_date)

    now = datetime.now()
    delta_seconds = (target_date - now).total_seconds()
    if delta_seconds < 0:
        delta_seconds = 60 
    invoke_agent_task.apply_async(args=[case_id], countdown=int(delta_seconds))

    return f"Successfully logged promise to pay on {date_str}. Let the user know it is confirmed."

    


tools = [
    send_email_reminder,
    create_payment_link,
    escalate_to_human,
    get_next_salary_date,
    complete_case,
    get_voice_call,
    send_whatsapp_msg,
    log_promise_to_pay
]
