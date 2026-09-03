import asyncio
import calendar
from datetime import date, datetime, timedelta

from config.clients import (
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


async def _log_audit(state, tool_name: str, next_retry_at: datetime, db):
    entry = AuditEntry(
        event_triggered=tool_name,
        amount=str(state.amount_inr),
        recovery_status=state.recovery_status,
        customer=state.customer,
        next_contact=next_retry_at,
    )
    state.audit_log.append(entry.model_dump(mode="json"))
    logger.info(f"  [LOG_AUDIT] tool={tool_name} next_retry_at_param={next_retry_at} state.next_retry_at_before={state.next_retry_at}")
    if next_retry_at:
        state.next_retry_at = next_retry_at
    if tool_name in ["send_whatsapp_msg", "send_email_reminder", "get_voice_call", "escalate_to_human"]:
        state.last_action_taken = tool_name
    logger.info(f"  [LOG_AUDIT] after set → state.next_retry_at={state.next_retry_at} last_action={state.last_action_taken}")
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

        await send_resend_email(urgency, customer_name, customer_email, amount_inr)

        if state.attempt_count == 0 and state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            base_time = max(datetime.now(), state.next_retry_at) if state.next_retry_at else datetime.now()
            next_contact = base_time + timedelta(days=3)
        await _schedule_task(state, next_contact, db)

        await _log_audit(state, "send_email_reminder", next_contact, db)

    return f"Email ({urgency}) queued for {customer_email}"


@tool(args_schema=PaymentLinkArgs)
async def create_payment_link(config: RunnableConfig) -> str:
    """
    Create a Razorpay payment link for the customer to complete payment.
    Use this for hard declines (expired card, lost card) where the customer must re-enter card details.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        customer_name = state.customer.get("name", "Customer")
        customer_email = state.customer.get("email", "")
        customer_contact = state.customer.get("contact", "")
        amount_inr = state.amount_inr

        logger.info(f"\n  [TOOL] create_payment_link")

        short_url = await create_rzp_payment_link(
            customer_name, customer_email, customer_contact, amount_inr
        )
        logger.info(f"    → Link     : {short_url}")

        if state.attempt_count == 0 and state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            base_time = max(datetime.now(), state.next_retry_at) if state.next_retry_at else datetime.now()
            next_contact = base_time + timedelta(days=1)
        try:
            await _schedule_task(state, next_contact, db)
        except Exception as e:
            logger.info(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")

        await _log_audit(state, "create_payment_link", next_contact, db)

    return f"Payment link generated: {short_url}"


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
        await _log_audit(state, "escalate_to_human", None, db)

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
        await _log_audit(state, "get_next_salary_date", target_time, db)

    logger.info(f"\n  [TOOL] get_next_salary_date")
    logger.info(f"    → Upcoming milestones: {result}. Scheduled retry for {target_time}.")

    return result


@tool(args_schema=CompleteCaseArgs)
async def complete_case(summary: str) -> str:
    """
    Call this tool when you have finished taking all necessary actions for this case.
    This tells the system to stop the workflow and move to the audit phase.
    """
    print(f"\n  [TOOL] complete_case")
    print(f"    → Summary : {summary}")
    return "Case workflow completed."


@tool
async def send_whatsapp_msg(msg: str, config: RunnableConfig):
    """
    Sends a WhatsApp message to the customer using Twilio.
    msg is the content of the message.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        contact_number = state.customer.get("contact", "")

        if not contact_number:
            return "Failed: Customer has no contact number."

        sid = await send_twilio_whatsapp(contact_number, msg)
        print(f"Message dispatched successfully! SID: {sid}")

        if state.attempt_count == 0 and state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            base_time = max(datetime.now(), state.next_retry_at) if state.next_retry_at else datetime.now()
            next_contact = base_time + timedelta(days=3)

        try:
            await _schedule_task(state, next_contact, db)
        except Exception as e:
            print(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")

        await _log_audit(state, "send_whatsapp_msg", next_contact, db)

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

        if state.attempt_count == 0 and state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            base_time = max(datetime.now(), state.next_retry_at) if state.next_retry_at else datetime.now()
            next_contact = base_time + timedelta(days=2)

        try:
            await _schedule_task(state, next_contact, db)
        except Exception as e:
            print(f"    [WARN] Failed to schedule follow-up task (non-fatal): {e}")

        await _log_audit(state, "get_voice_call", next_contact, db)

    return f"Voice note dispatched successfully to {contact_number}! SID: {sid}"




def sanity_date(date:datetime):

    if date < datetime.today():
        return False 
    if abs(date.year-datetime.now().year) >= 1:
        return False 
    
    return True

@tool(args_schema=PromiseToPayArgs)
async def log_promise_to_pay(
    date_str: str, reason: str, sentiment: str, config: RunnableConfig
):
    """
    Call this tool when a customer replies via email or WhatsApp and promises to pay
    on a specific future date. This will log their promise and pause all automated
    reminders until that date.
    """
    case_id = config.get("configurable", {}).get("thread_id")

    if sentiment.lower() in ["angry", "upset", "frustrated"]:
        # Don't log a promise, immediately escalate to human
        # NOTE: invoke the async function
        return await escalate_to_human.ainvoke(
            {
                "reason": f"Customer promised to pay on {date_str} but was {sentiment}. Reason: {reason}"
            },
            config=config,
        )

    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        try:
            target_date = datetime.fromisoformat(date_str)
        except Exception:
            target_date = datetime.now() + timedelta(days=3)

        if not sanity_date(target_date):
            return await escalate_to_human.ainvoke(
            {
                "reason": f"Customer promised to pay on {date_str} but was {sentiment}. Reason: {reason} which doesnt seem realistic possible"
            },
            config=config,
        )

        await _schedule_task(state, target_date, db)

        # Send confirmation message directly to customer
        confirm_msg = f"Thank you! We have noted your promise to pay on {target_date.strftime('%Y-%m-%d')}. Automated reminders are paused until then."
        contact_number = state.customer.get("contact", "")
        if contact_number:
            await send_twilio_whatsapp(contact_number, confirm_msg)

        await _log_audit(state, "log_promise_to_pay", target_date, db)

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
