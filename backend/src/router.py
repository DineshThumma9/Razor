





from datetime import datetime
from models import RecoveryState
from pydantic import BaseModel
from fastapi import APIRouter
router = APIRouter()
from fastapi import Request
from agent.graph import start_graph 
import uuid



HANDLED_EVENTS = []
import razorpay
from config import settings 

client = razorpay.Client(auth=(settings.razorpay_key_id,settings.razorpay_key_secret))


def parse_webhook(payload:dict):

    event = payload["event"]

    if event not in HANDLED_EVENTS:
        return None 
    

    customer = dict()
    language = "english"
    s = payload["payload"]["payment"]["entity"]
    if "payment" in payload["contains"]:
        customer["name"] = s["name"]
        customer["email"] = s["email"]
        customer["contact"] = s["contact"]
    elif "subscription" in payload["contains"]:
        cust = client.customer.fetch(s["customer_id"])     
        customer["name"] = cust["name"]   
        customer["email"] = cust["email"]
        customer["contact"] = cust["contact"]
        language = cust["notes"].get("language","english")
    elif "invoice" in payload["contains"]:
        cust = s["customer_details"]
        customer["name"] = cust["name"]   
        customer["email"] = cust["email"]
        customer["contact"] = cust["contact"]
        language = cust["notes"].get("language","english")

    elif "payment_link" in payload["contains"]:
        cust = s["contact"]
        customer["name"] = cust["name"]   
        customer["email"] = cust["email"]
        customer["contact"] = cust["contact"]
        language = cust["notes"].get("language","english")

    
    amount = s["amount"]
    
    return RecoveryState(
        case_id = s["id"],
        source = s["contains"],            
    case_type = payload['event'],    # failed_payment | abandoned_checkout | ...
    decline_type=  None,   
    failure_reason= None,
    amount_inr=amount ,
    recovered_amount= 0.0,
    customer= customer,
    contact_preference="email"  , # email | sms | whatsapp | call
    language = language ,
    recovery_status = "pending",   # pending | in_progress | recovered | escalated | closed
    attempt_count = 0,
    last_action_taken= None,
    first_seen_at= s["created_at"],
    next_retry_at = None,
    audit_log = []
    )




@router.post("/listen-events")
def events_reciver(request:Request):
    start_graph(parse_webhook(request))
    