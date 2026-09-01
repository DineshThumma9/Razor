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


async def _schedule_task(state, target_date: datetime, db):
    from background.worker import invoke_agent_task, revoke_active_task, broker
    
    if state.active_task_id:
        await revoke_active_task(state.active_task_id)

    now = datetime.now()
    delta_seconds = (target_date - now).total_seconds()
    if delta_seconds < 0:
        delta_seconds = 60

    # Ensure broker is connected (important when called from within a worker task)
    if broker.connection_pool is None:
        await broker.startup()

    task = await invoke_agent_task.kiq(state.case_id)
    # Note: For Taskiq, we don't have task.id on kiq immediately in the same way as Celery, but taskiq returns a TaskiqResult
    state.active_task_id = task.task_id
    await save_state(state, db)


async def _log_audit(state, tool_name: str, next_retry_at: datetime, db):
    entry = AuditEntry(
        event_triggered=tool_name,
        amount=str(state.amount_inr),
        recovery_status=state.recovery_status,
        customer=state.customer,
        next_contact=next_retry_at,
    )
    state.audit_log.append(entry.model_dump(mode="json"))
    if next_retry_at:
        state.next_retry_at = next_retry_at
    await save_state(state, db)


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

        print(f"\n  [TOOL] send_email_reminder")
        print(f"    → To      : {customer_name} <{customer_email}>")
        print(f"    → Amount  : ₹{amount_inr}")
        print(f"    → Urgency : {urgency}")

        await send_resend_email(urgency, customer_name, customer_email, amount_inr)

        if state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            next_contact = datetime.now() + timedelta(days=3)
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

        print(f"\n  [TOOL] create_payment_link")

        short_url = await create_rzp_payment_link(
            customer_name, customer_email, customer_contact, amount_inr
        )
        print(f"    → Link     : {short_url}")

        if state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            next_contact = datetime.now() + timedelta(days=1)
            await _schedule_task(state, next_contact, db)

        await _log_audit(state, "create_payment_link", next_contact, db)

    return short_url


@tool(args_schema=EscalateArgs)
async def escalate_to_human(reason: str, config: RunnableConfig) -> str:
    """
    Escalate this case to a human agent.
    Use when: hard decline after payment link sent, dispute raised,
    3+ failed attempts, or legal action needed.
    """
    case_id = config.get("configurable", {}).get("thread_id")
    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        customer_name = state.customer.get("name", "Customer")

        print(f"\n  [TOOL] escalate_to_human")
        print(f"    → Customer : {customer_name}")
        print(f"    → Reason   : {reason}")

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

    ref = date.today()
    year, month = ref.year, ref.month

    milestones = []
    for day in [1, 15]:
        d = date(year, month, day)
        if d > ref:
            milestones.append(d)

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

    async with app_db.AsyncSessionLocal() as db:
        state = await load_state(case_id, db)
        await _schedule_task(state, target_time, db)
        await _log_audit(state, "get_next_salary_date", target_time, db)

    print(f"\n  [TOOL] get_next_salary_date")
    print(f"    → Upcoming milestones: {result}. Scheduled retry for {target_time}.")

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

        if state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            next_contact = datetime.now() + timedelta(days=3)
            await _schedule_task(state, next_contact, db)

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

        if state.next_retry_at and state.next_retry_at > datetime.now():
            next_contact = state.next_retry_at
        else:
            next_contact = datetime.now() + timedelta(days=2)
            await _schedule_task(state, next_contact, db)

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
        target_date = datetime.fromisoformat(date_str)
        if not sanity_date(target_date):
            return await escalate_to_human.ainvoke(
            {
                "reason": f"Customer promised to pay on {date_str} but was {sentiment}. Reason: {reason} which doesnt seem realistic possible"
            },
            config=config,
        )

        await _schedule_task(state, target_date, db)
        await _log_audit(state, "log_promise_to_pay", target_date, db)

    return f"Successfully logged promise to pay on {date_str}. Let the user know it is confirmed."


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
