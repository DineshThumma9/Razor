import uuid
from datetime import datetime
from models.models import RecoveryState, CustomerProfile
from models.schema import RazorpayWebhook
from service.customer import get_customer_profile, save_customer_profile
from sqlalchemy.ext.asyncio import AsyncSession
from config.clients import razorpay_client as client
from config.constants import HANDLED_EVENTS




def extract_ids_from_payload(payload: dict):
    try:
        webhook = RazorpayWebhook.model_validate(payload)
    except Exception:
        return None, "unknown"

    contains = webhook.contains
    case_id = None
    source_id = "unknown"
    
    if "subscription" in contains and webhook.payload.subscription:
        s = webhook.payload.subscription.entity
        case_id = s.id
        source_id = s.plan_id or "unknown"
    elif "invoice" in contains and webhook.payload.invoice:
        s = webhook.payload.invoice.entity
        case_id = s.id
        source_id = s.order_id or "unknown"
    elif "payment_link" in contains and webhook.payload.payment_link:
        s = webhook.payload.payment_link.entity
        case_id = s.id
        source_id = "unknown"
    elif "order" in contains and webhook.payload.order:
        s = webhook.payload.order.entity
        case_id = None  # order is usually the source_id
        source_id = s.get("id")
    elif "payment" in contains and webhook.payload.payment:
        s = webhook.payload.payment.entity
        case_id = s.id
        source_id = s.order_id or "unknown"
    elif "dispute" in contains and webhook.payload.dispute:
        s = webhook.payload.dispute.entity
        case_id = s.payment_id or s.id
        source_id = "unknown"
        
    return case_id, source_id


async def parse_webhook(payload: dict, db: AsyncSession) -> RecoveryState | None:
    try:
        webhook = RazorpayWebhook.model_validate(payload)
    except Exception as e:
        print(f"[WEBHOOK ERROR] Payload validation failed: {e}")
        return None

    if webhook.event not in HANDLED_EVENTS:
        return None
    
    # Captured and disputes are handled entirely in handle_payment_event, not here
    if webhook.event in ["payment.captured", "payment.dispute.created"]:
        return None
        
    contains = webhook.contains
    customer = dict()
    language = "english"
    amount = 0.0
    case_id = str(uuid.uuid4())
    source_id = "unknown"
    failure_reason = "Unknown"
    error_details = {}
    method = None
    through = None
    
    # Extract based on the richest available entity
    if "subscription" in contains and webhook.payload.subscription:
        s = webhook.payload.subscription.entity
        try:
            if s.customer_id and not s.customer_id.startswith("cust_mock"):
                cust = client.customer.fetch(s.customer_id)
                customer["name"] = cust.get("name", "Customer")
                customer["email"] = cust.get("email", "")
                customer["contact"] = cust.get("contact", "")
        except Exception:
            pass

        if not customer.get("name") or customer.get("name") == "Customer":
            if s.notes:
                customer["name"] = getattr(s.notes, "customer_name", None) or "Customer"
                customer["email"] = getattr(s.notes, "customer_email", None) or ""
                customer["contact"] = getattr(s.notes, "customer_contact", None) or ""
                language = getattr(s.notes, "language", None) or "english"

        case_id = s.id
        source_id = s.plan_id or "unknown"

        if getattr(s, "amount", None):
            amount = float(s.amount) / 100.0
        elif s.notes and getattr(s.notes, "amount", None):
            amount = float(s.notes.amount)

        if s.notes:
            failure_reason = getattr(s.notes, "halt_reason", None) or getattr(s.notes, "failure_reason", None) or "Subscription charge failed"
        
    elif "invoice" in contains and webhook.payload.invoice:
        s = webhook.payload.invoice.entity
        if s.customer_details:
            cd = s.customer_details
            customer["name"] = getattr(cd, "name", None) or getattr(cd, "customer_name", None) or "Customer"
            customer["email"] = getattr(cd, "email", None) or getattr(cd, "customer_email", None) or ""
            customer["contact"] = getattr(cd, "contact", None) or getattr(cd, "customer_contact", None) or ""
        case_id = s.id
        source_id = s.order_id or "unknown"
        amount = float(s.amount) / 100.0
        
    elif "payment_link" in contains and webhook.payload.payment_link:
        s = webhook.payload.payment_link.entity
        if s.customer:
            customer["name"] = s.customer.name or "Customer"
            customer["email"] = s.customer.email or ""
            customer["contact"] = s.customer.contact or ""
        case_id = s.id
        source_id = "unknown"
        amount = float(s.amount) / 100.0
        
    elif "payment" in contains and webhook.payload.payment:
        s = webhook.payload.payment.entity
        customer["name"] = s.name or "Customer"
        customer["email"] = s.email or ""
        customer["contact"] = s.contact or ""
        case_id = s.id
        source_id = s.order_id or "unknown"
        amount = float(s.amount) / 100.0
        failure_reason = s.error_description or "Unknown"
        
        error_details = {
            "error_code": s.error_code,
            "error_description": s.error_description,
            "error_reason": s.error_reason,
            "error_source": s.error_source,
            "error_step": s.error_step
        }
        if s.card:
            error_details["card_network"] = s.card.network
            error_details["card_last4"] = s.card.last4
            error_details["card_type"] = s.card.type
            error_details["card_issuer"] = s.card.issuer
        if s.acquirer_data:
            error_details["rrn"] = s.acquirer_data.get("rrn") or s.acquirer_data.get("bank_transaction_id")
            error_details["bank_transaction_id"] = s.acquirer_data.get("bank_transaction_id")
        method = s.method
        through = s.bank or s.vpa or s.wallet or (s.card.issuer if s.card else None)

    case_type = "failed_payment"
    if "subscription" in contains:
        if webhook.event == "subscription.cancelled":
            case_type = "subscription_cancelled"
        else:
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

    # --- Customer Intelligence Layer ---
    # Attempt to extract customer_id from payload or fallback to email/contact
    cust_id = customer.get("id")
    if not cust_id and "subscription" in contains and webhook.payload.subscription:
        cust_id = webhook.payload.subscription.entity.customer_id
        
    if not cust_id:
        # Generate a fake one for now if Razorpay didn't provide one
        cust_id = f"cust_{customer.get('contact', 'unknown')}"
        
    # Check if we have this customer in memory
    existing_profile = await get_customer_profile(cust_id, db)
    if existing_profile:
        # Use their saved preferences! Memory at work.
        language = existing_profile.language
        contact_pref = existing_profile.contact_preference
        customer["trust_score"] = existing_profile.trust_score
        customer["total_spend"] = existing_profile.total_spend
        await save_customer_profile(existing_profile, db)
    else:
        # First time seeing this customer, save them
        contact_pref = "whatsapp"
        customer["trust_score"] = 100
        customer["total_spend"] = 0.0
        new_profile = CustomerProfile(
            id=cust_id,
            name=customer.get("name"),
            email=customer.get("email"),
            contact=customer.get("contact"),
            language=language,
            contact_preference=contact_pref,
            trust_score=100,
            total_spend=0.0
        )
        await save_customer_profile(new_profile, db)
    
    return RecoveryState(
        case_id=case_id or str(uuid.uuid4()),
        source_id=source_id,            
        case_type=case_type,
        decline_type=decline_type,   
        failure_reason=failure_reason,
        error_details=error_details,
        method=method,
        through=through,
        amount_inr=amount,
        recovered_amount=0.0,
        customer=customer,
        contact_preference=contact_pref,
        language=language,
        recovery_status="pending",
        attempt_count=0,
        last_action_taken=None,
        first_seen_at=datetime.now(),
        next_retry_at=None,
        audit_log=[
            {
                "event_triggered": "payment_failed",
                "amount": str(amount),
                "recovery_status": "pending",
                "customer": customer,
                "next_contact": None,
                "message": f"Payment failure detected: {failure_reason or 'Transaction declined'}",
                "channel": "system",
                "direction": "system",
                "created_at": datetime.now().isoformat()
            }
        ]
    )
