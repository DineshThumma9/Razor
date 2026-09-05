# pyright: reportMissingImports=false
"""
Renvue — Rich Razorpay Webhook Payload Builder
Constructs authentic 2026 Razorpay Webhook payloads with full banking fidelity,
including card entities (network, last4, issuer), acquirer data (RRN, UTR),
and graceful live Razorpay SDK order integration.
"""

import uuid
import time
import random
from typing import Optional
from config.clients import razorpay_client

CARD_NETWORKS = ["Visa", "MasterCard", "RuPay"]
DEFAULT_LAST4 = ["4242", "1111", "8821", "5543", "9012"]

def try_create_live_razorpay_order(amount_inr: float, receipt_id: str) -> Optional[str]:
    """
    Attempts to create an authentic live Order via the official Razorpay SDK.
    Falls back gracefully if test account limits or rate quotas are reached.
    """
    if not razorpay_client:
        return None
    try:
        order = razorpay_client.order.create({
            "amount": int(amount_inr * 100),
            "currency": "INR",
            "receipt": receipt_id[:40],
            "notes": {"source": "renvue_recovery_engine"}
        })
        return order.get("id")
    except Exception:
        return None


def build_rich_webhook_payload(scen: dict) -> dict:
    """
    Constructs a production-grade Razorpay Webhook JSON payload for a given scenario.
    """
    scen_id = scen.get("id", "SCEN-01")
    amount_inr = float(scen.get("amount_inr", 2499.0))
    amount_paisa = int(amount_inr * 100)
    
    cust = scen.get("customer", {})
    cust_name = cust.get("name", "Customer")
    cust_email = cust.get("email", "customer@example.com")
    cust_phone = cust.get("contact", "9876543210")
    
    method = scen.get("method", "card")
    through = scen.get("through", "HDFC")
    decline_type = scen.get("decline_type", "hard")
    failure_reason = scen.get("failure_reason", "Payment failed")
    
    suffix = uuid.uuid4().hex[:14]
    pay_id = f"pay_{suffix}"
    card_id = f"card_{suffix}"
    
    order_id = try_create_live_razorpay_order(amount_inr, f"rcpt_{scen_id}")
    if not order_id:
        order_id = f"order_{suffix}"
        
    created_at = int(time.time())

    rrn = f"{random.randint(100000000000, 999999999999)}"
    bank_txn_id = f"{random.randint(10000000, 99999999)}"
    acquirer_data = {
        "bank_transaction_id": bank_txn_id,
        "rrn": rrn,
        "auth_code": None
    }

    card_entity = None
    if method == "card":
        network = "RuPay" if through in ["SBI", "PNB", "BOB"] else "Visa" if "HDFC" in through else "MasterCard"
        card_entity = {
            "id": card_id,
            "entity": "card",
            "name": cust_name,
            "last4": "4242",
            "network": network,
            "type": "debit" if amount_inr < 5000 else "credit",
            "issuer": through,
            "international": False,
            "emi": False,
            "sub_type": "consumer"
        }

    err_code = "BAD_REQUEST_ERROR" if decline_type == "hard" else "GATEWAY_ERROR"
    err_source = "bank" if through else "customer"
    err_step = "payment_authentication" if "3DS" in failure_reason or "OTP" in failure_reason else "payment_authorization"
    err_reason = failure_reason.lower().replace(" ", "_")[:30]

    payment_entity = {
        "id": pay_id,
        "entity": "payment",
        "amount": amount_paisa,
        "currency": "INR",
        "status": "failed",
        "order_id": order_id,
        "invoice_id": None,
        "international": False,
        "method": method,
        "amount_refunded": 0,
        "refund_status": None,
        "captured": False,
        "description": scen.get("title", "Renvue Order"),
        "card_id": card_id if method == "card" else None,
        "card": card_entity,
        "bank": through if method in ["netbanking", "card"] else None,
        "wallet": through if method == "wallet" else None,
        "vpa": f"{cust_name.lower().replace(' ', '')}@ok{(through or 'axis').lower()}" if method == "upi" else None,
        "email": cust_email,
        "contact": f"+91{cust_phone}",
        "customer_id": f"cust_{suffix[:12]}",
        "notes": {
            "scenario_id": scen_id,
            "category": scen.get("category", "General"),
            "language": scen.get("language", "english")
        },
        "fee": None,
        "tax": None,
        "error_code": err_code,
        "error_description": failure_reason,
        "error_source": err_source,
        "error_step": err_step,
        "error_reason": err_reason,
        "acquirer_data": acquirer_data,
        "created_at": created_at
    }

    webhook_payload = {
        "entity": "event",
        "account_id": "acc_RenvueLiveDemo2026",
        "event": scen.get("event_type", "payment.failed"),
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": payment_entity
            }
        },
        "created_at": created_at
    }

    if "subscription" in scen.get("case_type", ""):
        webhook_payload["contains"] = ["subscription", "payment"]
        webhook_payload["payload"]["subscription"] = {
            "entity": {
                "id": f"sub_{suffix}",
                "customer_id": f"cust_{suffix[:12]}",
                "status": "halted" if "cancel" not in scen.get("case_type", "") else "cancelled",
                "plan_id": f"plan_{suffix[:8]}",
                "total_count": 12,
                "paid_count": 1,
                "remaining_count": 11,
                "notes": {
                    "customer_name": cust_name,
                    "customer_email": cust_email,
                    "customer_contact": cust_phone,
                    "language": scen.get("language", "english")
                }
            }
        }

    if "invoice" in scen.get("case_type", ""):
        webhook_payload["contains"] = ["invoice"]
        webhook_payload["payload"]["invoice"] = {
            "entity": {
                "id": f"inv_{suffix}",
                "amount": amount_paisa,
                "amount_paid": 0,
                "amount_due": amount_paisa,
                "currency": "INR",
                "status": "expired",
                "order_id": order_id,
                "customer_details": {
                    "name": cust_name,
                    "email": cust_email,
                    "contact": cust_phone
                }
            }
        }

    return webhook_payload
