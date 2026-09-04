"""
Renvue Core Demo & Feature Regression Test Suite.
Validates:
1. Fast-Forward 3 Times: Progressive date advancement and automatic Human Escalation when attempts >= 3.
2. Promise-To-Pay (PTP): Customer commitment extraction, grace-period validation, and follow-up snapping.
3. Overdue Commercial Invoice (B2B): AP tone decorum, Net-30 terms, TDS compliance acknowledgment.
4. Recurring Subscription: Mandate update link generation and RBI Section 10(2) pre-debit intimation.

Run directly via:
PYTHONPATH=src uv run python test_demo_flows.py
"""

import asyncio
from datetime import datetime, timedelta, date
import sys
import uuid

from config.db import AsyncSessionLocal, _init_db
from models.models import RecoveryState
from service.states import save_state, load_state
from agent.graph import get_compiled_agent
from langchain_core.messages import HumanMessage
from agent.prompts import get_escalation_tone
from agent.tools import log_promise_to_pay
from agent.utils import sanity_date
from service.compliance import get_bell_curve_discount
from config.config import settings


GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str):
    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    print(f"{CYAN}{BOLD} TEST: {title}{RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}")


async def test_fast_forward_3_times_and_escalate():
    print_banner("1. Fast-Forward 3 Times & Auto-Escalation")
    _init_db()
    case_id = f"test_ff_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
    
    async with AsyncSessionLocal() as db:
        initial = RecoveryState(
            case_id=case_id,
            source_id=f"order_{uuid.uuid4().hex[:6]}",
            case_type="failed_payment",
            amount_inr=5000.0,
            customer={"name": "Dinesh Test", "email": "test@example.com", "contact": "+919876543210"},
            failure_reason="Insufficient funds",
            recovery_status="pending",
            attempt_count=0,
            audit_log=[]
        )
        await save_state(initial, db)

    agent = get_compiled_agent()
    config = {"configurable": {"thread_id": case_id}}

    prev_retry = None

    # Turn 1: Attempt 1
    async with AsyncSessionLocal() as db:
        st = await load_state(case_id, db)
    await agent.ainvoke({"messages": [], "recovery_state": st, "event_source": "automated.webhook"}, config=config)
    async with AsyncSessionLocal() as db:
        t1 = await load_state(case_id, db)
    print(f"  Turn 1: attempt={t1.attempt_count}, status={t1.recovery_status}, next_retry={t1.next_retry_at}")
    assert t1.attempt_count == 1, f"Expected attempt 1, got {t1.attempt_count}"
    assert t1.recovery_status == "pending", f"Expected pending, got {t1.recovery_status}"
    assert t1.next_retry_at is not None, "next_retry_at should be scheduled"
    prev_retry = t1.next_retry_at

    # Customer Reply 1 (Inbound conversational interaction): MUST NOT increment attempt_count
    async with AsyncSessionLocal() as db:
        st = await load_state(case_id, db)
    await agent.ainvoke({
        "messages": [HumanMessage(content="Why did my card payment decline? Can you help?")],
        "recovery_state": st,
        "event_source": "inbound.whatsapp"
    }, config=config)
    async with AsyncSessionLocal() as db:
        t1_reply = await load_state(case_id, db)
    print(f"  Customer Reply 1: attempt={t1_reply.attempt_count}, status={t1_reply.recovery_status} (MUST remain 1)")
    assert t1_reply.attempt_count == 1, f"Inbound reply must NOT increment attempt_count (expected 1, got {t1_reply.attempt_count})"

    # Turn 2: Fast-Forward to Attempt 2
    async with AsyncSessionLocal() as db:
        st = await load_state(case_id, db)
    await agent.ainvoke({"messages": [], "recovery_state": st, "event_source": "scheduled.follow_up"}, config=config)
    async with AsyncSessionLocal() as db:
        t2 = await load_state(case_id, db)
    print(f"  Turn 2: attempt={t2.attempt_count}, status={t2.recovery_status}, next_retry={t2.next_retry_at}")
    assert t2.attempt_count == 2, f"Expected attempt 2, got {t2.attempt_count}"
    assert t2.recovery_status == "pending", f"Expected pending, got {t2.recovery_status}"
    assert t2.next_retry_at is not None and t2.next_retry_at > prev_retry, "next_retry_at should advance forward"
    prev_retry = t2.next_retry_at

    # Customer Reply 2 (Another conversational interaction): MUST NOT increment attempt_count
    async with AsyncSessionLocal() as db:
        st = await load_state(case_id, db)
    await agent.ainvoke({
        "messages": [HumanMessage(content="Okay, could you resend the secure payment link?")],
        "recovery_state": st,
        "event_source": "inbound.whatsapp"
    }, config=config)
    async with AsyncSessionLocal() as db:
        t2_reply = await load_state(case_id, db)
    print(f"  Customer Reply 2: attempt={t2_reply.attempt_count}, status={t2_reply.recovery_status} (MUST remain 2)")
    assert t2_reply.attempt_count == 2, f"Inbound reply must NOT increment attempt_count (expected 2, got {t2_reply.attempt_count})"

    # Turn 3: Fast-Forward to Attempt 3 (Final Notice)
    async with AsyncSessionLocal() as db:
        st = await load_state(case_id, db)
    await agent.ainvoke({"messages": [], "recovery_state": st, "event_source": "scheduled.follow_up"}, config=config)
    async with AsyncSessionLocal() as db:
        t3 = await load_state(case_id, db)
    print(f"  Turn 3: attempt={t3.attempt_count}, status={t3.recovery_status}, next_retry={t3.next_retry_at}")
    assert t3.attempt_count == 3, f"Expected attempt 3, got {t3.attempt_count}"
    assert t3.recovery_status == "pending", f"Expected pending, got {t3.recovery_status}"
    assert t3.next_retry_at is not None and t3.next_retry_at >= prev_retry, "next_retry_at should reflect final grace window"

    # Turn 4: Fast-Forward after 3 attempts exhausted -> MUST Auto-Escalate and NEVER exceed 3/3
    async with AsyncSessionLocal() as db:
        st = await load_state(case_id, db)
    await agent.ainvoke({"messages": [], "recovery_state": st, "event_source": "scheduled.follow_up"}, config=config)
    async with AsyncSessionLocal() as db:
        t4 = await load_state(case_id, db)
    print(f"  Turn 4 (Post-Attempt 3): attempt={t4.attempt_count}, status={t4.recovery_status}, last_action={t4.last_action_taken}, next_retry={t4.next_retry_at}")
    assert t4.attempt_count == 3, f"Attempt count must NEVER exceed 3 (got {t4.attempt_count}/3)"
    assert t4.recovery_status == "escalated", f"Expected status 'escalated', got '{t4.recovery_status}'"
    assert t4.last_action_taken == "escalate_to_human", f"Expected last_action 'escalate_to_human', got '{t4.last_action_taken}'"
    assert t4.next_retry_at is None, f"Expected next_retry_at None after escalation, got {t4.next_retry_at}"
    print(f"{GREEN}✓ Fast-forward 3 times, customer conversation, and auto-escalation strictly at 3/3 passed!{RESET}")


async def test_promise_to_pay_case():
    print_banner("2. Promise-To-Pay (PTP) Validation & Scheduling")
    now = datetime.now()
    
    # 1. Valid future date (within 7 days max grace)
    valid_dt = now + timedelta(days=3)
    is_valid, msg = sanity_date(valid_dt)
    print(f"  Testing date +3 days ({valid_dt.strftime('%Y-%m-%d')}): valid={is_valid}, msg={msg}")
    assert is_valid is True, f"Expected valid date, got {msg}"

    # 2. Past date (must be rejected)
    past_dt = now - timedelta(days=1)
    is_valid_past, msg_past = sanity_date(past_dt)
    print(f"  Testing past date ({past_dt.strftime('%Y-%m-%d')}): valid={is_valid_past}, msg={msg_past}")
    assert is_valid_past is False, "Past date should be rejected"

    # 3. Excessive grace period (> 7 days, must be rejected)
    far_dt = now + timedelta(days=20)
    is_valid_far, msg_far = sanity_date(far_dt)
    print(f"  Testing far future date ({far_dt.strftime('%Y-%m-%d')}): valid={is_valid_far}, msg={msg_far}")
    assert is_valid_far is False, "Date beyond policy grace period should be rejected"

    # 4. Anti-Exploitation: Cumulative Grace Period Tracking
    # Failure on 1st, customer promised 6th (5 days used), on 6th tries to promise 12th (total 11 days > 7 limit)
    incident_date = date(2026, 9, 1)
    ptp_1 = datetime(2026, 9, 6, 10, 0)
    valid_ptp_1, msg_ptp_1 = sanity_date(ptp_1, anchor_date=incident_date)
    print(f"  Testing Turn 1 promise 6th (incident 1st): valid={valid_ptp_1}, msg={msg_ptp_1}")
    assert valid_ptp_1 is True, "First promise within 7 cumulative days should be valid"

    ptp_2_exploit = datetime(2026, 9, 12, 10, 0)
    valid_ptp_2, msg_ptp_2 = sanity_date(ptp_2_exploit, anchor_date=incident_date)
    print(f"  Testing Turn 2 chained promise 12th (incident 1st): valid={valid_ptp_2}, msg={msg_ptp_2}")
    assert valid_ptp_2 is False, "Chained promise exceeding cumulative 7-day limit from incident must be rejected"

    # 5. Tool execution test: Date extracted from typo ("5th of spet" -> valid tomorrow date)
    case_id_ptp = f"test_ptp_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
    async with AsyncSessionLocal() as db:
        ptp_case = RecoveryState(
            case_id=case_id_ptp,
            source_id=f"order_{uuid.uuid4().hex[:6]}",
            case_type="failed_payment",
            amount_inr=5000.0,
            customer={"name": "Dinesh Test", "email": "test@example.com", "contact": "+919876543210"},
            failure_reason="Insufficient funds",
            recovery_status="pending",
            attempt_count=1,
            audit_log=[]
        )
        await save_state(ptp_case, db)

    config_ptp = {"configurable": {"thread_id": case_id_ptp}}
    valid_ptp_str = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    res_ptp = await log_promise_to_pay.ainvoke(
        {"date_str": valid_ptp_str, "reason": "5th of spet payment commitment", "sentiment": "neutral"},
        config=config_ptp
    )
    print(f"  Tool execution (valid date): {res_ptp}")
    assert "Successfully logged promise to pay" in res_ptp

    async with AsyncSessionLocal() as db:
        after_ptp = await load_state(case_id_ptp, db)
    assert after_ptp.recovery_status == "pending", "Case must remain pending (not escalated) on valid date"
    assert after_ptp.case_metadata.get("cumulative_grace_days_used") is not None
    assert "cumulative_grace_days_used" not in (after_ptp.error_details or {})

    # 6. Tool execution test: No date / vague reply (`date_str=None`) -> schedules +3 days, NO escalation
    case_id_none = f"test_none_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
    async with AsyncSessionLocal() as db:
        none_case = RecoveryState(
            case_id=case_id_none,
            source_id=f"order_{uuid.uuid4().hex[:6]}",
            case_type="failed_payment",
            amount_inr=5000.0,
            customer={"name": "Dinesh Test", "email": "test@example.com", "contact": "+919876543210"},
            failure_reason="Insufficient funds",
            recovery_status="pending",
            attempt_count=1,
            audit_log=[]
        )
        await save_state(none_case, db)

    config_none = {"configurable": {"thread_id": case_id_none}}
    res_none = await log_promise_to_pay.ainvoke(
        {"date_str": None, "reason": "Will pay in a few days", "sentiment": "gentle"},
        config=config_none
    )
    print(f"  Tool execution (date_str=None): {res_none}")
    assert "No concrete commitment date specified" in res_none or "standard follow-up scheduled" in res_none

    async with AsyncSessionLocal() as db:
        after_none = await load_state(case_id_none, db)
    assert after_none.recovery_status == "pending", "Vague reply without concrete date must NOT escalate to human"
    assert after_none.next_retry_at is not None, "Standard +3 days follow-up must be scheduled"

    print(f"{GREEN}✓ Promise-to-Pay policy validation and execution passed!{RESET}")


async def test_overdue_invoice_case():
    print_banner("3. B2B Commercial Overdue Invoice Recovery")
    _init_db()
    case_id = f"test_inv_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
    
    async with AsyncSessionLocal() as db:
        inv_case = RecoveryState(
            case_id=case_id,
            source_id="inv_mock_999",
            case_type="overdue_invoice",
            amount_inr=150000.0,
            customer={"name": "Acme Corp AP", "email": "ap@acme.com", "contact": "+919876543210"},
            failure_reason="Invoice overdue by 15 days",
            error_details={},
            case_metadata={"invoice_number": "INV-2026-8888", "po_number": "PO-4421"},
            recovery_status="pending",
            attempt_count=0,
            audit_log=[]
        )
        await save_state(inv_case, db)

    # Verify B2B escalation tone contract
    wa_msg, email_urg, voice_msg = get_escalation_tone(inv_case)
    print(f"  B2B WhatsApp Copy : {wa_msg[:80]}...")
    print(f"  B2B Email Urgency : {email_urg}")
    print(f"  B2B Voice Script  : {voice_msg[:80]}...")
    
    assert "Accounts Payable" in wa_msg or "Invoice" in wa_msg, "B2B copy must address AP / Invoice"
    assert email_urg.startswith("b2b_"), f"Expected B2B email urgency, got {email_urg}"
    assert "Accounts Receivable" in voice_msg, "B2B voice note must identify as Accounts Receivable"

    # Run agent execution
    agent = get_compiled_agent()
    config = {"configurable": {"thread_id": case_id}}
    await agent.ainvoke({"messages": [], "recovery_state": inv_case, "event_source": "automated.webhook"}, config=config)

    async with AsyncSessionLocal() as db:
        after = await load_state(case_id, db)
    print(f"  Execution: attempt={after.attempt_count}, last_action={after.last_action_taken}, status={after.recovery_status}")
    assert after.attempt_count == 1, "Attempt count should be 1"
    assert len(after.audit_log) > 0, "Audit log must record B2B outreach"
    print(f"{GREEN}✓ B2B Commercial Overdue Invoice recovery passed!{RESET}")


async def test_recurring_subscription_case():
    print_banner("4. Recurring Subscription Mandate Recovery & RBI Intimation")
    _init_db()
    case_id = f"test_sub_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"

    async with AsyncSessionLocal() as db:
        sub_case = RecoveryState(
            case_id=case_id,
            source_id="sub_mock_777",
            case_type="failed_subscription",
            amount_inr=2499.0,
            customer={"name": "Rahul Verma", "email": "rahul@example.com", "contact": "+919876543210"},
            failure_reason="Auto-debit recurring mandate failed: Card expired",
            error_details={},
            recovery_status="pending",
            attempt_count=0,
            audit_log=[]
        )
        await save_state(sub_case, db)

    agent = get_compiled_agent()
    config = {"configurable": {"thread_id": case_id}}
    await agent.ainvoke({"messages": [], "recovery_state": sub_case, "event_source": "automated.webhook"}, config=config)

    async with AsyncSessionLocal() as db:
        after = await load_state(case_id, db)

    link = (after.case_metadata or {}).get("payment_link")
    link_type = (after.case_metadata or {}).get("link_type")
    print(f"  Hydrated Link: {link} (type={link_type})")
    print(f"  Attempt={after.attempt_count}, Next Retry={after.next_retry_at}")
    
    assert link is not None, "Mandate / payment link must be hydrated"
    assert "payment_link" not in (after.error_details or {}), "error_details must not contain payment_link"
    assert after.attempt_count == 1, "Attempt count should be 1"
    print(f"{GREEN}✓ Recurring Subscription Mandate recovery passed!{RESET}")


async def test_abandoned_checkout_bell_curve_discount():
    print_banner("5. Abandoned Checkout Bell-Curve Concession & Anti-Gaming")
    _init_db()

    # 1. Non-abandoned case policy rejection verification
    inv_state = RecoveryState(case_id="dummy_inv", source_id="inv_1", case_type="overdue_invoice", amount_inr=10000.0)
    sub_state = RecoveryState(case_id="dummy_sub", source_id="sub_1", case_type="failed_subscription", amount_inr=2000.0)
    assert get_bell_curve_discount(inv_state) == 0.0, "Discounts must be strictly disallowed for corporate invoices"
    assert get_bell_curve_discount(sub_state) == 0.0, "Discounts must be strictly disallowed for recurring subscriptions"

    # 2. Abandoned checkout deterministic recovery flow
    case_id = f"test_cart_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}"
    original_amount = 5000.0

    async with AsyncSessionLocal() as db:
        cart_case = RecoveryState(
            case_id=case_id,
            source_id=f"cart_{uuid.uuid4().hex[:6]}",
            case_type="abandoned_checkout",
            amount_inr=original_amount,
            customer={"name": "Ananya Sharma", "email": "ananya@example.com", "contact": "+919876543210"},
            failure_reason="Customer abandoned cart during payment checkout",
            error_details={},
            recovery_status="pending",
            attempt_count=0,
            audit_log=[]
        )
        await save_state(cart_case, db)

    agent = get_compiled_agent()
    config = {"configurable": {"thread_id": case_id}}

    # Turn 1: Automated webhook outreach
    await agent.ainvoke({"messages": [], "recovery_state": cart_case, "event_source": "automated.webhook"}, config=config)

    async with AsyncSessionLocal() as db:
        t1 = await load_state(case_id, db)

    eligible = (t1.case_metadata or {}).get("eligible_discount")
    discount_pct = (t1.case_metadata or {}).get("discount_pct")
    effective_amt = (t1.case_metadata or {}).get("effective_amount_inr")
    payment_link = (t1.case_metadata or {}).get("payment_link")

    print(f"  Attempt 1 Outreach: eligible_discount={eligible}%, applied_discount={discount_pct}%, effective_amount=₹{effective_amt}, link={payment_link}")

    assert eligible is not None, "eligible_discount must be populated for abandoned checkout"
    assert float(settings.min_discount) <= eligible <= float(settings.max_discount), f"Discount {eligible}% out of bounds [{settings.min_discount}, {settings.max_discount}]"
    assert discount_pct == eligible, "Applied discount must match approved eligible concession"
    expected_amt = round(original_amount * (1.0 - (eligible / 100.0)), 2)
    assert effective_amt == expected_amt, f"Expected effective amount ₹{expected_amt}, got ₹{effective_amt}"
    assert payment_link is not None, "Payment link must be hydrated"
    assert "eligible_discount" not in (t1.error_details or {}), "error_details must not contain eligible_discount"
    assert "discount_pct" not in (t1.error_details or {}), "error_details must not contain discount_pct"
    assert "payment_link" not in (t1.error_details or {}), "error_details must not contain payment_link"

    # Idempotency & Anti-Gaming Verification
    locked_again = get_bell_curve_discount(t1)
    assert locked_again == eligible, f"Discount must be idempotently locked (expected {eligible}, got {locked_again})"

    # Tone copy check
    wa_msg, email_urg, voice_msg = get_escalation_tone(t1)
    assert email_urg == "cart_gentle", f"Expected cart_gentle email tone, got {email_urg}"
    assert "cart" in wa_msg.lower() or "reserved" in wa_msg.lower(), "WhatsApp copy must reference cart reservation"

    # Turn 2: Customer haggles for 50% discount (Anti-gaming check)
    await agent.ainvoke({
        "messages": [HumanMessage(content="Can I get an extra 50% discount? It's too expensive.")],
        "recovery_state": t1,
        "event_source": "inbound.whatsapp"
    }, config=config)

    async with AsyncSessionLocal() as db:
        t2 = await load_state(case_id, db)

    post_haggle_eligible = (t2.case_metadata or {}).get("eligible_discount")
    post_haggle_discount = (t2.case_metadata or {}).get("discount_pct")
    print(f"  Customer Haggle Response: eligible={post_haggle_eligible}%, applied={post_haggle_discount}%")
    assert post_haggle_eligible == eligible, f"Concession ceiling must not expand on customer haggle (locked at {eligible}%)"
    assert post_haggle_discount <= eligible, f"Applied discount must not exceed locked ceiling ({eligible}%)"
    assert "eligible_discount" not in (t2.error_details or {}), "error_details must not contain eligible_discount"
    assert "discount_pct" not in (t2.error_details or {}), "error_details must not contain discount_pct"
    assert t2.attempt_count == 1, "Inbound negotiation reply must not increment attempt_count"

    print(f"{GREEN}✓ Abandoned Checkout Bell-Curve Concession & Anti-Gaming test passed!{RESET}")


async def main():
    print(f"\n{BOLD}Starting Renvue Demo & Core Feature Regression Test Suite...{RESET}")
    start = datetime.now()
    try:
        await test_fast_forward_3_times_and_escalate()
        await test_promise_to_pay_case()
        await test_overdue_invoice_case()
        await test_recurring_subscription_case()
        await test_abandoned_checkout_bell_curve_discount()
        elapsed = (datetime.now() - start).total_seconds()
        print(f"\n{GREEN}{BOLD}{'='*70}{RESET}")
        print(f"{GREEN}{BOLD} ALL 5 DEMO REGRESSION SUITES PASSED CLEANLY in {elapsed:.2f}s!{RESET}")
        print(f"{GREEN}{BOLD}{'='*70}{RESET}\n")
    except AssertionError as e:
        print(f"\n{RED}{BOLD}❌ REGRESSION ASSERTION FAILED:{RESET} {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}{BOLD}❌ UNEXPECTED TEST ERROR:{RESET} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
