from datetime import datetime, timedelta, timezone
import random
import time
from fastapi import APIRouter, Depends

from config.config import settings
from config.db import get_db
from config.logger import get_logger
from models.models import RecoveryState
from models.schema import CustomerAction, SimulationEvent
from service.service import handle_inbound_whatsapp, handle_payment_event
from service.states import load_state

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


def fpayload_to_payload(fstate: SimulationEvent):
     # Mock an order (represents a payment attempt that never completed)
    acc_id = getattr(fstate, "account_id", None) or "acc_TestMode"
    amount_paise = int(round(float(fstate.amount) * 100))

    if fstate.event_type in ["order.failed", "failed_payment", "payment.failed"]:
        
        order = {
            "id": f"order_mock_{int(time.time())}_{random.random()*10}",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"rcpt_fail_{random.random()*10}_{int(time.time())}",
            "notes": {
                "customer_name": fstate.name,
                "customer_email": fstate.email,
                "scenario": "failed_payment",
                "failure_reason": fstate.decline_reason,
            },
        }

        _id = f"pay_fail_{int(time.time())}_{int(random.random()*1000)}"
        webhook_payload = {
            "entity": "event",
            "account_id": acc_id,
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": _id,
                        "entity": "payment",
                        "amount": amount_paise,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": order["id"],
                        "name": fstate.name,
                        "email": fstate.email,
                        "contact": fstate.phone,
                        "error_description": order["notes"]["failure_reason"],
                        "created_at": int(time.time()),
                    }
                }
            },
            "created_at": int(time.time())
        }
        
        return webhook_payload, _id 

    elif fstate.event_type in ["subscription_failed", "subscription.halted"]:
        plan = {
        "id": f"plan_mock_{int(time.time())}",
        "period": "monthly",
        "interval": 1,
        "item": {
            "name": "Renvue Pro — Test Plan",
            "amount": amount_paise,
            "currency": "INR",
            "description": "Monthly subscription (test)",
        },
        }
        start_at = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

        _id = f"sub_mock_{int(time.time())}"
        cust_id = f"cust_mock_{int(time.time())}"
        decline_reason = fstate.decline_reason or random.choice(
            [
                "Payment method expired",
                "Insufficient funds",
                "User cancellation",
                "Declined by bank"
            ]
        )
        sub = {
            "id": _id,
            "customer_id": cust_id,
            "plan_id": plan["id"],
            "amount": amount_paise,
            "total_count": 12,
            "customer_notify": 1,
            "start_at": start_at,
            "customer_details": {
                "name": fstate.name,
                "email": fstate.email,
                "contact": fstate.phone,
            },
            "notes": {
                "customer_name": fstate.name,
                "customer_email": fstate.email,
                "customer_contact": fstate.phone,
                "scenario": "subscription_halted",
                "halt_reason": decline_reason,
                "failure_reason": decline_reason,
                "amount": fstate.amount,
            },
        }

        webhook_payload = {
            "entity": "event",
            "account_id": acc_id,
            "event": "subscription.halted",
            "contains": ["subscription"],
            "payload": {
                "subscription": {
                    "entity": sub
                }
            },
            "created_at": int(time.time())
        }
        
        logger.info(f"Created plan: {plan['id']}")
        return webhook_payload, _id

    elif fstate.event_type in ["invoice_failed", "invoice.expired"] :
        rzp_cust = {
            "id": f"cust_mock_{int(time.time())}",
            "name": fstate.name,
            "email": fstate.email,
            "contact": fstate.phone,
        }
        
        # Mock invoice
        _id = f"inv_mock_{int(time.time())}"
        inv = {
            "id": _id,
            "type": "invoice",
            "description": f"Monthly billing for {fstate.name}",
            "customer_id": rzp_cust["id"],
            "amount": amount_paise,
            "currency": "INR",
            "date": int(time.time()),
            "customer_details": {
                "name": fstate.name,
                "email": fstate.email,
                "contact": fstate.phone,
                "customer_name": fstate.name,
                "customer_email": fstate.email,
                "customer_contact": fstate.phone,
            },
            "line_items": [
                {
                    "name": "Software License",
                    "description": "Monthly API access",
                    "amount": amount_paise,
                    "currency": "INR",
                    "quantity": 1,
                }
            ],
            "notes": {
                "scenario": "overdue_invoice",
                "days_overdue": random.random()*30,
            },
        }

        webhook_payload = {
            "entity": "event",
            "account_id": acc_id,
            "event": "invoice.expired",
            "contains": ["invoice"],
            "payload": {
                "invoice": {
                    "entity": inv
                }
            },
            "created_at": int(time.time())
        }
        
        return webhook_payload, _id
    
    return None, None



@router.post("/fake-event")
async def fake_event(fstate: SimulationEvent, db=Depends(get_db)):
    payload, _id = fpayload_to_payload(fstate)
    if payload:
        # Call the service directly — NOT via HTTP — so it hits the LOCAL db
        await handle_payment_event(payload, db)
    return {"id": _id}


import json


async def generate_success_payload(case_id, db):

    state: RecoveryState = await load_state(case_id, db)
    if not state:
        return None

    amount_paise = int(round(float(state.amount_inr) * 100))
    return {
        "entity": "event",
        "account_id": "acc_BFQ7uQEaa7j2z7",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": state.case_id,
                    "entity": "payment",
                    "amount": amount_paise,
                    "currency": "INR",
                    "base_amount": amount_paise,
                    "status": "captured",
                    "order_id": state.source_id,
                    "invoice_id": None,
                    "international": False,
                    "method": "wallet",
                    "amount_refunded": 0,
                    "amount_transferred": 0,
                    "refund_status": None,
                    "captured": True,
                    "description": None,
                    "card_id": None,
                    "bank": None,
                    "wallet": "payzapp",
                    "vpa": None,
                    "email": state.customer.get("email", ""),
                    "contact": state.customer.get("contact", ""),
                    "notes": [],
                    "fee": 2,
                    "tax": 0,
                    "error_code": None,
                    "error_description": None,
                    "error_source": None,
                    "error_step": None,
                    "error_reason": None,
                    "acquirer_data": {
                        "transaction_id": None
                    },
                    "created_at": int(time.time())
                }
            }
        },
        "created_at": int(time.time())
    }



@router.post("/fake-action")
async def fake_action(action: CustomerAction, db=Depends(get_db)):
    if action.actions == "pay":
        success_payload = await generate_success_payload(action.case_id, db)
        if success_payload:
            await handle_payment_event(success_payload, db)
    elif action.actions == "ignore":
        state = await load_state(action.case_id, db)
        if state:
            if state.recovery_status in ["recovered", "closed", "escalated"]:
                return {"status": f"Case is already {state.recovery_status}"}
            if state.active_task_id:
                from background.worker import revoke_active_task
                await revoke_active_task(state.active_task_id)
                state.active_task_id = None
                from service.states import save_state
                await save_state(state, db)
            from background.worker import invoke_agent_task
            await invoke_agent_task(action.case_id)
    elif action.actions == "reply":
        # Route directly to the whatsapp handler with the explicit case_id
        state = await load_state(action.case_id, db)
        if state:
            phone = state.customer.get("contact", "9876543210")
            await handle_inbound_whatsapp(phone, action.messages, db, case_id=action.case_id)
    return {"status": "ok"}
