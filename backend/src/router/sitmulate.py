





from config.clients import get_http_client
from models.models import RecoveryState
from elevenlabs.types import asr_conversational_config
from elevenlabs.types import asr_conversational_config
from elevenlabs.types import asr_conversational_config
from elevenlabs.types import asr_conversational_config
from background.worker import invoke_agent_task
from background.worker import broker
from service.states import load_state
from service.service import handle_inbound_whatsapp
from config.db import get_db
from service.service import handle_payment_event
from models.schema import CustomerAction
from aiohttp import log
from os import fstatvfs
from requests import RequestException
from config.clients import http_client
from models.schema import SimulationEvent
from fastapi.routing import APIRouter
from config.config import settings

router = APIRouter(prefix="/api")






async def trigeer_webhook(payload:dict):
    try:
        response = await get_http_client().post(settings.backend_url,json=payload,timeout=5)
        print(f"f -> Webhook fired! Status {response.status_code}")
    except RequestException as e:
        print(f"[WARNING] Failed to trigger webhook:{e}")

import time
import random
from datetime import timedelta,timezone
from datetime import datetime

def fpayload_to_payload(fstate:SimulationEvent):
     # Mock an order (represents a payment attempt that never completed)

    if fstate.event_type == "order.failed":
        
        order = {
            "id": f"order_mock_{int(time.time())}_{random.random()*10}",
            "amount": fstate.amount,
            "currency": "INR",
            "receipt": f"rcpt_fail_{random.random()*10}_{int(time.time())}",
            "notes": {
                "customer_name": fstate.name,
                "customer_email": fstate.email,
                "scenario": "failed_payment",
                "failure_reason": fstate.decline_reason,
            },
        }

        _id = f"pay_fail_{int(time.time())}_{random.random()*10}"
        webhook_payload = {
            "entity": "event",
            "account_id": "acc_TestMode",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": _id,
                        "entity": "payment",
                        "amount": fstate.amount,
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

    elif fstate.event_type == "subscription_failed":
        plan = {
        "id": f"plan_mock_{int(time.time())}",
        "period": "monthly",
        "interval": 1,
        "item": {
            "name": "Renvue Pro — Test Plan",
            "amount": 99900,
            "currency": "INR",
            "description": "Monthly subscription (test)",
        },
        }
        start_at = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

        _id = f"sub_mock_{int(time.time())}"
        sub = {
            "id": _id,
            "plan_id": plan["id"],
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
                "halt_reason": random.choice(
                    [
                        "Payment method expired",
                        "Insufficient funds",
                        "User cancellation",
                        "Declined by bank"
                    ]
                )
            },
        }

        webhook_payload = {
            "entity": "event",
            "account_id": "acc_TestMode",
            "event": "subscription.halted",
            "contains": ["subscription"],
            "payload": {
                "subscription": {
                    "entity": sub
                }
            },
            "created_at": int(time.time())
        }
        
        log(f"  → Created plan: {plan['id']}")
        return webhook_payload, _id

    elif fstate.event_type == "invoice_failed":
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
            "amount": fstate.amount,
            "currency": "INR",
            "date": int(time.time()),
            "customer_details": {
                "customer_name": fstate.name,
                "customer_email": fstate.email,
                "customer_contact": fstate.phone,
            },
            "line_items": [
                {
                    "name": "Software License",
                    "description": "Monthly API access",
                    "amount": fstate.amount,
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
            "account_id": "acc_TestMode",
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



from fastapi import Depends

    

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
                    "amount": state.amount_inr,
                    "currency": "INR",
                    "base_amount": state.amount_inr,
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


from fastapi import Depends 
import config

@router.post("/fake-action")
async def fake_action(action: CustomerAction, db=Depends(get_db)):
    if action.actions == "pay":
        success_payload = await generate_success_payload(action.case_id, db)
        if success_payload:
            await handle_payment_event(success_payload, db)
    elif action.actions == "ignore":
        state = await load_state(action.case_id, db)
        if state and state.active_task_id:
            from background.worker import revoke_active_task
            await revoke_active_task(state.active_task_id)
            state.active_task_id = None
            from service.states import save_state
            await save_state(state, db)
        if broker.connection_pool is None:
            await broker.startup()
        await invoke_agent_task.kiq(action.case_id)
    elif action.actions == "reply":
        # Route directly to the whatsapp handler with the explicit case_id
        state = await load_state(action.case_id, db)
        if state:
            phone = state.customer.get("contact", "9876543210")
            await handle_inbound_whatsapp(phone, action.messages, db, case_id=action.case_id)
    return {"status": "ok"}
