"""
Suite 6: Razorpay HMAC-SHA256 Webhook Signature Verification.
Validates:
- Valid HMAC-SHA256 signature returns HTTP 200 (accepted)
- Tampered or corrupted signature returns HTTP 400 (bad request)
- Missing signature in DEMO_MODE permits graceful fallback for local development / testing
- Missing signature in production mode (DEMO_MODE=False) strictly blocks with HTTP 400
"""

import asyncio
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = SRC_DIR.parent
for p in [str(SRC_DIR), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from httpx import ASGITransport, AsyncClient

from config.config import settings
from main import app
from tests.common import GREEN, RESET, print_banner


async def test_razorpay_webhook_signature_verification():
    print_banner("6. Razorpay HMAC-SHA256 Webhook Signature Verification")

    orig_secret = settings.razorpay_webhook_secret
    orig_demo = settings.demo_mode

    try:
        settings.razorpay_webhook_secret = "whsec_test_demo_secret_key"
        payload = json.dumps({
            "entity": "event",
            "account_id": "acc_demo_test",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_sig_123",
                        "entity": "payment",
                        "amount": 500000,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": "order_sig_123",
                        "name": "Sig Test User",
                        "email": "sig@example.com",
                        "contact": "+919876543210",
                        "error_description": "Card expired",
                        "created_at": int(datetime.now().timestamp()),
                    }
                }
            },
        }).encode("utf-8")

        valid_sig = hmac.new(b"whsec_test_demo_secret_key", payload, hashlib.sha256).hexdigest()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Valid signature -> 200 accepted
            r_valid = await client.post(
                "/listen-events",
                content=payload,
                headers={"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"},
            )
            assert r_valid.status_code == 200, f"Expected 200 for valid signature, got {r_valid.status_code}"
            print("  Valid signature: accepted (HTTP 200)")

            # 2. Tampered signature -> 400 Bad Request
            r_bad = await client.post(
                "/listen-events",
                content=payload,
                headers={"X-Razorpay-Signature": "tampered_signature_hex", "Content-Type": "application/json"},
            )
            assert r_bad.status_code == 400, f"Expected 400 for tampered signature, got {r_bad.status_code}"
            print("  Tampered signature: rejected (HTTP 400)")

            # 3. Missing signature in DEMO_MODE -> 200 accepted (preserves local testing)
            settings.demo_mode = True
            r_demo_missing = await client.post(
                "/listen-events",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert r_demo_missing.status_code == 200, f"Expected 200 in DEMO_MODE bypass, got {r_demo_missing.status_code}"
            print("  Missing signature in DEMO_MODE: permitted for seamless local testing (HTTP 200)")

            # 4. Missing signature in Production (demo_mode=False) -> 400 Bad Request
            settings.demo_mode = False
            r_prod_missing = await client.post(
                "/listen-events",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert r_prod_missing.status_code == 400, f"Expected 400 in production for missing signature, got {r_prod_missing.status_code}"
            print("  Missing signature in Production: strictly blocked (HTTP 400)")

        print(f"{GREEN}✓ Razorpay HMAC Webhook Signature Verification passed!{RESET}")
    finally:
        settings.razorpay_webhook_secret = orig_secret
        settings.demo_mode = orig_demo


if __name__ == "__main__":
    asyncio.run(test_razorpay_webhook_signature_verification())
