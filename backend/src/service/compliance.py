"""
Renvue Compliance & Regulatory Guardrail Engine.

Implements:
1. TRAI Operating Window (9:00 AM - 9:00 PM IST) under TCCCPR telecom guidelines.
2. RBI 24-Hour Pre-Debit Intimation Rule under Section 10(2) Payment and Settlement Systems Act (PSS Act).
3. Meta WhatsApp 24-Hour Customer Care Window & HSM Utility Template Compliance.
"""

import calendar
from datetime import date, datetime, time, timedelta
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from config.config import settings
from config.logger import get_logger
from models.models import RecoveryState

logger = get_logger(__name__)

# TRAI Telecom Commercial Communications Customer Preference Regulations (TCCCPR)
TRAI_START_TIME = time(9, 0)   # 9:00 AM
TRAI_END_TIME = time(21, 0)    # 9:00 PM


# =====================================================================
# 1. TRAI Operating Window Guardrail (9:00 AM – 9:00 PM)
# =====================================================================

def is_within_trai_window(dt: Optional[datetime] = None) -> bool:
    """
    Checks if given timestamp (defaults to now) falls within the permitted
    TRAI communication window (09:00 to 21:00).
    """
    check_dt = dt or datetime.now()
    current_time = check_dt.time()
    return TRAI_START_TIME <= current_time < TRAI_END_TIME


def adjust_for_trai_window(dt: datetime) -> datetime:
    """
    Adjusts a target contact timestamp so it strictly falls within the
    TRAI 9:00 AM - 9:00 PM operating window:
    - Before 9:00 AM: snaps to today at 09:05 AM.
    - At or after 9:00 PM: snaps to next day at 09:05 AM.
    - Within 9:00 AM - 9:00 PM: preserves target time.
    """
    target_time = dt.time()
    if target_time < TRAI_START_TIME:
        return dt.replace(hour=9, minute=5, second=0, microsecond=0)
    elif target_time >= TRAI_END_TIME:
        next_day = dt + timedelta(days=1)
        return next_day.replace(hour=9, minute=5, second=0, microsecond=0)
    return dt


# =====================================================================
# 2. RBI 24-Hour Pre-Debit Intimation Rule (Section 10(2) PSS Act)
# =====================================================================

def is_recurring_mandate_case(state: RecoveryState) -> bool:
    """
    Determines if this case involves a recurring AutoPay / e-mandate under RBI circulars.
    Applies to subscription retries, tokenized mandate updates, and subscription halt events.
    """
    meta = state.case_metadata or {}
    return (
        state.case_type in ["failed_subscription", "subscription_cancelled"]
        or bool(meta.get("mandate_update"))
        or bool(meta.get("sub_card_change"))
        or str(state.source_id or "").startswith("sub_")
    )


def calculate_rbi_pre_debit_schedule(
    state: RecoveryState,
    retry_target: datetime,
) -> Optional[datetime]:
    """
    Under RBI e-mandate guidelines (Section 10(2) PSS Act):
    For recurring debits, an automated pre-debit intimation MUST be dispatched
    at least 24 hours prior to actual auto-debit retry execution (T - 24h).

    Returns the computed pre-debit intimation timestamp (adjusted for TRAI window),
    or None if this is not a recurring mandate case.
    """
    if not is_recurring_mandate_case(state):
        return None

    now = datetime.now()
    # At least 24 hours required prior to debit retry
    raw_pre_debit = retry_target - timedelta(hours=24)
    if raw_pre_debit <= now:
        # If retry is less than 24h away, pre-debit notification must be sent immediately (in window)
        pre_debit_time = adjust_for_trai_window(now)
    else:
        pre_debit_time = adjust_for_trai_window(raw_pre_debit)

    return pre_debit_time


def format_rbi_pre_debit_intimation(
    state: RecoveryState,
    debit_date: datetime,
    payment_link: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Generates an RBI-compliant pre-debit intimation message and structured metadata.
    """
    name = state.customer.get("name", "Customer")
    amount_str = f"₹{state.amount_inr:,.0f}"
    sub_id = state.source_id or state.case_id[-8:]
    date_str = debit_date.strftime("%d %b %Y at %I:%M %p")
    ref_code = state.case_id[-4:].upper() if len(state.case_id) >= 4 else state.case_id

    link_str = f"\n\nManage / Update AutoPay: {payment_link}" if payment_link else ""

    message = (
        f"RBI MANDATE PRE-DEBIT NOTICE: Dear {name}, as required under RBI Section 10(2) PSS Act, "
        f"your account will be auto-debited for {amount_str} on {date_str} for recurring plan ({sub_id}). "
        f"Ensure sufficient balance.{link_str} (Ref: #RNV-{ref_code})"
    )

    metadata = {
        "pss_act_section": "10(2)",
        "regulation": "RBI/2020-21/74 DPSS.CO.PD.No.750/02.14.003/2020-21",
        "pre_debit_required": True,
        "scheduled_debit_at": debit_date.isoformat(),
        "subscription_id": sub_id,
        "compliance_verified": True,
    }

    return message, metadata


# =====================================================================
# 3. Meta WhatsApp 24-Hour Window & HSM Utility Template Compliance
# =====================================================================

class WhatsAppHSMTemplate:
    """Pre-approved Meta WhatsApp Utility / Authentication HSM Template definitions."""
    PAYMENT_REMINDER = "renvue_payment_reminder_utility"
    RBI_PRE_DEBIT = "renvue_pre_debit_intimation"
    INVOICE_OVERDUE = "renvue_invoice_overdue_notice"
    CHECKOUT_RECOVERY = "renvue_checkout_recovery_utility"


def has_active_whatsapp_session(state: RecoveryState, max_window_hours: int = 24) -> bool:
    """
    Verifies if the customer sent an inbound WhatsApp message within the last 24 hours,
    which opens Meta's free-form customer service window.
    """
    if not state.audit_log:
        return False

    now = datetime.now()
    threshold = now - timedelta(hours=max_window_hours)

    for entry in reversed(state.audit_log):
        if (
            entry.get("channel") == "whatsapp"
            and entry.get("direction") == "inbound"
        ):
            created_at_raw = entry.get("created_at")
            if created_at_raw:
                try:
                    if isinstance(created_at_raw, str):
                        created_dt = datetime.fromisoformat(created_at_raw)
                    else:
                        created_dt = created_at_raw
                    if created_dt >= threshold:
                        return True
                except Exception:
                    pass
    return False


def build_whatsapp_payload(
    state: RecoveryState,
    raw_message: str,
    payment_link: Optional[str] = None,
    is_inbound_reply: bool = False,
) -> Dict[str, Any]:
    """
    Applies Meta WhatsApp Business API compliance rules:
    - If customer sent an inbound message within 24 hours: allows conversational free-form text.
    - If outside 24 hours (cold outbound / automated webhook): structures the message into
      a pre-approved Meta HSM Utility Template with positional parameters.
    """
    name = state.customer.get("name", "Customer")
    amount_str = f"₹{state.amount_inr:,.0f}"
    ref_code = state.case_id[-4:].upper() if len(state.case_id) >= 4 else state.case_id
    meta = state.case_metadata or {}
    effective_link = payment_link or meta.get("payment_link", "")

    # Hydrate {payment_link} placeholder in conversational/raw messages
    if effective_link and "{payment_link}" in raw_message:
        raw_message = raw_message.replace("{payment_link}", effective_link)

    # Check 24-hour customer care window
    is_in_window = is_inbound_reply or has_active_whatsapp_session(state)

    if is_in_window:
        logger.info(f"[WHATSAPP COMPLIANCE] Active 24h session verified for case {state.case_id}. Free-form text permitted.")
        return {
            "mode": "freeform_session",
            "body": raw_message,
            "template_name": None,
            "category": "CUSTOMER_SERVICE",
            "is_hsm": False,
            "meta_compliance": "ACTIVE_24H_WINDOW",
        }

    # Cold outbound -> Strict HSM Utility Template required
    logger.info(f"[WHATSAPP COMPLIANCE] Cold outbound for case {state.case_id}. Enforcing pre-approved Meta HSM Utility Template.")

    if state.case_type == "overdue_invoice":
        template_name = WhatsAppHSMTemplate.INVOICE_OVERDUE
        inv_num = meta.get("invoice_number", f"INV-2026-{ref_code}")
        params = [name, inv_num, amount_str, effective_link or f"https://rzp.io/l/inv-{ref_code.lower()}", ref_code]
        rendered_body = (
            f"Dear Accounts Payable ({name}), courtesy reminder that Invoice {inv_num} ({amount_str}) "
            f"is overdue. Pay securely: {effective_link or 'Portal'}. (Ref: #RNV-{ref_code})"
        )
    elif state.case_type == "abandoned_checkout":
        template_name = WhatsAppHSMTemplate.CHECKOUT_RECOVERY
        disc = meta.get("discount_pct") or meta.get("eligible_discount")
        eff_amt = meta.get("effective_amount_inr")
        disc_text = f" ({disc:.0f}% off, now ₹{eff_amt:,.0f})" if disc and eff_amt else (f" ({disc:.0f}% off)" if disc else "")
        params = [name, amount_str, effective_link, ref_code]
        rendered_body = (
            f"Hi {name}, you left items in your cart ({amount_str}). "
            f"Complete checkout with your reserved discount{disc_text}: {effective_link}. (Ref: #RNV-{ref_code})"
        )
    elif is_recurring_mandate_case(state) and "RBI" in raw_message:
        template_name = WhatsAppHSMTemplate.RBI_PRE_DEBIT
        sub_id = state.source_id or state.case_id[-8:]
        target_date = (state.next_retry_at or datetime.now()).strftime("%d %b %Y")
        params = [name, amount_str, target_date, sub_id, ref_code]
        rendered_body = raw_message
    else:
        template_name = WhatsAppHSMTemplate.PAYMENT_REMINDER
        params = [name, amount_str, effective_link or "Payment Link", ref_code]
        rendered_body = raw_message

    return {
        "mode": "hsm_utility",
        "body": rendered_body,
        "template_name": template_name,
        "category": "UTILITY",
        "parameters": params,
        "is_hsm": True,
        "meta_compliance": "UTILITY_HSM_COMPLIANT",
    }


# =====================================================================
# 4. Shared Salary Milestone Calculation
# =====================================================================

def calculate_salary_milestones(ref_date: Optional[date] = None) -> list[date]:
    """
    Returns upcoming salary milestone dates (1st, 15th, and last Friday of the month).
    If no remaining milestones in current month, rolls to 1st of next month.
    """
    ref = ref_date or date.today()
    year, month = ref.year, ref.month
    milestones: list[date] = []

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

    return milestones


# =====================================================================
# 5. Margin-Safe Bell-Curve Discount Policy & Anti-Gaming
# =====================================================================

def get_bell_curve_discount(state: RecoveryState) -> float:
    """
    Evaluates and idempotently locks a right-skewed bell-curve discount for the case.
    Protects margins so that the vast majority receive low/baseline concessions:
      - 65% get settings.min_discount (e.g. 5%)
      - 22% get a modest incentive (e.g. 10%)
      - 10% get a high incentive (e.g. 15% - 20%)
      -  3% get the rare maximum tail (up to settings.max_discount, e.g. 25% - 30%)

    Anti-Gaming: Idempotently locks the approved discount into state.case_metadata["eligible_discount"].
    Subsequent haggles by the customer return this pre-locked ceiling.
    """
    meta = state.case_metadata or {}
    if "eligible_discount" in meta:
        return float(meta["eligible_discount"])

    # Disallow discounts on corporate invoices or recurring mandate renewals
    if state.case_type not in ["abandoned_checkout"]:
        return 0.0

    min_d = float(settings.min_discount)
    max_d = float(settings.max_discount)
    roll = random.random()

    if roll < 0.65:
        discount = min_d
    elif roll < 0.87:
        mid_low = min_d + (max_d - min_d) * 0.25
        discount = round(random.uniform(min_d, mid_low), 0)
    elif roll < 0.97:
        mid_low = min_d + (max_d - min_d) * 0.25
        mid_high = min_d + (max_d - min_d) * 0.60
        discount = round(random.uniform(mid_low, mid_high), 0)
    else:
        mid_high = min_d + (max_d - min_d) * 0.60
        discount = round(random.uniform(mid_high, max_d), 0)

    discount = max(min_d, min(discount, max_d))
    if state.case_metadata is None:
        state.case_metadata = {}
    state.case_metadata["eligible_discount"] = discount
    return discount
