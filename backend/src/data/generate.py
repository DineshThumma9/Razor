"""
Razorpay Sample Data Generator
================================
Generates realistic test data across all 4 revenue-at-risk categories:

  1. Failed payments          → payment.failed events
  2. Abandoned checkouts      → orders with no captured payment
  3. Halted subscriptions     → subscription in 'halted' state
  4. Overdue invoices         → invoices past due date

Run:
    uv run python -m backend.data.generate

Requires:
    .env with RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET (test mode keys)
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import razorpay
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from config import Settings 

settings = Settings()
client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

# --- Rate Limiter Fix ---
original_request = client.request
def retrying_request(method, path, **options):
    for attempt in range(10):
        try:
            return original_request(method, path, **options)
        except razorpay.errors.BadRequestError as e:
            if "Too many requests" in str(e) or "Too Many Requests" in str(e):
                log(f"  [Rate Limit] Hit Razorpay throttle. Sleeping {2 * (attempt + 1)}s...")
                time.sleep(2 * (attempt + 1))
            else:
                raise e
    raise Exception("Razorpay rate limit retries exhausted!")
client.request = retrying_request
# ------------------------

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import requests

WEBHOOK_URL = "http://localhost:8000/listen-events"

def trigger_webhook(payload: dict):
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        log(f"  → Webhook fired! Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log(f"  [Warning] Failed to trigger webhook: {e}")

CUSTOMERS = [
    {"name": "Dinesh Thumma", "email": "dineshthumma15@gmail.com", "contact": "9393519918"},
    {"name": "Duct Dynamic", "email": "ductdynamic73@gmail.com", "contact": "9393519918"},
    {"name": "Duct Dynamic 07", "email": "ductdynamic07@gmail.com", "contact": "9393519918"},
    {"name": "Duct Dynamic 99", "email": "ductdynamic99@gmail.com", "contact": "9393519918"},
    {"name": "Dinesh Thumma 0", "email": "dineshthumma0@gmail.com", "contact": "9393519918"},
    {"name": "Student", "email": "23B81A7217@cvr.ac.in", "contact": "9393519918"},
]

AMOUNTS_INR = [49900, 99900, 199900, 499900, 999900]  # paise


def rand_customer() -> dict:
    return random.choice(CUSTOMERS)


def rand_amount() -> int:
    return random.choice(AMOUNTS_INR)


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ---------------------------------------------------------------------------
# 1. Failed Payments
# ---------------------------------------------------------------------------


def generate_failed_payments(n: int = 5) -> list[dict]:
    """
    Create orders then attempt payment with a card that Razorpay test mode
    treats as failed (e.g. error code BAD_REQUEST_ERROR).

    NOTE: In test mode, you cannot programmatically trigger payment.failed
    directly via the API — payments must go through the checkout flow.
    We create orders and mark them as 'abandoned_payment_attempt' in our
    local records to simulate this, since Razorpay doesn't expose a way to
    force-fail via server-to-server API.
    """
    log(f"Generating {n} failed payment records...")
    records = []

    for i in range(n):
        time.sleep(2)
        customer = rand_customer()
        amount = rand_amount()

        # Check if we are forcing a Voice Note test case
        import sys
        is_voice_test = "--test-voice-whatsapp" in sys.argv

        failure_reason = "Card expired" if is_voice_test else random.choice(
            [
                "Insufficient funds",
                "Card declined by issuer",
                "3DS authentication failed",
                "Invalid CVV",
                "Card expired",
            ]
        )

        # Mock an order (represents a payment attempt that never completed)
        order = {
            "id": f"order_mock_{int(time.time())}_{i}",
            "amount": amount,
            "currency": "INR",
            "receipt": f"rcpt_fail_{i}_{int(time.time())}",
            "notes": {
                "customer_name": customer["name"],
                "customer_email": customer["email"],
                "scenario": "failed_payment",
                "failure_reason": failure_reason,
            },
        }

        records.append(
            {
                "type": "failed_payment",
                "order_id": order["id"],
                "amount_paise": amount,
                "amount_inr": amount / 100,
                "currency": "INR",
                "customer": customer,
                "failure_reason": order["notes"]["failure_reason"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "payment_failed",
                "recovery_status": "pending",
            }
        )
        log(
            f"  ✓ Failed payment [{i+1}/{n}]: {order['id']} | ₹{amount/100:.0f} | {customer['name']}"
        )

        webhook_payload = {
            "entity": "event",
            "account_id": "acc_TestMode",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_fail_{int(time.time())}_{i}",
                        "entity": "payment",
                        "amount": amount,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": order["id"],
                        "email": customer["email"],
                        "contact": customer["contact"],
                        "error_description": order["notes"]["failure_reason"],
                        "created_at": int(time.time()),
                    }
                }
            },
            "created_at": int(time.time())
        }
        trigger_webhook(webhook_payload)

    return records


# ---------------------------------------------------------------------------
# 2. Abandoned Checkouts (order created, no payment)
# ---------------------------------------------------------------------------


def generate_abandoned_checkouts(n: int = 5) -> list[dict]:
    """
    Create orders with no subsequent payment — simulates users who reached
    checkout but dropped off before paying.
    """
    log(f"Generating {n} abandoned checkout records...")
    records = []

    for i in range(n):
        time.sleep(1.5)
        customer = rand_customer()
        amount = rand_amount()

        # Instead of an order, let's create a mock payment link to simulate abandoned checkout
        # (This bypasses the absolute limit of 30 payment links in Razorpay Test Mode)
        link = {
            "id": f"plink_mock_{int(time.time())}_{i}",
            "amount": amount,
            "currency": "INR",
            "description": f"Checkout for {customer['name']}",
            "customer": {
                "name": customer["name"],
                "email": customer["email"],
                "contact": customer["contact"],
            },
            "notes": {
                "scenario": "checkout_abandoned",
                "drop_step": random.choice(
                    [
                        "payment_method_selection",
                        "card_details_entry",
                        "otp_verification",
                        "address_confirmation",
                    ]
                ),
            },
        }

        records.append(
            {
                "type": "abandoned_checkout",
                "payment_link_id": link["id"],
                "amount_paise": amount,
                "amount_inr": amount / 100,
                "currency": "INR",
                "customer": customer,
                "drop_step": link["notes"]["drop_step"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "expired",
                "recovery_status": "pending",
            }
        )
        log(
            f"  ✓ Abandoned checkout [{i+1}/{n}]: {link['id']} | ₹{amount/100:.0f} | dropped at: {link['notes']['drop_step']}"
        )

        webhook_payload = {
            "entity": "event",
            "account_id": "acc_TestMode",
            "event": "payment_link.expired",
            "contains": ["payment_link"],
            "payload": {
                "payment_link": {
                    "entity": link
                }
            },
            "created_at": int(time.time())
        }
        trigger_webhook(webhook_payload)

    return records


# ---------------------------------------------------------------------------
# 3. Halted Subscriptions
# ---------------------------------------------------------------------------


def generate_failed_subscriptions(n: int = 3) -> list[dict]:
    """
    Create subscriptions using a test plan. Razorpay subscriptions in test
    mode start in 'created' state. We record them as halted in our local
    store to simulate revenue at risk from subscription churn.

    Note: To create a real subscription, a plan must first exist. We create
    a plan here dynamically.
    """
    log(f"Generating {n} failed subscription records...")
    records = []

    # Mock a test plan once
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
    log(f"  → Created plan: {plan['id']}")

    for i in range(n):
        time.sleep(3)
        customer = rand_customer()
        # future start so Razorpay accepts it
        start_at = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        
        # Mock subscription
        sub = {
            "id": f"sub_mock_{int(time.time())}_{i}",
            "plan_id": plan["id"],
            "total_count": 12,
            "customer_notify": 1,
            "start_at": start_at,
            "customer_details": {
                "name": customer["name"],
                "email": customer["email"],
                "contact": customer["contact"],
            },
            "notes": {
                "customer_name": customer["name"],
                "customer_email": customer["email"],
                "customer_contact": customer["contact"],
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

        records.append(
            {
                "type": "failed_subscription",
                "subscription_id": sub["id"],
                "plan_id": plan["id"],
                "amount_paise": 99900,
                "amount_inr": 999.00,
                "currency": "INR",
                "customer": customer,
                "halt_reason": sub["notes"]["halt_reason"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "halted",
                "recovery_status": "pending",
            }
        )
        log(f"  ✓ Failed subscription [{i+1}/{n}]: {sub['id']} | {customer['name']}")

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
        trigger_webhook(webhook_payload)

    return records


# ---------------------------------------------------------------------------
# 4. Overdue Invoices (B2B)
# ---------------------------------------------------------------------------


def generate_overdue_invoices(n: int = 4) -> list[dict]:
    """
    Create draft invoices with past due dates to simulate B2B overdue
    receivables. Razorpay invoices can be created with a due_by timestamp.
    """
    log(f"Generating {n} overdue invoice records...")
    records = []

    for i in range(n):
        time.sleep(1.5)
        customer = rand_customer()
        amount = rand_amount()
        days_overdue = random.randint(7, 60)
        due_by = int(
            (datetime.now(timezone.utc) - timedelta(days=days_overdue)).timestamp()
        )

        # Mock customer
        rzp_cust = {
            "id": f"cust_mock_{int(time.time())}_{i}",
            "name": customer["name"],
            "email": customer["email"],
            "contact": customer["contact"],
        }
        
        # Mock invoice
        inv = {
            "id": f"inv_mock_{int(time.time())}_{i}",
            "type": "invoice",
            "description": f"Monthly billing for {customer['name']}",
            "customer_id": rzp_cust["id"],
            "amount": amount,
            "currency": "INR",
            "date": int(time.time()),
            "customer_details": {
                "customer_name": customer["name"],
                "customer_email": customer["email"],
                "customer_contact": customer["contact"],
            },
            "line_items": [
                {
                    "name": "Software License",
                    "description": "Monthly API access",
                    "amount": amount,
                    "currency": "INR",
                    "quantity": 1,
                }
            ],
            "notes": {
                "scenario": "overdue_invoice",
                "days_overdue": days_overdue,
            },
        }

        records.append(
            {
                "type": "overdue_invoice",
                "invoice_id": inv["id"],
                "invoice_number": f"INV-{1000 + i}",
                "amount_paise": amount,
                "amount_inr": amount / 100,
                "currency": "INR",
                "customer": customer,
                "days_overdue": days_overdue,
                "due_by": datetime.fromtimestamp(due_by, tz=timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "overdue",
                "recovery_status": "pending",
            }
        )
        log(
            f"  ✓ Overdue invoice [{i+1}/{n}]: {inv['id']} | ₹{amount/100:.0f} | {days_overdue}d overdue"
        )

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
        trigger_webhook(webhook_payload)

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


import argparse

def main():
    parser = argparse.ArgumentParser(description="Generate mock Renvue cases.")
    parser.add_argument("--payment", type=int, default=0, help="Number of failed payments to generate")
    parser.add_argument("--checkout", type=int, default=0, help="Number of abandoned checkouts to generate")
    parser.add_argument("--subscription", type=int, default=0, help="Number of failed subscriptions to generate")
    parser.add_argument("--invoice", type=int, default=0, help="Number of overdue invoices to generate")
    parser.add_argument("--test-voice-whatsapp", action="store_true", help="Generate a single failed payment with amount > ₹5000 to trigger WhatsApp and Voice Note")
    parser.add_argument("--all", action="store_true", help="Generate all cases (the original 17 cases)")
    
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Renvue — Razorpay Sample Data Generator")
    print("=" * 60 + "\n")

    all_cases = []
    
    if args.all:
        args.payment = 5
        args.checkout = 5
        args.subscription = 3
        args.invoice = 4

    if args.payment == 0 and args.checkout == 0 and args.subscription == 0 and args.invoice == 0 and not args.test_voice_whatsapp:
        print("No cases generated! Please use flags like --payment 2, --test-voice-whatsapp, or --all.")
        return

    if args.test_voice_whatsapp:
        # Override random amount globally for this single test case
        global AMOUNTS_INR
        AMOUNTS_INR = [999900]
        args.payment = 1

    if args.payment > 0:
        all_cases.extend(generate_failed_payments(n=args.payment))
        time.sleep(2)
    if args.checkout > 0:
        all_cases.extend(generate_abandoned_checkouts(n=args.checkout))
        time.sleep(2)
    if args.subscription > 0:
        all_cases.extend(generate_failed_subscriptions(n=args.subscription))
        time.sleep(2)
    if args.invoice > 0:
        all_cases.extend(generate_overdue_invoices(n=args.invoice))

    output_file = OUTPUT_DIR / "sample_cases.json"
    with open(output_file, "w") as f:
        json.dump(all_cases, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  ✅ Generated {len(all_cases)} cases → {output_file}")
    print(f"{'='*60}\n")

    # Summary
    by_type = {}
    for case in all_cases:
        by_type.setdefault(case["type"], []).append(case)

    for t, cases in by_type.items():
        total = sum(c["amount_inr"] for c in cases)
        print(f"  {t:30s}  {len(cases):>2} cases  ₹{total:>10,.2f} at risk")

    print()


if __name__ == "__main__":
    main()
