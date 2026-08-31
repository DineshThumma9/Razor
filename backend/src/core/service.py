from langchain_mistralai import ChatMistralAI
from datetime import datetime
import uuid
import razorpay
from langchain_core.messages import HumanMessage
from sqlmodel import Session, select

from core.models import RecoveryState
from agent.graph import build_agent
from config import settings
from db import engine, load_state, save_state
from core.clients import razorpay_client as client

HANDLED_EVENTS = [
    "payment.failed", 
    "payment.captured",
    "payment_link.expired",
    "subscription.halted",
    "invoice.expired"
]

def parse_webhook(payload: dict) -> RecoveryState | None:
    event = payload.get("event")
    if event not in HANDLED_EVENTS:
        return None 
    
    if event == "payment.captured":
        return None 
        
    contains = payload.get("contains", [])
    customer = dict()
    language = "english"
    amount = 0.0
    case_id = str(uuid.uuid4())
    source_id = "unknown"
    failure_reason = "Unknown"
    
    # Extract based on the richest available entity
    if "subscription" in contains:
        s = payload["payload"]["subscription"]["entity"]
        try:
            cust = client.customer.fetch(s["customer_id"])
            customer["name"] = cust.get("name", "Customer")
            customer["email"] = cust.get("email", "")
            customer["contact"] = cust.get("contact", "")
        except Exception:
            notes = s.get("notes") or {}
            customer["name"] = notes.get("customer_name", "Customer")
            customer["email"] = notes.get("customer_email", "")
            customer["contact"] = notes.get("customer_contact", "")
            language = notes.get("language", "english")
        case_id = s.get("id")
        source_id = s.get("plan_id", "unknown")
        
    elif "invoice" in contains:
        s = payload["payload"]["invoice"]["entity"]
        cust = s.get("customer_details", {})
        customer["name"] = cust.get("customer_name", cust.get("name", "Customer"))
        customer["email"] = cust.get("customer_email", cust.get("email", ""))
        customer["contact"] = cust.get("customer_contact", cust.get("contact", ""))
        notes = s.get("notes") or {}
        language = notes.get("language", "english") if isinstance(notes, dict) else "english"
        case_id = s.get("id")
        source_id = s.get("order_id", "unknown")
        amount = float(s.get("amount", 0)) / 100.0
        
    elif "payment_link" in contains:
        s = payload["payload"]["payment_link"]["entity"]
        cust = s.get("customer", {})
        customer["name"] = cust.get("name", "Customer")
        customer["email"] = cust.get("email", "")
        customer["contact"] = cust.get("contact", "")
        notes = s.get("notes") or {}
        language = notes.get("language", "english") if isinstance(notes, dict) else "english"
        case_id = s.get("id")
        source_id = s.get("order_id", "unknown")
        amount = float(s.get("amount", 0)) / 100.0
        
    elif "payment" in contains:
        s = payload["payload"]["payment"]["entity"]
        customer["name"] = s.get("name", "Customer")
        customer["email"] = s.get("email", "")
        customer["contact"] = s.get("contact", "")
        language = "english"
        case_id = s.get("id")
        source_id = s.get("order_id", "unknown")
        amount = float(s.get("amount", 0)) / 100.0
        failure_reason = s.get("error_description", "Unknown")

    case_type = "failed_payment"
    if "subscription" in contains:
        case_type = "failed_subscription"
    elif "invoice" in contains:
        case_type = "overdue_invoice"
    elif "payment_link" in contains:
        case_type = "abandoned_checkout"
        
    decline_type = None
    if case_type in ['failed_payment', 'failed_subscription']:
        fail_lower = failure_reason.lower()
        if "insufficient funds" in fail_lower or "limit" in fail_lower:
            decline_type = "soft"
        else:
            decline_type = "hard"

    return RecoveryState(
        case_id = case_id or str(uuid.uuid4()),
        source_id = source_id,            
        case_type = case_type,
        decline_type= decline_type,   
        failure_reason= failure_reason,
        amount_inr=amount,
        recovered_amount= 0.0,
        customer= customer,
        contact_preference="email",
        language = language,
        recovery_status = "pending",
        attempt_count = 0,
        last_action_taken= None,
        first_seen_at= datetime.now(),
        next_retry_at = None,
        audit_log = []
    )

def handle_payment_event(payload: dict) -> dict:
    event = payload.get("event")
    
    if event == "payment.captured":
        amount = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("amount", 0) / 100.0
        contact = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("contact", "")
        if contact:
            contact_number = contact.replace("+91", "").replace(" ", "") # normalise
            with Session(engine) as session:
                cases = session.exec(select(RecoveryState).where(RecoveryState.recovery_status.not_in(["recovered", "closed", "escalated"]))).all()
                for case in cases:
                    db_contact = case.customer.get("contact", "").replace("+91", "").replace(" ", "")
                    if db_contact == contact_number:
                        case.recovery_status = "recovered"
                        case.recovered_amount = amount
                        session.add(case)
                        session.commit()
                        return {"status": f"Case {case.case_id} marked as recovered!"}
        return {"status": "ok, but no active case matched contact"} 
        
    elif event in ["payment.failed", "payment_link.expired", "subscription.halted", "invoice.expired"]:
        new_state = parse_webhook(payload)
        if new_state:
            save_state(new_state)
            agent = build_agent(new_state)
            config = {"configurable": {"thread_id": new_state.case_id}}
            agent.invoke({"messages": [], "recovery_state": new_state, "event_source": f"webhook.{event}"}, config=config)
            return {"status": "Agent started for new case"}
            
    return {"status": "ok"}

def handle_inbound_email(payload: dict) -> dict:
    recipient = payload.get("to", "")
    try:
        case_id = recipient.split("+")[1].split("@")[0]
    except IndexError:
        return {"status": "ignored", "reason": "No valid case_id in recipient"}
        
    state = load_state(case_id)
    if not state or state.recovery_status in ["recovered", "closed", "escalated"]:
        return {"status": "ignored", "reason": "Case not active"}
    

    customer_reply_text = payload.get("text", "")
    new_message = HumanMessage(content=f"Customer Replied via Email: {customer_reply_text}")

        
    agent = build_agent(state)
    config = {"configurable": {"thread_id": case_id}}
    agent.invoke(
            {"messages": [new_message], "recovery_state": state, "event_source": "inbound.email"}, 
            config=config
        )

    return {"status": "Agent woken up successfully"}


def handle_inbound_whatsapp(from_number: str, body: str) -> dict:
    print(f"\n[INBOUND WHATSAPP] Received message from {from_number}: {body}")
    
    contact_number = from_number.replace("whatsapp:", "")
    if contact_number.startswith("+91"):
        contact_number = contact_number[3:]
        
    print(f"[INBOUND WHATSAPP] Looking for active case for contact: {contact_number}")
    
    active_case = None
    with Session(engine) as session:
        cases = session.exec(select(RecoveryState).where(RecoveryState.recovery_status.not_in(["recovered", "closed", "escalated"]))).all()
        for case in cases:
            case_contact = case.customer.get("contact", "")
            if case_contact == contact_number or case_contact.endswith(contact_number):
                active_case = case
                break
                
    if not active_case:
        print(f"[INBOUND WHATSAPP] Ignored: No active case found for {contact_number}")
        return {"status": "ignored", "reason": "No active case found for this number"}
        
    print(f"[INBOUND WHATSAPP] Matched case {active_case.case_id}. Waking up agent!")
        
    new_message = HumanMessage(content=f"Customer Replied via WhatsApp: {body}")
    agent = build_agent(active_case)
    config = {"configurable": {"thread_id": active_case.case_id}}
    
    agent.invoke(
        {"messages": [new_message], "recovery_state": active_case, "event_source": "inbound.whatsapp"}, 
        config=config
    )
    
    return {"status": "Agent woken up successfully"}



def detect_downtime(downtime):
    
    # with Session(engine) as session:
    pass 
    
    