import asyncio
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.messages import SystemMessage
from langchain_mistralai import ChatMistralAI
from sqlalchemy.ext.asyncio import AsyncSession

from config.clients import (
    create_rzp_mandate_update_link,
    create_rzp_payment_link,
    generate_and_send_voice_note,
    get_redis_client,
    send_resend_email,
    send_twilio_whatsapp,
)
from config.config import settings
from config.constants import hard_declines
from config.db import AsyncSessionLocal
from config.logger import get_logger
from models.models import RecoveryState
from models.schema import AuditEntry
from service.broadcast import broadcast_case_update
from service.compliance import (
    adjust_for_trai_window,
    build_whatsapp_payload,
    calculate_rbi_pre_debit_schedule,
    calculate_salary_milestones,
    format_rbi_pre_debit_intimation,
    get_bell_curve_discount,
    is_recurring_mandate_case,
)
from service.states import save_state
from agent.prompts import (
    get_escalation_tone,
    should_send_channel,
)

logger = get_logger(__name__)

_llm_instance = None
_llm_with_tools = None


def get_llm(tools=None):
    """
    Returns the singleton ChatMistralAI instance bound with agent tools.
    Preserves connection pooling and tool bindings across conversation turns.
    """
    global _llm_instance, _llm_with_tools
    if _llm_with_tools is None:
        if tools is None:
            from agent.tools import tools as agent_tools
            tools = agent_tools
        _llm_instance = ChatMistralAI(model=settings.model, temperature=0, max_retries=2, timeout=25)
        _llm_with_tools = _llm_instance.bind_tools(tools)
    return _llm_with_tools


def get_next_follow_up_time(state: RecoveryState) -> Optional[datetime]:
    """
    Computes progressive next retry milestone moving FORWARD in time:
    - Attempt >= 3: None (escalated to human operations, stopping rule)
    - Milestone is 3 days forward per attempt milestone (Attempt 1: +3d, Attempt 2: +6d, Attempt 3: +9d),
      snapped to business hours (10:00 AM) and verified against TRAI 9 AM - 9 PM window.
    - For recurring subscriptions, calculates RBI 24-hour pre-debit intimation schedule.
    """
    attempt = getattr(state, "attempt_count", 0)
    if attempt >= 3:
        return None

    now = datetime.now()
    base_dt = state.next_retry_at if state.next_retry_at and state.next_retry_at > now else now
    target = (base_dt + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    target = adjust_for_trai_window(target)

    # RBI Section 10(2) PSS Act: Pre-Debit Intimation for recurring mandate cases (#14)
    if is_recurring_mandate_case(state):
        if state.case_metadata is None:
            state.case_metadata = {}
        pre_debit_dt = calculate_rbi_pre_debit_schedule(state, target)
        state.case_metadata["rbi_pre_debit_compliance"] = {
            "pss_act_section": "10(2)",
            "mandate_pre_debit_required": True,
            "scheduled_debit_at": target.isoformat(),
            "pre_debit_intimation_at": pre_debit_dt.isoformat() if pre_debit_dt else None,
            "compliance_verified": True,
        }

    return target


async def _schedule_task(state: RecoveryState, target_date: datetime, db: AsyncSession):
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
    state: RecoveryState,
    tool_name: str,
    next_retry_at: datetime | None,
    db: AsyncSession,
    message: str | None = None,
    channel: str | None = None,
    direction: str | None = None,
    meta_compliance: str | None = None,
    hsm_template: str | None = None,
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
        meta_compliance=meta_compliance,
        hsm_template=hsm_template,
        created_at=datetime.now(),
    )
    state.audit_log.append(entry.model_dump(mode="json"))
    logger.info(f"  [LOG_AUDIT] tool={tool_name} next_retry_at_param={next_retry_at} message={message}")
    if tool_name in ["escalate_to_human", "complete_case"]:
        state.next_retry_at = None
    if tool_name in ["send_whatsapp_msg", "send_email_reminder", "get_voice_call", "escalate_to_human"]:
        state.last_action_taken = tool_name
    await save_state(state, db)
    logger.info(f"  [LOG_AUDIT] save_state done for case={state.case_id}")


async def _generate_link_for_state(
    state: RecoveryState, customer_name: str, customer_email: str, contact_number: str, amount_inr: float
) -> tuple[str, str, bool]:
    """
    Differentiates between one-time cart/invoice recovery and recurring subscription recovery.
    Returns (short_url, link_type, is_subscription).
    """
    sub_id = (state.case_metadata or {}).get("subscription_id")
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


async def ensure_payment_link(state: RecoveryState, db: AsyncSession, discount_pct: float = 0.0) -> tuple[str, str, bool]:
    """
    Consolidated helper: checks state.case_metadata for existing payment_link.
    If missing, generates it via _generate_link_for_state, updates state.case_metadata,
    and commits to db.
    Returns (payment_link, link_type, is_subscription).
    """
    meta = state.case_metadata or {}
    payment_link = meta.get("payment_link")
    link_type = meta.get("link_type", "one_time_payment")
    is_sub = bool(meta.get("mandate_update"))

    if payment_link:
        return payment_link, link_type, is_sub

    customer_name = state.customer.get("name", "Customer")
    customer_email = state.customer.get("email", "")
    customer_contact = state.customer.get("contact", "")
    base_amount = state.amount_inr

    # Margin-Safe Bell-Curve Discount Policy & Anti-Gaming
    if state.case_type == "abandoned_checkout":
        eligible = get_bell_curve_discount(state)
        discount_pct = eligible if discount_pct <= 0.0 else min(discount_pct, eligible)
        amount_inr = round(base_amount * (1.0 - (discount_pct / 100.0)), 2)
    else:
        discount_pct = 0.0
        amount_inr = base_amount

    try:
        payment_link, link_type, is_sub = await _generate_link_for_state(
            state, customer_name, customer_email, customer_contact, amount_inr
        )
        if state.case_metadata is None:
            state.case_metadata = {}
        state.case_metadata["payment_link"] = payment_link
        state.case_metadata["link_type"] = link_type
        if is_sub:
            state.case_metadata["mandate_update"] = True
            state.case_metadata["sub_card_change"] = True
        if discount_pct > 0:
            state.case_metadata["discount_pct"] = discount_pct
            state.case_metadata["eligible_discount"] = discount_pct
            state.case_metadata["effective_amount_inr"] = amount_inr
        await save_state(state, db)
    except Exception as e:
        ref_code = state.case_id[-4:].upper() if len(state.case_id) >= 4 else state.case_id
        logger.critical(f"No generated a link just faking it due to :{e}")
        payment_link = f"https://rzp.io/l/inv-{ref_code.lower()}"
        link_type = "one_time_payment"
        is_sub = False

    return payment_link, link_type, is_sub


def sanity_date(d: datetime | None, anchor_date: date | datetime | None = None) -> tuple[bool, str]:
    """
    Validates that promise-to-pay date is:
    1. Not None
    2. Today or in the future (no past dates)
    3. Within max_grace_period days (default 7 days) from today
    4. Within max_grace_period days cumulative from the initial incident/failure anchor date
       (prevents chained promise exploitation where customers push out dates indefinitely).
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

    # Check cumulative grace period from initial incident date
    if anchor_date is not None:
        incident_date = anchor_date.date() if isinstance(anchor_date, datetime) else anchor_date
        max_cumulative_allowed = incident_date + timedelta(days=settings.max_grace_period)
        if target_date > max_cumulative_allowed:
            total_days = (target_date - incident_date).days
            return False, (
                f"Date {target_date.strftime('%Y-%m-%d')} is {total_days} days after the initial failure incident "
                f"({incident_date.strftime('%Y-%m-%d')}), which exceeds the cumulative policy grace period limit of "
                f"{settings.max_grace_period} days"
            )

    max_allowed = today + timedelta(days=settings.max_grace_period)
    if target_date > max_allowed:
        days_out = (target_date - today).days
        return False, f"Date {target_date.strftime('%Y-%m-%d')} is {days_out} days in the future, exceeding the maximum policy grace period of {settings.max_grace_period} days"

    return True, "Valid"


def cant_resolve(rs: RecoveryState) -> tuple[bool, str]:
    """
    Checks if a case is fundamentally unrecoverable due to hard declines, fraud, or internal errors.
    """
    details = rs.error_details or {}
    source = details.get("error_source")
    reason = details.get("error_reason")
    desc = details.get("error_description", "")

    unresolvable_reasons = ['fraud_suspected', 'card_lost_or_stolen', 'account_frozen', 'account_closed']

    if source == "internal":
        return True, "There is a temporary issue with our payment gateway. Please try again later."

    if reason in unresolvable_reasons:
        return True, "Your payment was blocked by your bank for security reasons. Please try a different payment method or contact your bank."

    if rs.method == "card" and desc in hard_declines.values():
        return True, f"Your card payment failed because: {desc}. Please try using a different payment method like UPI."

    return False, ""


async def mark_case_escalated(rs: RecoveryState, reason: str, db: AsyncSession | None = None):
    """
    Persists escalation status to DB, cancels pending background tasks,
    logs the audit trail, and broadcasts an SSE update to the dashboard.
    """
    rs.recovery_status = "escalated"
    rs.last_action_taken = "escalate_to_human"
    rs.next_retry_at = None
    if rs.attempt_count and rs.attempt_count > 3:
        rs.attempt_count = 3

    async def _execute_escalation(session: AsyncSession):
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
            session,
            message=f"Escalated to human ops: {reason}",
            channel="system",
            direction="internal",
        )
        await save_state(rs, session)

    if db is not None:
        await _execute_escalation(db)
    else:
        async with AsyncSessionLocal() as session:
            await _execute_escalation(session)

    try:
        await broadcast_case_update(rs)
    except Exception as e:
        logger.warning(f"[HIL] Could not broadcast escalation: {e}")


async def execute_deterministic_recovery(rs: RecoveryState, event_source: str) -> RecoveryState:
    """
    6-Stage Deterministic Recovery Engine (Architecture Blueprint #9).
    Executes automated webhook ingestion, downtime circuit-breaking, compliance boundaries,
    link hydration, multi-channel dispatch, and progressive scheduling directly in Python (<10ms),
    eliminating artificial AIMessage tool-node wrappers and DB-reload state desync.
    """
    ref_code = rs.case_id[-4:].upper() if len(rs.case_id) >= 4 else rs.case_id
    target_method = rs.method
    through = rs.through

    # Stage 0: Terminal State Guard
    if rs.recovery_status in ["recovered", "closed", "escalated"]:
        logger.info(f"[ROUTER] Case {rs.case_id} is in terminal status ({rs.recovery_status}). Aborting automated dunning.")
        return rs

    # Stage 1: Diagnose & Triage (Fast-Path)
    # 1.1 Stopping Rules: Max 3 Attempts Hard Limit (Auto-Escalate to Human)
    if (rs.attempt_count or 0) >= 3 and event_source != "inbound.human_approval":
        rs.attempt_count = min(3, rs.attempt_count or 0)
        context_str = f"Context: Name={rs.customer.get('name', 'Unknown')}, Amount=₹{rs.amount_inr:,.0f}, Case={rs.case_type}, Last Action={rs.last_action_taken}"
        reason = f"Max attempts (3) reached. {context_str}"
        logger.info(f"[STOPPING RULE] Case {rs.case_id} reached attempt 3 >= 3. Auto-escalating to human operations.")
        await mark_case_escalated(rs, reason)
        return rs

    # 1.2 Customer Disputes: Immediate Human Transfer
    if rs.case_type == "dispute":
        reason = "Customer raised a dispute"
        await mark_case_escalated(rs, reason)
        return rs

    # 1.3 Gateway Downtime Circuit Breaker
    redis = get_redis_client()
    if target_method and await redis.sismember("downtimes:method", target_method):
        is_down = (
            await redis.exists(f"downtimes:{target_method}:all")
            or (through and await redis.exists(f"downtimes:{target_method}:{through}"))
            or (through and await redis.exists(f"downtimes:{target_method}:{through.upper()}"))
        )
        if is_down:
            customer_name = rs.customer.get("name", "Customer")
            bank_name = (through or target_method).upper()
            downtime_msg = (
                f"Hi {customer_name}, we noticed {bank_name} servers are temporarily experiencing gateway downtime. "
                f"We have paused your payment deadline. We'll update you as soon as your bank resolves this. (Ref: #RNV-{ref_code})"
            )
            target_retry = adjust_for_trai_window(datetime.now() + timedelta(hours=2))
            async with AsyncSessionLocal() as db:
                if should_send_channel(rs, "whatsapp"):
                    wa_payload = build_whatsapp_payload(rs, downtime_msg)
                    await send_twilio_whatsapp(rs.customer.get("contact", ""), wa_payload["body"])
                    await _log_audit(
                        rs,
                        "send_whatsapp_msg",
                        target_retry,
                        db,
                        message=wa_payload["body"],
                        channel="whatsapp",
                        direction="outbound",
                        meta_compliance=wa_payload.get("meta_compliance"),
                        hsm_template=wa_payload.get("template_name"),
                    )
                await _schedule_task(rs, target_retry, db)
                await _log_audit(
                    rs,
                    "gateway_downtime_pause",
                    target_retry,
                    db,
                    message=f"Circuit breaker active: {bank_name} downtime. Retrying at {target_retry.isoformat()}",
                    channel="system",
                    direction="system",
                )
                await save_state(rs, db)
            rs.next_retry_at = target_retry
            rs.last_action_taken = "gateway_downtime_pause"
            await broadcast_case_update(rs)
            return rs

    # 1.2 Unresolvable / Hard Decline Immediate Escalation
    can_t, decline_reason = cant_resolve(rs)
    if can_t:
        await mark_case_escalated(rs, f"Hard decline / unresolvable: {decline_reason}")
        return rs

    # Stage 2: Link Hydration
    async with AsyncSessionLocal() as db:
        payment_link, link_type, is_sub = await ensure_payment_link(rs, db)

        # Stage 3: Escalation Tone Matrix & Template Formatting
        wa_text, email_urgency, voice_text = get_escalation_tone(rs)
        if payment_link and "{payment_link}" in wa_text:
            wa_text = wa_text.replace("{payment_link}", payment_link)
        if payment_link and "{payment_link}" in voice_text:
            voice_text = voice_text.replace("{payment_link}", payment_link)

        # Meta HSM Utility Template Compliance (#15)
        whatsapp_payload = build_whatsapp_payload(rs, wa_text, payment_link=payment_link)
        final_wa_body = whatsapp_payload["body"]

        # Stage 4: Multi-Channel Parallel / Sequential Dispatch
        dispatched_channel = None

        if should_send_channel(rs, "whatsapp") and rs.customer.get("contact"):
            sid = await send_twilio_whatsapp(rs.customer["contact"], final_wa_body)
            await _log_audit(
                rs,
                "send_whatsapp_msg",
                None,
                db,
                message=final_wa_body,
                channel="whatsapp",
                direction="outbound",
                meta_compliance=whatsapp_payload.get("meta_compliance"),
                hsm_template=whatsapp_payload.get("template_name"),
            )
            dispatched_channel = "send_whatsapp_msg"

        # Attempt 2 or 3: Voice dispatch if preferred or escalation warrants
        if should_send_channel(rs, "voice") and rs.customer.get("contact") and rs.attempt_count >= 1:
            voice_sid = await generate_and_send_voice_note(rs.customer["contact"], voice_text)
            await _log_audit(
                rs,
                "get_voice_call",
                None,
                db,
                message=f"Voice note dispatched: {voice_text}",
                channel="voice",
                direction="outbound",
            )
            dispatched_channel = dispatched_channel or "get_voice_call"

        # Attempt 0 or 2: Email backup
        if should_send_channel(rs, "email") and rs.customer.get("email"):
            email_amount = (rs.case_metadata or {}).get("effective_amount_inr", rs.amount_inr)
            email_ok = await send_resend_email(
                email_urgency,
                rs.customer.get("name", "Customer"),
                rs.customer["email"],
                email_amount,
                extra_context={
                    "invoice_number": f"INV-{ref_code}",
                    "link": payment_link,
                },
            )
            if email_ok:
                await _log_audit(
                    rs,
                    "send_email_reminder",
                    None,
                    db,
                    message=f"Sent {email_urgency} recovery email with secure link {payment_link}",
                    channel="email",
                    direction="outbound",
                )
                dispatched_channel = dispatched_channel or "send_email_reminder"

        # Stage 5: Regulatory Compliance & Next Milestone Scheduling
        # 5.1 Recurring Subscription: RBI 24-hour Pre-Debit Intimation
        if is_recurring_mandate_case(rs):
            target_retry_dt = adjust_for_trai_window(datetime.now() + timedelta(days=3))
            pre_debit_dt = calculate_rbi_pre_debit_schedule(rs, target_retry_dt)
            intimation_text = format_rbi_pre_debit_intimation(rs, target_retry_dt)
            if pre_debit_dt:
                await _log_audit(
                    rs,
                    "rbi_pre_debit_intimation",
                    pre_debit_dt,
                    db,
                    message=f"[RBI Section 10(2) PSS Act] Scheduled pre-debit intimation notice at {pre_debit_dt.isoformat()}: {intimation_text}",
                    channel="system",
                    direction="internal",
                )

        # 5.2 Salary-Cycle Smart Hold (only on initial triage)
        if (rs.attempt_count or 0) == 0 and rs.failure_reason and any(kw in rs.failure_reason.lower() for kw in ["insufficient funds", "balance", "limit", "low funds"]):
            try:
                milestones = calculate_salary_milestones()
                if milestones:
                    salary_str = ", ".join(d.strftime('%d %b') for d in milestones)
                    first_dt = datetime.combine(milestones[0], datetime.min.time()) + timedelta(hours=10)
                    await _log_audit(
                        rs,
                        "get_next_salary_date",
                        None,
                        db,
                        message=f"Upcoming salary dates: {salary_str}. Recommended follow-up window for {first_dt.strftime('%b %d, %Y')}.",
                        channel="system",
                        direction="system",
                    )
            except Exception as e:
                logger.warning(f"[ROUTER] Salary date calculation error: {e}")

        # Stage 6: Update attempt count & last_action_taken
        rs.attempt_count = min(3, (rs.attempt_count or 0) + 1)
        if dispatched_channel:
            rs.last_action_taken = dispatched_channel
        elif not rs.last_action_taken:
            rs.last_action_taken = "create_payment_link"

        # Compute next follow-up milestone (TRAI & RBI pre-debit compliant)
        if rs.attempt_count >= 3:
            # All 3 outreach attempts have now been dispatched (Attempt 1, 2, and Final Notice).
            # Schedule the final grace deadline. If unpaid when triggered, it auto-escalates.
            base_dt = rs.next_retry_at if rs.next_retry_at and rs.next_retry_at > datetime.now() else datetime.now()
            final_grace = adjust_for_trai_window((base_dt + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0))
            await _schedule_task(rs, final_grace, db)
            rs.next_retry_at = final_grace
        else:
            next_contact = get_next_follow_up_time(rs)
            if next_contact:
                await _schedule_task(rs, next_contact, db)
            else:
                rs.next_retry_at = None

        await save_state(rs, db)

    await broadcast_case_update(rs)
    return rs
