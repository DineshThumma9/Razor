from datetime import datetime, date, timedelta
import calendar
from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Tool: send_email_reminder
# ---------------------------------------------------------------------------

@tool
def send_email_reminder(customer_name: str, customer_email: str, amount_inr: float, urgency: str) -> str:
    """
    Send a recovery email to the customer.
    urgency must be one of: 'gentle', 'urgent', 'final'.
    Returns a confirmation string.
    """
    print(f"\n[TOOL] send_email_reminder")
    print(f"  → To      : {customer_name} <{customer_email}>")
    print(f"  → Amount  : ₹{amount_inr}")
    print(f"  → Urgency : {urgency}")
    # In production: call Resend / SendGrid here
    return f"Email ({urgency}) sent to {customer_email}"


# ---------------------------------------------------------------------------
# Tool: create_payment_link
# ---------------------------------------------------------------------------

@tool
def create_payment_link(customer_name: str, customer_email: str, customer_contact: str, amount_paise: int) -> str:
    """
    Create a Razorpay payment link and return the short URL.
    amount_paise is the amount in paise (₹1 = 100 paise).
    """
    print(f"\n[TOOL] create_payment_link")
    print(f"  → Customer : {customer_name}")
    print(f"  → Amount   : ₹{amount_paise / 100:.2f}")
    # In production: call razorpay client here
    fake_url = f"https://rzp.io/l/recovery-{customer_email.split('@')[0]}"
    print(f"  → Link     : {fake_url}")
    return fake_url


# ---------------------------------------------------------------------------
# Tool: escalate_to_human
# ---------------------------------------------------------------------------

@tool
def escalate_to_human(customer_name: str, reason: str) -> str:
    """
    Escalate this case to a human agent.
    Use this when: hard decline, customer unresponsive after 3 attempts,
    dispute raised, or legal action needed.
    """
    print(f"\n[TOOL] escalate_to_human")
    print(f"  → Customer : {customer_name}")
    print(f"  → Reason   : {reason}")
    return f"Case for {customer_name} escalated. Reason: {reason}"


# ---------------------------------------------------------------------------
# Tool: log_audit_entry
# ---------------------------------------------------------------------------

@tool
def log_audit_entry(action: str, result: str, next_retry_days: int = 0) -> str:
    """
    Log what action was taken and what the result was.
    Always call this after every action to maintain the audit trail.
    next_retry_days: how many days until the next retry (0 = no retry scheduled).
    """
    now = datetime.now()
    next_contact = (now + timedelta(days=next_retry_days)).isoformat() if next_retry_days > 0 else "None"
    print(f"\n[TOOL] log_audit_entry")
    print(f"  → Action      : {action}")
    print(f"  → Result      : {result}")
    print(f"  → Logged at   : {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  → Next contact: {next_contact}")
    return f"Audit logged: {action} | {result} | next_contact={next_contact}"


# ---------------------------------------------------------------------------
# Tool: get_next_salary_date
# ---------------------------------------------------------------------------

@tool
def get_next_salary_date(reference_date_iso: str = "") -> str:
    """
    Returns upcoming salary milestone dates (1st, 15th, last Friday of month)
    relative to today or a given ISO date string (YYYY-MM-DD).
    Use this to decide when to schedule the next retry for a soft decline.
    """
    ref = date.fromisoformat(reference_date_iso) if reference_date_iso else date.today()
    year, month = ref.year, ref.month

    milestones = []

    for day in [1, 15]:
        d = date(year, month, day)
        if d >= ref:
            milestones.append(d)

    # Last Friday of the month
    last_day = calendar.monthrange(year, month)[1]
    last_date = date(year, month, last_day)
    offset = (last_date.weekday() - 4) % 7
    last_friday = last_date - timedelta(days=offset)
    if last_friday >= ref:
        milestones.append(last_friday)

    milestones = sorted(set(milestones))

    if not milestones:
        # Roll to next month's 1st
        if month == 12:
            next_first = date(year + 1, 1, 1)
        else:
            next_first = date(year, month + 1, 1)
        milestones = [next_first]

    result = ", ".join(str(d) for d in milestones)
    print(f"\n[TOOL] get_next_salary_date")
    print(f"  → Upcoming milestones: {result}")
    return result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

tools = [
    send_email_reminder,
    create_payment_link,
    escalate_to_human,
    log_audit_entry,
    get_next_salary_date,
]
