import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

import os
WEBHOOK_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/") + "/listen-events"

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def trigger_webhook(payload: dict):
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        log(f"  → Webhook fired! {payload['event']} | Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log(f"  [Warning] Failed to trigger webhook: {e}")

CUSTOMERS = [
    {"name": "Dinesh Thumma", "email": "dineshthumma15@gmail.com", "contact": "+919393519918"},
    {"name": "Duct Dynamic", "email": "ductdynamic73@gmail.com", "contact": "+919393519918"},
    {"name": "Duct Dynamic 07", "email": "ductdynamic07@gmail.com", "contact": "+919393519918"},
    {"name": "Duct Dynamic 99", "email": "ductdynamic99@gmail.com", "contact": "+919393519918"},
    {"name": "Student", "email": "23B81A7217@cvr.ac.in", "contact": "+919393519918"},
]

AMOUNTS_INR = [49900, 99900, 199900, 499900, 999900]  # paise

def rand_customer() -> dict:
    return random.choice(CUSTOMERS)

def rand_amount() -> int:
    return random.choice(AMOUNTS_INR)

def generate_pending_case(i: int):
    """Simulates a fresh failed payment that remains pending."""
    customer = rand_customer()
    amount = rand_amount()
    order_id = f"order_demo_{int(time.time())}_{i}"
    payment_id = f"pay_fail_{int(time.time())}_{i}"

    log(f"Generating PENDING case... (₹{amount/100:.0f}) for {customer['name']}")
    
    payload = {
        "entity": "event",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": order_id,
                    "email": customer["email"],
                    "contact": customer["contact"],
                    "error_description": "Insufficient funds",
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time())
    }
    trigger_webhook(payload)


def generate_recovered_case(i: int):
    """Simulates a failed payment that is successfully recovered moments later."""
    customer = rand_customer()
    amount = rand_amount()
    order_id = f"order_demo_rec_{int(time.time())}_{i}"
    payment_id = f"pay_fail_rec_{int(time.time())}_{i}"

    log(f"Generating RECOVERED case... (₹{amount/100:.0f}) for {customer['name']}")
    
    # 1. Fail the payment
    fail_payload = {
        "entity": "event",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": order_id,
                    "email": customer["email"],
                    "contact": customer["contact"],
                    "error_description": "Card expired",
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time())
    }
    trigger_webhook(fail_payload)
    
    # Wait for the backend to process the initial failure
    time.sleep(3)
    
    # 2. Simulate the AI outreach worked, and the payment is captured
    capture_payload = {
        "entity": "event",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_succ_{int(time.time())}_{i}", # new payment ID for success
                    "amount": amount,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": order_id, # Matches the same order!
                    "email": customer["email"],
                    "contact": customer["contact"],
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time())
    }
    log(f"  Simulating successful recovery capture for {order_id}...")
    trigger_webhook(capture_payload)


def generate_escalated_case(i: int):
    """Simulates a failed payment that results in a customer dispute (Escalated)."""
    customer = rand_customer()
    amount = rand_amount()
    order_id = f"order_demo_esc_{int(time.time())}_{i}"
    payment_id = f"pay_fail_esc_{int(time.time())}_{i}"

    log(f"Generating ESCALATED case... (₹{amount/100:.0f}) for {customer['name']}")
    
    # 1. Fail the payment
    fail_payload = {
        "entity": "event",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": order_id,
                    "email": customer["email"],
                    "contact": customer["contact"],
                    "error_description": "Suspected Fraud",
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time())
    }
    trigger_webhook(fail_payload)
    
    time.sleep(3)
    
    # 2. Customer files a dispute
    dispute_payload = {
        "entity": "event",
        "event": "payment.dispute.created",
        "contains": ["dispute"],
        "payload": {
            "dispute": {
                "entity": {
                    "id": f"disp_{int(time.time())}_{i}",
                    "payment_id": payment_id,
                    "amount": amount,
                    "currency": "INR",
                    "status": "open",
                    "reason_code": "fraudulent",
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time())
    }
    log(f"  Simulating customer dispute for {payment_id}...")
    trigger_webhook(dispute_payload)


def generate_partial_payment_case(i: int):
    """Simulates an overdue invoice that receives a partial payment."""
    customer = rand_customer()
    amount = rand_amount()
    invoice_id = f"inv_demo_part_{int(time.time())}_{i}"
    
    log(f"Generating PARTIAL PAYMENT case... (₹{amount/100:.0f}) for {customer['name']}")
    
    # 1. Expire the invoice
    inv_payload = {
        "entity": "event",
        "event": "invoice.expired",
        "contains": ["invoice"],
        "payload": {
            "invoice": {
                "entity": {
                    "id": invoice_id,
                    "amount": amount,
                    "currency": "INR",
                    "status": "expired",
                    "order_id": f"order_inv_{int(time.time())}_{i}",
                    "customer_details": {
                        "name": customer["name"],
                        "email": customer["email"],
                        "contact": customer["contact"],
                    },
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time())
    }
    trigger_webhook(inv_payload)
    
    time.sleep(3)
    
    # 2. Receive a partial payment (e.g. 50%)
    partial_amount = int(amount * 0.5)
    partial_payload = {
        "entity": "event",
        "event": "invoice.partially_paid",
        "contains": ["invoice", "payment"],
        "payload": {
            "invoice": {
                "entity": {
                    "id": invoice_id,
                    "amount": amount,
                    "amount_paid": partial_amount,
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_part_{int(time.time())}_{i}",
                    "amount": partial_amount,
                    "order_id": inv_payload["payload"]["invoice"]["entity"]["order_id"],
                }
            }
        },
        "created_at": int(time.time())
    }
    log(f"  Simulating partial payment of ₹{partial_amount/100:.0f} for {invoice_id}...")
    trigger_webhook(partial_payload)


def main():
    print("\n" + "=" * 60)
    print("  Renvue — Lifecycle Demo Simulator")
    print("=" * 60 + "\n")
    
    # Generate a mix of 8 cases to populate the dashboard with realistic variance
    
    # 3 Pending cases (Brand new failures)
    for i in range(3):
        generate_pending_case(i)
        time.sleep(2)
        
    # 2 Recovered cases (AI succeeded!)
    for i in range(2):
        generate_recovered_case(i)
        time.sleep(2)
        
    # 2 Partially paid cases (Customer negotiated/paid an installment)
    for i in range(2):
        generate_partial_payment_case(i)
        time.sleep(2)
        
    # 1 Escalated case (Customer was angry or disputed)
    generate_escalated_case(0)
    
    print("\n" + "=" * 60)
    print("  ✅ Dashboard Demo Simulation Complete")
    print("     Check your frontend dashboard to see the mixed states!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
