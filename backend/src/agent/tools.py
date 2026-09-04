import asyncio
import calendar
from datetime import date, datetime, timedelta

from config.clients import (
    create_rzp_mandate_update_link,
    create_rzp_payment_link,
    generate_and_send_voice_note,
    send_resend_email,
    send_twilio_whatsapp,
)
import config.db as app_db
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from models.schema import (
    AuditEntry,
    CompleteCaseArgs,
    EmailReminderArgs,
    EscalateArgs,
    PaymentLinkArgs,
    PromiseToPayArgs,
    SalaryDateArgs,
)
from service.states import load_state, save_state
import logging as logger 
from typing import Optional

def get_next_follow_up_time(state) -> Optional[datetime]:
    """
    Computes progressive next retry milestone moving FORWARD in time:
    - Attempt >= 3: None (escalated to human operations, stopping rule)
    - Milestone is 3 days forward per attempt milestone (Attempt 1: +3d, Attempt 2: +6d, Attempt 3: +9d),
      snapped to business hours (10:00 AM).
    """
    attempt = getattr(state, "attempt_count", 0)
    if attempt >= 3:
        return None

    now = datetime.now()
    days_forward = (attempt + 1) * 3
    target = (now + timedelta(days=days_forward)).replace(hour=10, minute=0, second=0, microsecond=0)
    return target


async def _schedule_task(state, target_date: datetime, db):
    from background.worker import invoke_agent_task, revoke_active_task, schedule_source

    if state.active_task_id:
        await revoke_active_task(state.active_task_id)

    now = datetime.now()
    if target_date <= now:
        target_date = now + timedelta(minutes=1)

    logger.info(f"  [SCHEDULE] case={state.case_id} next_retry_at={target_date.isoformat()}")

    # Ensure schedule_source is connected
    if schedule_source._connection_pool is None:
        await schedule_source.startup()

    created = await invoke_agent_task.kicker().schedule_by_time(
        schedule_source,
        target_date,
        state.case_id,
    )
    # Store native Taskiq schedule ID so cancellation works cleanly
    state.active_task_id = created.schedule_id
    state.next_retry_at = target_date
    await save_state(state, db)
    logger.info(f"  [SCHEDULE] saved in Redis with schedule_id={created.schedule_id} — next_retry_at={state.next_retry_at}")


async def _log_audit(
    state,
    tool_name: str,
    next_retry_at: datetime | None,
    db,
    message: str | None = None,
    channel: str | None = None,
    direction: str | None = None,
):
    entry = AuditEntry(
        event_triggered=tool_name,
        amount=str(state.amount_inr),
        recovery_status=state.recovery_status,
        customer=state.customer,
        next_contact=next_retry_at,
        message=message,
        channel=channel,
        direction=direction,
        created_at=datetime.now(),
    )
    state.audit_log.append(entry.model_dump(mode="json"))
    logger.info(f"  [LOG_AUDIT] tool={tool_name} next_retry_at_param={next_retry_at} message={message}")
    if next_retry_at:
        state.next_retry_at = next_retry_at
    elif tool_name in ["escalate_to_human", "complete_case"]:
        state.next_retry_at = None
    if tool_name in ["send_whatsapp_msg", "send_email_reminder", "get_voice_call", "escalate_to_human"]:
        state.last_action_taken = tool_name
    await save_state(state, db)
    logger.info(f"  [LOG_AUDIT] save_state done for case={state.case_id}")


@tool(args_schema=EmailReminderArgs)
async def send_email_reminder(urgency: str, config: RunnableConfig) -> str:
    """
    Send a recovery email to the customer.
    Use 'gentle' for first contact, 'urgent' for 2nd attempt, 'final' before escalation.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        customer_name = state.customer.get("name", "Customer")
        customer_email = state.customer.get("email", "")
        amount_inr = state.amount_inr

        logger.info(f"\n  [TOOL] send_email_reminder")
        logger.info(f"    → To      : {customer_name} <{customer_email}>")
        logger.info(f"    → Amount  : ₹{amount_inr}")
        logger.info(f"    → Urgency : {urgency}")

        ref_code = state.case_id[-4:].upper() if len(state.case_id) >= 4 else state.case_id
        payment_link = (state.error_details or {}).get("payment_link")
        if not payment_link:
            try:
                payment_link, link_type, is_sub = await _generate_link_for_state(
                    state, customer_name, customer_email, state.customer.get("contact", ""), amount_inr
                )
                if state.error_details is None:
                    state.error_details = {}
                state.error_details["payment_link"] = payment_link
                state.error_details["link_type"] = link_type
                if is_sub:
                    state.error_details["mandate_update"] = True
                    state.error_details["sub_card_change"] = True
                await save_state(state, db)
            except Exception:
                payment_link = f"https://rzp.io/l/inv-{ref_code.lower()}"

        extra_ctx = {
            "invoice_number": (state.error_details or {}).get("invoice_number", f"INV-2026-{ref_code}"),
            "link": payment_link
        }

        await send_resend_email(urgency, customer_name, customer_email, amount_inr, extra_context=extra_ctx)

        next_contact = get_next_follow_up_time(state)
        if next_contact:
            await _schedule_task(state, next_contact, db)
        else:
            state.next_retry_at = None
            await save_state(state, db)

        if "b2b" in urgency:
            email_msg = f"Corporate Dunning ({urgency}): Invoice {extra_ctx['invoice_number']} for ₹{amount_inr:,.0f} sent to Accounts Payable <{customer_email}>."
        else:
            email_msg = f"Reminder ({urgency}): Payment of ₹{amount_inr:,.0f} for your order is due. Please complete payment to avoid service interruption."
        await _log_audit(
            state,
            "send_email_reminder",
            next_contact,
            db,
            message=email_msg,
            channel="email",
            direction="outbound",
        )

    return f"Email ({urgency}) queued for {customer_email}"


async def _generate_link_for_state(
    state, customer_name: str, customer_email: str, contact_number: str, amount_inr: float
) -> tuple[str, str, bool]:
    """
    Differentiates between one-time cart/invoice recovery and recurring subscription recovery.
    Returns (short_url, link_type, is_subscription).
    For recurring subscriptions, generates a Mandate Re-Authorization / Token Migration link (sub_card_change).
    For one-time orders/invoices, generates a standard one-time Razorpay payment link.
    """
    sub_id = (state.error_details or {}).get("subscription_id")
    if not sub_id and state.source_id and "sub_" in str(state.source_id):
        sub_id = state.source_id

    is_subscription = (
        state.case_type in ["failed_subscription", "subscription_cancelled", "subscription"]
        or bool(sub_id)
    )

    if is_subscription:
        short_url = await create_rzp_mandate_update_link(
            sub_id or f"sub_{state.case_id[-8:]}",
            customer_name,
            customer_email,
            contact_number,
            amount_inr,
        )
        return short_url, "mandate_reauthorization", True
    else:
        short_url = await create_rzp_payment_link(
            customer_name, customer_email, contact_number, amount_inr
        )
        return short_url, "one_time_payment", False


@tool(args_schema=PaymentLinkArgs)
async def create_payment_link(discount_pct: float = 0.0, config: RunnableConfig = None) -> str:
    """
    Create a Razorpay payment or mandate re-authorization link for the customer.
    Differentiates between one-time checkouts and recurring subscriptions (sub_card_change).
    Optionally accepts a discount_pct bounded by policy (e.g., between 5% and 30%).
    """
    case_id = config.get("configurable", {}).get("thread_id") if config else None
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        if not state:
            return "Error: Case state not found."
        customer_name = state.customer.get("name", "Customer")
        customer_email = state.customer.get("email", "")
        customer_contact = state.customer.get("contact", "")
        amount_inr = state.amount_inr

        # Bounded concession enforcement (clamped between min_discount and max_discount)
        if discount_pct > 0:
            discount_pct = max(float(settings.min_discount), min(float(discount_pct), float(settings.max_discount)))
            amount_inr = round(state.amount_inr * (1.0 - (discount_pct / 100.0)), 2)

        short_url, link_type, is_subscription = await _generate_link_for_state(
            state, customer_name, customer_email, customer_contact, amount_inr
        )

        logger.info(f"\n  [TOOL] create_payment_link")
        logger.info(f"    → Type     : {link_type} ({'Mandate Re-Auth (sub_card_change)' if is_subscription else 'One-Time Link'})")
        logger.info(f"    → Amount   : ₹{amount_inr} (Discount: {discount_pct}%)")
        logger.info(f"    → Link     : {short_url}")

        next_contact = get_next_follow_up_time(state)
        if next_contact:
            try:
                await _schedule_task(state, next_contact, db)
            except Exception as e:
                logger.info(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")

        # Store payment link and effective amount in error_details for message hydration
        if state.error_details is None:
            state.error_details = {}
        state.error_details["payment_link"] = short_url
        state.error_details["link_type"] = link_type
        if is_subscription:
            state.error_details["mandate_update"] = True
            state.error_details["sub_card_change"] = True
        state.error_details["discount_pct"] = discount_pct
        state.error_details["effective_amount_inr"] = amount_inr

        disc_str = f" ({discount_pct:.0f}% discount applied, payable ₹{amount_inr:,.0f})" if discount_pct > 0 else ""
        if is_subscription:
            link_msg = (
                f"Mandate Re-Authorization Link generated for recurring subscription: {short_url} "
                f"(Penny-drop auth to migrate token & protect future LTV)"
            )
        else:
            link_msg = f"Secure Razorpay payment link generated{disc_str}: {short_url}"

        await _log_audit(
            state,
            "create_payment_link",
            next_contact,
            db,
            message=link_msg,
            channel="link",
            direction="outbound",
        )

    if is_subscription:
        return f"Mandate re-authorization link generated for subscription: {short_url} (Token migration enabled)"
    return f"Payment link generated: {short_url}{disc_str}"


@tool(args_schema=EscalateArgs)
async def escalate_to_human(reason: str, config: RunnableConfig) -> str:
    """
    Escalate the case to human operations when automated recovery fails.
    Requires a detailed reason and customer context.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        customer_name = state.customer.get("name", "Customer")

        logger.info(f"\n  [TOOL] escalate_to_human")
        logger.info(f"    → Customer : {customer_name}")
        logger.info(f"    → Reason   : {reason}")

        state.recovery_status = "escalated"
        state.next_retry_at = None
        if state.active_task_id:
            from background.worker import revoke_active_task
            await revoke_active_task(state.active_task_id)
            state.active_task_id = None

        await _log_audit(
            state,
            "escalate_to_human",
            None,
            db,
            message=f"Escalated to human support. Reason: {reason}",
            channel="system",
            direction="system",
        )

    return f"Case for {customer_name} escalated to human. Reason: {reason}"


@tool(args_schema=SalaryDateArgs)
async def get_next_salary_date(config: RunnableConfig) -> str:
    """
    Returns upcoming salary milestone dates (1st, 15th, last Friday of month).
    Use this to decide the best retry date for soft declines (insufficient funds).
    """
    case_id = config.get("configurable", {}).get("thread_id")

    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        ref = state.next_retry_at.date() if (state and state.next_retry_at) else date.today()
        year, month = ref.year, ref.month

        milestones = []
        for day in [1, 15]:
            try:
                d = date(year, month, day)
                if d > ref:
                    milestones.append(d)
            except ValueError:
                pass

        last_day = calendar.monthrange(year, month)[1]
        last_date = date(year, month, last_day)
        offset = (last_date.weekday() - 4) % 7
        last_friday = last_date - timedelta(days=offset)
        if last_friday > ref:
            milestones.append(last_friday)

        milestones = sorted(set(milestones))

        if not milestones:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            milestones = [date(next_year, next_month, 1)]

        result = ", ".join(str(d) for d in milestones)
        closest = milestones[0]
        target_time = datetime.combine(closest, datetime.min.time()) + timedelta(
            hours=10
        )  # 10 AM

        try:
            await _schedule_task(state, target_time, db)
        except Exception as e:
            logger.info(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")

        salary_msg = f"Upcoming salary dates: {result}. Auto-scheduled next follow-up for {target_time.strftime('%b %d, %Y')}."
        await _log_audit(
            state,
            "get_next_salary_date",
            target_time,
            db,
            message=salary_msg,
            channel="system",
            direction="system",
        )

    logger.info(f"\n  [TOOL] get_next_salary_date")
    logger.info(f"    → Upcoming milestones: {result}. Scheduled retry for {target_time}.")

    return result


@tool(args_schema=CompleteCaseArgs)
async def complete_case(summary: str, config: RunnableConfig) -> str:
    """
    Call this tool when you have finished taking all necessary actions for this case.
    This tells the system to stop the workflow and move to the audit phase.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    if case_id:
        async with app_db.AsyncSessionLocal() as db:
            state = await load_state(case_id, db)
            if state:
                state.recovery_status = "closed"
                await _log_audit(
                    state,
                    "complete_case",
                    None,
                    db,
                    message=f"Case closed: {summary}",
                    channel="system",
                    direction="system",
                )
    print(f"\n  [TOOL] complete_case")
    print(f"    → Summary : {summary}")
    return "Case workflow completed."


@tool
async def send_whatsapp_msg(msg: str, config: RunnableConfig):
    """
    Sends a WhatsApp message to the customer using Twilio.
    msg is the content of the message. Automatically hydrates payment links if referenced.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        if not state:
            return "Failed: Case state not found."
        contact_number = state.customer.get("contact", "")

        if not contact_number:
            return "Failed: Customer has no contact number."

        # Link Hydration (Issue #4): Ensure real payment link is injected instead of ghost link
        payment_link = (state.error_details or {}).get("payment_link")
        needs_link = "{payment_link}" in msg or any(
            k in msg.lower() for k in ["link", "tap", "click", "pay", "settle", "checkout", "portal", "retry"]
        )

        if not payment_link and needs_link:
            # Brief yield in case create_payment_link is running concurrently in the same tool batch
            await asyncio.sleep(0.3)
            reloaded = await load_state(case_id, db)
            if reloaded:
                state = reloaded
                payment_link = (state.error_details or {}).get("payment_link")

            if not payment_link:
                try:
                    customer_name = state.customer.get("name", "Customer")
                    customer_email = state.customer.get("email", "")
                    effective_amt = (state.error_details or {}).get("effective_amount_inr", state.amount_inr)
                    payment_link, link_type, is_sub = await _generate_link_for_state(
                        state, customer_name, customer_email, contact_number, effective_amt
                    )
                    if state.error_details is None:
                        state.error_details = {}
                    state.error_details["payment_link"] = payment_link
                    state.error_details["link_type"] = link_type
                    if is_sub:
                        state.error_details["mandate_update"] = True
                        state.error_details["sub_card_change"] = True
                    await save_state(state, db)
                    logger.info(f"    → Hydrated missing {link_type} link on-the-fly: {payment_link}")
                except Exception as e:
                    logger.warning(f"    [WARN] Failed to auto-create payment link: {e}")

        # Hydrate message text with the payment link
        if payment_link:
            if "{payment_link}" in msg:
                msg = msg.replace("{payment_link}", payment_link)
            elif payment_link not in msg and "http://" not in msg and "https://" not in msg:
                is_recovery_msg = any(
                    k in msg.lower()
                    for k in ["link", "tap", "click", "pay", "settle", "checkout", "portal", "retry", "order", "invoice", "balance", "subscription"]
                )
                if is_recovery_msg:
                    if "(Ref:" in msg:
                        prefix, ref_part = msg.rsplit("(Ref:", 1)
                        msg = f"{prefix.strip()}\n\n🔗 Pay securely: {payment_link}\n\n(Ref:{ref_part}"
                    else:
                        msg = f"{msg.strip()}\n\n🔗 Pay securely: {payment_link}"
        
        sid = await send_twilio_whatsapp(contact_number, msg)
        print(f"Message dispatched successfully! SID: {sid}")

        next_contact = get_next_follow_up_time(state)
        if next_contact:
            try:
                await _schedule_task(state, next_contact, db)
            except Exception as e:
                print(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")
        else:
            state.next_retry_at = None
            await save_state(state, db)

        await _log_audit(
            state,
            "send_whatsapp_msg",
            next_contact,
            db,
            message=msg,
            channel="whatsapp",
            direction="outbound",
        )

    return f"WhatsApp sent to {contact_number}. SID: {sid}"


@tool
async def get_voice_call(msg: str, config: RunnableConfig):
    """
    Initiates an AI voice call using ElevenLabs to the customer, and sends it as a WhatsApp voice note.
    msg is the text to speak.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        contact_number = state.customer.get("contact", "")

        if not contact_number:
            return "Failed: Customer has no contact number."

        sid = await generate_and_send_voice_note(contact_number, msg)

        next_contact = get_next_follow_up_time(state)
        if next_contact:
            try:
                await _schedule_task(state, next_contact, db)
            except Exception as e:
                print(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")
        else:
            state.next_retry_at = None
            await save_state(state, db)

        await _log_audit(
            state,
            "get_voice_call",
            next_contact,
            db,
            message=f"Voice note dispatched: {msg}",
            channel="voice",
            direction="outbound",
        )

    return f"Voice note dispatched successfully to {contact_number}! SID: {sid}"



from config.config import settings
from datetime import datetime, timedelta

def sanity_date(d: datetime | None) -> tuple[bool, str]:
    """
    Validates that promise-to-pay date is:
    1. Not None
    2. Today or in the future (no past dates)
    3. Within max_grace_period days (default 7 days) from today
    """
    if not d:
        return False, "Promise date could not be parsed or was not provided"
    if d.tzinfo is not None:
        d = d.replace(tzinfo=None)
    now = datetime.now()
    today = now.date()
    target_date = d.date()

    if target_date < today:
        return False, f"Date {target_date.strftime('%Y-%m-%d')} is in the past (today is {today.strftime('%Y-%m-%d')})"

    max_allowed = today + timedelta(days=settings.max_grace_period)
    if target_date > max_allowed:
        days_out = (target_date - today).days
        return False, f"Date {target_date.strftime('%Y-%m-%d')} is {days_out} days in the future, exceeding the maximum policy grace period of {settings.max_grace_period} days"

    return True, "Valid"


async def _escalate_case_in_tool(rs, reason: str, db):
    """
    Directly persists escalation to database, revokes pending tasks,
    writes an internal escalation audit entry, and triggers an SSE broadcast.
    """
    rs.recovery_status = "escalated"
    rs.last_action_taken = "escalate_to_human"
    rs.next_retry_at = None

    if getattr(rs, "active_task_id", None):
        try:
            from background.worker import revoke_active_task
            await revoke_active_task(rs.active_task_id)
            rs.active_task_id = None
        except Exception as e:
            logger.warning(f"[HIL] Could not revoke task: {e}")

    await _log_audit(
        rs,
        "escalate_to_human",
        None,
        db,
        message=f"Escalated to human ops: {reason}",
        channel="system",
        direction="internal",
    )
    await save_state(rs, db)

    try:
        from service.broadcast import broadcast_case_update
        await broadcast_case_update(rs)
    except Exception as e:
        logger.warning(f"[HIL] Could not broadcast escalation: {e}")


@tool(args_schema=PromiseToPayArgs)
async def log_promise_to_pay(
    date_str: str, reason: str, sentiment: str, config: RunnableConfig
):
    """
    Call this tool when a customer replies via email or WhatsApp and promises to pay
    on a specific date. This will validate the date, schedule a business-hours reminder,
    or immediately escalate to human operations if the date is invalid, in the past, or out-of-bounds.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        if not state:
            return "Error: Case state not found."

        # Stopping rule: If already reached 3 attempts, reject automated promise and escalate
        if getattr(state, "attempt_count", 0) >= 3:
            rej_reason = f"Max attempts ({state.attempt_count}) reached. Cannot accept automated promise without human approval."
            logger.warning(f"[PTP REJECTED] {rej_reason} for case {state.case_id}")
            await _escalate_case_in_tool(state, rej_reason, db)
            return f"PROMISE_REJECTED: {rej_reason}. Case has been escalated to human operations."

        now = datetime.now()
        today = now.date()

        # 1. Parse target_date supporting multiple formats
        target_date = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                target_date = datetime.strptime(date_str.strip()[:19], fmt)
                break
            except ValueError:
                continue
        if not target_date:
            try:
                target_date = datetime.fromisoformat(date_str.strip())
            except Exception:
                try:
                    from dateutil.parser import parse
                    target_date = parse(date_str.strip(), fuzzy=True, default=datetime(now.year, now.month, now.day, 10, 0))
                except Exception:
                    target_date = None

        # Check hostility and grace period sanity
        is_hostile = sentiment.lower() in ["explicit", "threat", "danger", "angry", "hostile", "abusive"]
        is_valid, reject_reason = sanity_date(target_date)

        if is_hostile or not is_valid:
            rej_reason = f"Customer sentiment is hostile ('{sentiment}')" if is_hostile else reject_reason
            logger.warning(f"[PTP REJECTED] {rej_reason} for case {state.case_id}")
            await _escalate_case_in_tool(state, rej_reason, db)
            return (
                f"PROMISE_REJECTED: {rej_reason}. "
                f"Case has been escalated to human operations."
            )

        # 2. Timing adjustments: Snap to business hours (10:00 AM), avoiding 12:00 AM midnight retries
        from datetime import time as dt_time
        if target_date.date() > today:
            target_date = datetime.combine(target_date.date(), dt_time(10, 0))
        elif target_date.date() == today:
            target_date = datetime.combine(today, dt_time(18, 0))
            if target_date <= now:
                target_date = now + timedelta(hours=2)

        if state.error_details is None:
            state.error_details = {}
        state.error_details["ptp_date"] = target_date.strftime("%Y-%m-%d")

        await _schedule_task(state, target_date, db)

        confirm_msg = f"Thank you! We have noted your promise to pay on {target_date.strftime('%Y-%m-%d')}. Automated reminders are paused until then."
        contact_number = state.customer.get("contact", "")
        if contact_number:
            await send_twilio_whatsapp(contact_number, confirm_msg)

        ptp_msg = f"Promise to pay recorded for {target_date.strftime('%b %d, %Y')}. Confirmation sent to customer."
        await _log_audit(
            state,
            "log_promise_to_pay",
            target_date,
            db,
            message=ptp_msg,
            channel="system",
            direction="system",
        )

    return f"Successfully logged promise to pay on {date_str}. Confirmation message sent to customer."


tools = [
    send_email_reminder,
    create_payment_link,
    escalate_to_human,
    get_next_salary_date,
    complete_case,
    get_voice_call,
    send_whatsapp_msg,
    log_promise_to_pay,
]
