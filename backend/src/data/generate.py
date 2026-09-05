"""
Renvue — Unified Razorpay Case Generator & Live Demo Simulator
==============================================================
Consolidates synthetic dataset generation and real-time dashboard simulation
into a single, high-fidelity tool.

Modes:
  1. Live Demo Simulation (default / --demo):
     Fires an interactive, realistic sequence of 7 cases across all 4 recovery
     categories, state transitions (recovered, partially paid, escalated dispute),
     and displays real-time updates on the frontend dashboard.

  2. Custom CLI Generation:
     Generates arbitrary counts of test events and optionally exports to JSON:
     uv run python src/data/generate.py --payment 3 --checkout 2 --subscription 2 --invoice 2
     uv run python src/data/generate.py --all
     uv run python src/data/generate.py --no-webhook   (export sample_cases.json only)

Features:
  - Authentic Razorpay 2026 banking payloads (card networks, acquirer RRN, error diagnostics)
  - Automatic HMAC-SHA256 signature generation (X-Razorpay-Signature)
  - Zero-config sys.path bootstrapping
"""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

# Path configuration & sys.path bootstrapping
DATA_DIR = Path(__file__).resolve().parent
BACKEND_SRC = DATA_DIR.parent
BACKEND_DIR = BACKEND_SRC.parent

for p in [str(BACKEND_SRC), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import requests
from config.config import settings

# Output directory for exported datasets
DATA_EXPORT_DIR = BACKEND_DIR / "data"
DATA_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Authentic Indian Customer Profiles & Telemetry
# ---------------------------------------------------------------------------

CUSTOMERS = [
    {"name": "Dinesh Thumma", "email": "dineshthumma15@gmail.com", "contact": "+919393519918"},
    {"name": "Ananya Sharma", "email": "ananya.sharma@example.in", "contact": "+919876543210"},
    {"name": "Rahul Verma", "email": "rahul.verma@example.in", "contact": "+919811223344"},
    {"name": "Vikram Malhotra", "email": "vikram.m@innovatecorp.in", "contact": "+919820011223"},
    {"name": "Priya Nair", "email": "priya.nair@example.com", "contact": "+919745123456"},
    {"name": "Arjun Patel", "email": "arjun.p@quicklogistics.in", "contact": "+919898012345"},
]

AMOUNTS_INR = [49900, 99900, 199900, 249900, 499900, 999900, 1500000]  # in paise


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def rand_customer() -> dict:
    return random.choice(CUSTOMERS)


def rand_amount() -> int:
    return random.choice(AMOUNTS_INR)


# ---------------------------------------------------------------------------
# Webhook Dispatcher with HMAC Signature
# ---------------------------------------------------------------------------

def trigger_webhook(payload: dict, url: Optional[str] = None) -> bool:
    port = getattr(settings, "port", 8000)
    target_url = url or f"http://localhost:{port}/listen-events"
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    # Compute authentic Razorpay webhook signature if secret configured
    secret = getattr(settings, "razorpay_webhook_secret", None)
    if secret:
        signature = hmac.new(
            secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        headers["X-Razorpay-Signature"] = signature

    try:
        response = requests.post(target_url, data=body_bytes, headers=headers, timeout=5)
        evt = payload.get("event", "unknown")
        if response.status_code in [200, 202]:
            log(f"  → Webhook fired: {evt:<28} | HTTP {response.status_code} OK")
            return True
        else:
            log(f"  [Warning] Webhook {evt}: HTTP {response.status_code} - {response.text[:80]}")
            return False
    except requests.exceptions.RequestException as e:
        log(f"  [Warning] Server unreachable at {target_url}: {e}")
        return False


# ---------------------------------------------------------------------------
# High-Fidelity Event Generators
# ---------------------------------------------------------------------------

def build_failed_payment(
    customer: dict,
    amount_paise: int,
    order_id: Optional[str] = None,
    failure_reason: str = "Insufficient funds",
    card_issuer: str = "HDFC",
) -> tuple[dict, dict]:
    """Builds a high-fidelity payment.failed event payload."""
    suffix = uuid.uuid4().hex[:8]
    oid = order_id or f"order_gen_{int(time.time())}_{suffix}"
    pid = f"pay_fail_{int(time.time())}_{suffix}"
    rrn = str(random.randint(100000000000, 999999999999))
    bank_txn_id = str(random.randint(10000000, 99999999))

    is_hard = failure_reason in ["Card expired", "Suspected Fraud", "Invalid card details"]
    err_code = "BAD_REQUEST_ERROR" if is_hard else "GATEWAY_ERROR"

    payment_entity = {
        "id": pid,
        "entity": "payment",
        "amount": amount_paise,
        "currency": "INR",
        "status": "failed",
        "order_id": oid,
        "invoice_id": None,
        "international": False,
        "method": "card",
        "amount_refunded": 0,
        "refund_status": None,
        "captured": False,
        "description": f"Checkout for {customer['name']}",
        "card_id": f"card_{suffix}",
        "card": {
            "id": f"card_{suffix}",
            "entity": "card",
            "name": customer["name"],
            "last4": "4242",
            "network": "Visa" if "HDFC" in card_issuer else "RuPay",
            "type": "debit" if amount_paise < 500000 else "credit",
            "issuer": card_issuer,
            "international": False,
            "emi": False,
            "sub_type": "consumer",
        },
        "bank": card_issuer,
        "wallet": None,
        "vpa": None,
        "email": customer["email"],
        "contact": customer["contact"],
        "customer_id": f"cust_{suffix}",
        "notes": {
            "scenario": "failed_payment",
            "failure_reason": failure_reason,
        },
        "fee": None,
        "tax": None,
        "error_code": err_code,
        "error_description": failure_reason,
        "error_source": "bank",
        "error_step": "payment_authorization",
        "error_reason": failure_reason.lower().replace(" ", "_"),
        "acquirer_data": {
            "bank_transaction_id": bank_txn_id,
            "rrn": rrn,
            "auth_code": None,
        },
        "created_at": int(time.time()),
    }

    payload = {
        "entity": "event",
        "account_id": "acc_RenvueSimulator",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {"payment": {"entity": payment_entity}},
        "created_at": int(time.time()),
    }

    record = {
        "type": "failed_payment",
        "order_id": oid,
        "payment_id": pid,
        "amount_inr": amount_paise / 100,
        "customer": customer,
        "failure_reason": failure_reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "payment_failed",
    }

    return payload, record


def build_abandoned_checkout(customer: dict, amount_paise: int) -> tuple[dict, dict]:
    """Builds a payment_link.expired event for abandoned checkouts."""
    suffix = uuid.uuid4().hex[:8]
    plink_id = f"plink_gen_{int(time.time())}_{suffix}"

    link_entity = {
        "id": plink_id,
        "amount": amount_paise,
        "currency": "INR",
        "description": f"Checkout for {customer['name']}",
        "customer": {
            "name": customer["name"],
            "email": customer["email"],
            "contact": customer["contact"],
        },
        "notes": {
            "scenario": "checkout_abandoned",
            "drop_step": random.choice(["otp_verification", "payment_method_selection"]),
        },
        "created_at": int(time.time()),
    }

    payload = {
        "entity": "event",
        "account_id": "acc_RenvueSimulator",
        "event": "payment_link.expired",
        "contains": ["payment_link"],
        "payload": {"payment_link": {"entity": link_entity}},
        "created_at": int(time.time()),
    }

    record = {
        "type": "abandoned_checkout",
        "payment_link_id": plink_id,
        "amount_inr": amount_paise / 100,
        "customer": customer,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "expired",
    }

    return payload, record


def build_subscription_halted(
    customer: dict, amount_paise: int = 249900
) -> tuple[dict, dict]:
    """Builds a subscription.halted event (Recurring Mandate)."""
    suffix = uuid.uuid4().hex[:8]
    sub_id = f"sub_gen_{int(time.time())}_{suffix}"
    plan_id = f"plan_pro_{suffix[:6]}"

    sub_entity = {
        "id": sub_id,
        "plan_id": plan_id,
        "total_count": 12,
        "customer_notify": 1,
        "start_at": int(time.time()) + 3600,
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
            "halt_reason": "Payment method expired",
        },
    }

    payload = {
        "entity": "event",
        "account_id": "acc_RenvueSimulator",
        "event": "subscription.halted",
        "contains": ["subscription"],
        "payload": {"subscription": {"entity": sub_entity}},
        "created_at": int(time.time()),
    }

    record = {
        "type": "failed_subscription",
        "subscription_id": sub_id,
        "amount_inr": amount_paise / 100,
        "customer": customer,
        "halt_reason": sub_entity["notes"]["halt_reason"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "halted",
    }

    return payload, record


def build_overdue_invoice(
    customer: dict, amount_paise: int, days_overdue: int = 30
) -> tuple[dict, dict]:
    """Builds an invoice.expired event (B2B Receivables)."""
    suffix = uuid.uuid4().hex[:8]
    inv_id = f"inv_gen_{int(time.time())}_{suffix}"

    inv_entity = {
        "id": inv_id,
        "type": "invoice",
        "description": f"Net-30 Enterprise Services for {customer['name']}",
        "customer_id": f"cust_{suffix}",
        "amount": amount_paise,
        "currency": "INR",
        "date": int(time.time()) - (days_overdue * 86400),
        "customer_details": {
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "customer_contact": customer["contact"],
        },
        "line_items": [
            {
                "name": "Platform Access & API Licensing",
                "amount": amount_paise,
                "quantity": 1,
            }
        ],
        "notes": {
            "scenario": "overdue_invoice",
            "days_overdue": days_overdue,
        },
    }

    payload = {
        "entity": "event",
        "account_id": "acc_RenvueSimulator",
        "event": "invoice.expired",
        "contains": ["invoice"],
        "payload": {"invoice": {"entity": inv_entity}},
        "created_at": int(time.time()),
    }

    record = {
        "type": "overdue_invoice",
        "invoice_id": inv_id,
        "amount_inr": amount_paise / 100,
        "customer": customer,
        "days_overdue": days_overdue,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "overdue",
    }

    return payload, record


# ---------------------------------------------------------------------------
# Interactive Live Demo Simulator
# ---------------------------------------------------------------------------

def run_demo_simulation(url: Optional[str] = None, delay: float = 2.0):
    """
    Executes a cinematic sequence of 7 scenarios to populate the live dashboard
    with rich variance: pending, recovered, concessions, subscriptions, and disputes.
    """
    print("\n" + "=" * 65)
    print("  Renvue — Live Dashboard Demo Simulation")
    print("=" * 65 + "\n")

    cases_summary = []

    # 1. Soft Decline Pending (₹1,999 — Insufficient funds)
    log("1/7: Simulating Soft Decline (₹1,999 — Insufficient funds)...")
    cust1 = CUSTOMERS[0]
    p1, r1 = build_failed_payment(cust1, 199900, failure_reason="Insufficient funds")
    trigger_webhook(p1, url)
    cases_summary.append(r1)
    time.sleep(delay)

    # 2. Hard Decline Recovered (₹4,999 — Card expired → AI outreach → Captured)
    log("2/7: Simulating Recovered Payment (₹4,999 — Card expired → Captured)...")
    cust2 = CUSTOMERS[1]
    p2, r2 = build_failed_payment(cust2, 499900, failure_reason="Card expired")
    trigger_webhook(p2, url)
    time.sleep(delay)
    # Simulate capture
    cap_payload = {
        "entity": "event",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_succ_{int(time.time())}",
                    "amount": 499900,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": r2["order_id"],
                    "email": cust2["email"],
                    "contact": cust2["contact"],
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time()),
    }
    log(f"  → Resolving {r2['order_id']} via recovery capture...")
    trigger_webhook(cap_payload, url)
    r2["status"] = "recovered"
    cases_summary.append(r2)
    time.sleep(delay)

    # 3. Abandoned Checkout (₹5,000 — Bell-Curve Concession Offer)
    log("3/7: Simulating Abandoned Checkout (₹5,000 — OTP Drop-off)...")
    cust3 = CUSTOMERS[2]
    p3, r3 = build_abandoned_checkout(cust3, 500000)
    trigger_webhook(p3, url)
    cases_summary.append(r3)
    time.sleep(delay)

    # 4. Recurring Mandate Halted (₹2,499 — RBI 24h pre-debit & re-auth)
    log("4/7: Simulating Recurring Subscription Mandate Halted (₹2,499)...")
    cust4 = CUSTOMERS[3]
    p4, r4 = build_subscription_halted(cust4, 249900)
    trigger_webhook(p4, url)
    cases_summary.append(r4)
    time.sleep(delay)

    # 5. Overdue B2B Invoice (₹9,999 — Net-30 overdue dunning)
    log("5/7: Simulating Overdue B2B Invoice (₹9,999 — Net-30 terms)...")
    cust5 = CUSTOMERS[4]
    p5, r5 = build_overdue_invoice(cust5, 999900, days_overdue=32)
    trigger_webhook(p5, url)
    cases_summary.append(r5)
    time.sleep(delay)

    # 6. Invoice Partial Payment (₹15,000 — 50% cleared)
    log("6/7: Simulating Invoice Partial Payment (₹15,000 invoice → ₹7,500 paid)...")
    cust6 = CUSTOMERS[5]
    p6, r6 = build_overdue_invoice(cust6, 1500000, days_overdue=14)
    trigger_webhook(p6, url)
    time.sleep(delay)
    part_payload = {
        "entity": "event",
        "event": "invoice.partially_paid",
        "contains": ["invoice", "payment"],
        "payload": {
            "invoice": {
                "entity": {
                    "id": r6["invoice_id"],
                    "amount": 1500000,
                    "amount_paid": 750000,
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_part_{int(time.time())}",
                    "amount": 750000,
                    "order_id": f"order_{r6['invoice_id']}",
                }
            },
        },
        "created_at": int(time.time()),
    }
    log(f"  → Applying partial payment of ₹7,500 to {r6['invoice_id']}...")
    trigger_webhook(part_payload, url)
    r6["status"] = "partially_paid"
    cases_summary.append(r6)
    time.sleep(delay)

    # 7. Escalated Dispute Kill-Switch (₹9,999 — Customer disputes fraud)
    log("7/7: Simulating Customer Dispute (₹9,999 — Escalation & freeze)...")
    p7, r7 = build_failed_payment(cust1, 999900, failure_reason="Suspected Fraud")
    trigger_webhook(p7, url)
    time.sleep(delay)
    disp_payload = {
        "entity": "event",
        "event": "payment.dispute.created",
        "contains": ["dispute"],
        "payload": {
            "dispute": {
                "entity": {
                    "id": f"disp_{int(time.time())}",
                    "payment_id": r7["payment_id"],
                    "amount": 999900,
                    "currency": "INR",
                    "status": "open",
                    "reason_code": "fraudulent",
                    "created_at": int(time.time()),
                }
            }
        },
        "created_at": int(time.time()),
    }
    log(f"  → Customer dispute created on {r7['payment_id']}...")
    trigger_webhook(disp_payload, url)
    r7["status"] = "escalated"
    cases_summary.append(r7)

    # Export dataset snapshot
    export_path = DATA_EXPORT_DIR / "sample_cases.json"
    with open(export_path, "w") as f:
        json.dump(cases_summary, f, indent=2)

    print("\n" + "=" * 65)
    print("  ✅ Live Demo Simulation Complete!")
    print(f"     Cases Dispatched : {len(cases_summary)}")
    print(f"     Dataset Exported : {export_path}")
    print("     Check your frontend dashboard to see all states live.")
    print("=" * 65 + "\n")


# ---------------------------------------------------------------------------
# CLI Argument Parsing & Batch Ingestion
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Renvue — Unified Razorpay Case Generator & Live Demo Simulator"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run interactive live demo simulation"
    )
    parser.add_argument(
        "--payment", type=int, default=0, help="Number of failed payments to generate"
    )
    parser.add_argument(
        "--checkout",
        type=int,
        default=0,
        help="Number of abandoned checkouts to generate",
    )
    parser.add_argument(
        "--subscription",
        type=int,
        default=0,
        help="Number of failed subscriptions to generate",
    )
    parser.add_argument(
        "--invoice", type=int, default=0, help="Number of overdue invoices to generate"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate standard batch (5 payments, 5 checkouts, 3 subs, 4 invoices)",
    )
    parser.add_argument(
        "--no-webhook",
        action="store_true",
        help="Skip firing webhooks, only export sample_cases.json",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Custom webhook URL (default: http://localhost:8000/listen-events)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay in seconds between webhook dispatches (default: 1.5)",
    )

    args = parser.parse_args()

    # Default to interactive demo simulation if no specific flags provided
    no_args = (
        not args.demo
        and not args.all
        and args.payment == 0
        and args.checkout == 0
        and args.subscription == 0
        and args.invoice == 0
    )

    if args.demo or no_args:
        run_demo_simulation(url=args.url, delay=args.delay)
        return

    if args.all:
        args.payment = 5
        args.checkout = 5
        args.subscription = 3
        args.invoice = 4

    print("\n" + "=" * 65)
    print("  Renvue — Razorpay Batch Case Generator")
    print("=" * 65 + "\n")

    records = []

    # Generate failed payments
    for i in range(args.payment):
        cust = rand_customer()
        amt = rand_amount()
        payload, rec = build_failed_payment(cust, amt)
        records.append(rec)
        if not args.no_webhook:
            trigger_webhook(payload, args.url)
            time.sleep(args.delay)

    # Generate abandoned checkouts
    for i in range(args.checkout):
        cust = rand_customer()
        amt = rand_amount()
        payload, rec = build_abandoned_checkout(cust, amt)
        records.append(rec)
        if not args.no_webhook:
            trigger_webhook(payload, args.url)
            time.sleep(args.delay)

    # Generate subscriptions
    for i in range(args.subscription):
        cust = rand_customer()
        payload, rec = build_subscription_halted(cust)
        records.append(rec)
        if not args.no_webhook:
            trigger_webhook(payload, args.url)
            time.sleep(args.delay)

    # Generate overdue invoices
    for i in range(args.invoice):
        cust = rand_customer()
        amt = rand_amount()
        payload, rec = build_overdue_invoice(cust, amt)
        records.append(rec)
        if not args.no_webhook:
            trigger_webhook(payload, args.url)
            time.sleep(args.delay)

    # Export dataset
    export_path = DATA_EXPORT_DIR / "sample_cases.json"
    with open(export_path, "w") as f:
        json.dump(records, f, indent=2)

    print("\n" + "=" * 65)
    print(f"  ✅ Generated {len(records)} cases → {export_path}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
