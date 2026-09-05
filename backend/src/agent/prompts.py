"""
Renvue Conversational Prompt Templates & Escalation Copy Engine.
Provides dynamic escalation tones, B2B vs B2C dunning copy, and LLM system prompt construction.
"""

from datetime import datetime
from config.config import settings
from models.models import RecoveryState
from config.constants import hard_declines
from service.compliance import get_bell_curve_discount


def get_escalation_tone(rs: RecoveryState, attempt: int | None = None) -> tuple[str, str, str]:
    """
    Returns (whatsapp_msg, email_urgency, voice_msg) dynamically based on attempt_count,
    language (English/Hinglish), and case_type (B2C order vs B2B commercial invoice).
    Includes short reference ticket code (#RNV-XXXX) for multi-case disambiguation.
    """
    if attempt is None:
        attempt = rs.attempt_count or 1
    name = rs.customer.get("name", "Customer")
    amount_str = f"₹{rs.amount_inr:,.0f}"
    lang = getattr(rs, "language", "english").lower()
    ref_code = rs.case_id[-4:].upper() if len(rs.case_id) >= 4 else rs.case_id

    # Abandoned Checkout Recovery Path
    if rs.case_type == "abandoned_checkout":
        meta = rs.case_metadata or {}
        disc = meta.get("discount_pct") or meta.get("eligible_discount")
        if disc is None:
            disc = get_bell_curve_discount(rs)
        disc_val = float(disc) if disc else float(settings.min_discount)
        eff_amt = meta.get("effective_amount_inr")
        eff_amt_str = f"₹{eff_amt:,.0f}" if eff_amt else amount_str

        if lang == "hinglish":
            if attempt <= 1:
                wa_msg = f"Namaste {name} ji, aapka cart ({amount_str}) reserved hai. Reserved {disc_val:.0f}% discount ke saath apna order complete karein (Payable: {eff_amt_str}). Checkout link: {{payment_link}} (Ref: #RNV-{ref_code})"
            elif attempt == 2:
                wa_msg = f"Zaroori reminder: {name} ji, aapke cart ({amount_str}) par {disc_val:.0f}% reserved concession offer jald expire ho raha hai. Settle karein {eff_amt_str} yahan: {{payment_link}} (Ref: #RNV-{ref_code})"
            else:
                wa_msg = f"Aakhri notice: {name} ji, aapka reserved cart discount ({disc_val:.0f}%) expire ho raha hai. Complete purchase ({eff_amt_str}): {{payment_link}} (Ref: #RNV-{ref_code})"
            voice_msg = f"Namaste {name} ji, Renvue support se call hai. Aapke cart par special {disc_val:.0f}% discount reserve kiya gaya hai. Checkout link humne WhatsApp par share kar diya hai."
        else:
            if attempt <= 1:
                wa_msg = f"Hi {name}, you left items in your cart ({amount_str}). Complete checkout today with a reserved {disc_val:.0f}% discount (Payable: {eff_amt_str}): {{payment_link}} (Ref: #RNV-{ref_code})"
            elif attempt == 2:
                wa_msg = f"Reminder: {name}, your reserved {disc_val:.0f}% cart concession ({amount_str} -> {eff_amt_str}) expires within 24 hours. Complete order: {{payment_link}} (Ref: #RNV-{ref_code})"
            else:
                wa_msg = f"Final Reminder: {name}, this is your last chance to claim your reserved {disc_val:.0f}% discount on your cart. Checkout: {{payment_link}} (Ref: #RNV-{ref_code})"
            voice_msg = f"Hello {name}, this is Renvue customer concierge. We noticed you left items in your cart. We've reserved a {disc_val:.0f}% discount for you and sent the secure link to your WhatsApp. Thank you."

        email_urg = "cart_gentle" if attempt <= 1 else "cart_urgent" if attempt == 2 else "cart_final"
        return wa_msg, email_urg, voice_msg

    # B2B Corporate Invoice Path
    if rs.case_type == "overdue_invoice":
        meta = rs.case_metadata or {}
        inv_num = meta.get("invoice_number", f"INV-2026-{ref_code}")
        po_num = meta.get("po_number", f"PO-{ref_code}")
        if attempt <= 1:
            wa_msg = f"Dear Accounts Payable ({name}), courtesy reminder that Invoice {inv_num} ({amount_str}, PO: {po_num}) is overdue under Net-30 terms. If TDS (194C/J) has been deducted, please share Form 16A or settle via corporate portal. (Ref: #RNV-{ref_code})"
            email_urg = "b2b_gentle"
        elif attempt == 2:
            wa_msg = f"Attention Accounts Payable ({name}): URGENT - Overdue Invoice {inv_num} ({amount_str}). Account is scheduled for vendor hold within 48 hours unless payment UTR is provided or balance settled. (Ref: #RNV-{ref_code})"
            email_urg = "b2b_urgent"
        else:
            wa_msg = f"FINAL STATUTORY NOTICE: Commercial Invoice {inv_num} ({amount_str}) is unsettled. Account transferred to credit operations. (Ref: #RNV-{ref_code})"
            email_urg = "b2b_final"
        voice_msg = f"Hello {name}, this is Accounts Receivable regarding overdue commercial invoice {inv_num} for {amount_str}. Please review our email statement to prevent administrative hold. Thank you."
        return wa_msg, email_urg, voice_msg

    # Subscription Cancelled
    if rs.case_type == "subscription_cancelled":
        wa_msg = f"Your auto-pay was cancelled, but your {amount_str} instalment is still due. Would you like to settle manually? (Ref: #RNV-{ref_code})"
        email_urg = "gentle" if attempt <= 1 else "urgent" if attempt == 2 else "final"
        voice_msg = f"Hello {name}, your auto-debit was cancelled. Please complete payment using the link sent to your WhatsApp. Thank you."
        return wa_msg, email_urg, voice_msg

    # Soft Decline (Insufficient funds / Salary alignment)
    if rs.decline_type == "soft":
        if lang == "hinglish":
            if attempt <= 1:
                wa_msg = f"Namaste {name} ji, bank technical issue ki wajah se aapka {amount_str} ka payment complete nahi ho paya. Aapki booking reserved hai, retry karne ke liye link bhej rahe hain. (Ref: #RNV-{ref_code})"
            elif attempt == 2:
                wa_msg = f"Zaroori suchna: {name} ji, aapka {amount_str} ka payment abhi bhi pending hai. Cancellation se bachane ke liye please agle 24 ghante mein settle karein. (Ref: #RNV-{ref_code})"
            else:
                wa_msg = f"ANTIM NOTICE: {name} ji, {amount_str} payment ke liye yeh aakhri automated reminder hai. Account human operations ko handover ho raha hai. (Ref: #RNV-{ref_code})"
            voice_msg = f"Namaste {name} ji, Renvue support se bol rahe hain. Dekha ki aapka {amount_str} ka payment bank issue se ruk gaya tha. WhatsApp par direct link bhej diya hai, wahan se complete kar sakte hain."
        else:
            if attempt <= 1:
                wa_msg = f"Hi {name}, looks like your payment of {amount_str} didn't go through due to a temporary bank glitch. Your order is reserved. Tap the link to retry. (Ref: #RNV-{ref_code})"
            elif attempt == 2:
                wa_msg = f"Urgent Notice: {name}, your payment of {amount_str} remains pending. Please settle within 24 hours to avoid cancellation. (Ref: #RNV-{ref_code})"
            else:
                wa_msg = f"FINAL NOTICE: {name}, this is our last reminder for {amount_str}. Your account has been scheduled for administrative hold. (Ref: #RNV-{ref_code})"
            voice_msg = f"Hello {name}, this is Renvue customer support. We noticed your payment of {amount_str} was interrupted by a temporary bank error. We've reserved your order and sent a secure link to your WhatsApp to complete it. Thank you."
        email_urg = "gentle" if attempt <= 1 else "urgent" if attempt == 2 else "final"
        return wa_msg, email_urg, voice_msg

    # Card & Reconciliation Metadata
    details = rs.error_details or {}
    card_net = details.get("card_network")
    card_last4 = details.get("card_last4")
    card_str = f" on your {card_net} (••{card_last4})" if card_net and card_last4 else ""
    rrn = details.get("rrn")
    rrn_str = f" (Bank RRN: {rrn})" if rrn else ""

    # Hard Decline / Card Expired / Standard failure
    if lang == "hinglish":
        if attempt <= 1:
            wa_msg = f"Namaste {name} ji, aapka {amount_str} ka payment{card_str} complete nahi ho paya. Is secure link se new card ya UPI se complete karein.{rrn_str} (Ref: #RNV-{ref_code})"
        elif attempt == 2:
            wa_msg = f"Zaroori notice: {name} ji, {amount_str} ka payment pending hai. Subscription pause hone se bachane ke liye please payment method update karein. (Ref: #RNV-{ref_code})"
        else:
            wa_msg = f"Aakhri notice: {name} ji, {amount_str} settle nahi hua. Account suspend hone ja raha hai. (Ref: #RNV-{ref_code})"
        voice_msg = f"Namaste {name} ji, aapka {amount_str} ka payment complete nahi hua. Link humne WhatsApp par share kar diya hai, please update karein."
    else:
        if attempt <= 1:
            wa_msg = f"Hi {name}, your payment of {amount_str}{card_str} was declined. Tap the link to update your payment method or pay with UPI.{rrn_str} (Ref: #RNV-{ref_code})"
        elif attempt == 2:
            wa_msg = f"Urgent Notice: {name}, your payment of {amount_str} is overdue. Please update your payment method today to avoid service suspension. (Ref: #RNV-{ref_code})"
        else:
            wa_msg = f"FINAL NOTICE: {name}, outstanding payment of {amount_str} is unresolved. Your account has been transferred to support. (Ref: #RNV-{ref_code})"
        voice_msg = f"Hello {name}, this is Renvue support. Your transaction of {amount_str} was declined by the card network. A secure payment update link has been sent to your WhatsApp. Thank you."

    email_urg = "gentle" if attempt <= 1 else "urgent" if attempt == 2 else "final"
    return wa_msg, email_urg, voice_msg


def should_send_channel(rs: RecoveryState, channel: str) -> bool:
    """
    Determines whether a communication channel (email, whatsapp, voice) should be dispatched
    based on customer contact_preference, available contact details, and compliance rules.
    """
    pref = (getattr(rs, "contact_preference", None) or rs.customer.get("contact_preference", "")).lower()
    has_email = bool(rs.customer.get("email"))
    has_phone = bool(rs.customer.get("contact"))

    if channel == "email":
        if not has_email:
            return False
        # Overdue B2B invoices always need formal email dunning
        if rs.case_type == "overdue_invoice":
            return True
        # If customer explicitly prefers email, or has no phone, or attempt >= 2 (escalated outreach)
        return pref == "email" or not has_phone or (rs.attempt_count or 0) >= 2

    elif channel == "whatsapp":
        if not has_phone:
            return False
        # If customer explicitly prefers email and has valid email, respect opt-out on early attempts
        if pref == "email" and has_email and (rs.attempt_count or 0) < 2:
            return False
        return True

    elif channel == "voice":
        if not has_phone:
            return False
        # Compliance & TRAI DND rule: Never initiate unsolicited voice calls if customer opted for email or whatsapp
        if pref in ["email", "whatsapp"]:
            return False
        # Voice is only allowed for high-value debts (> 5k) where preference is 'call' or unconstrained
        return pref == "call" or ((rs.attempt_count or 0) >= 2 and rs.amount_inr > 5000)

    return False


def build_system_prompt(rs: RecoveryState) -> str:
    """
    Constructs the system prompt for LLM routing in decide_reply.
    Enforces stopping rules, multi-language/typo-resilient promise-to-pay extraction,
    cumulative grace period limits, tool-mediated discount evaluation,
    and B2B/B2C objection handling.
    """
    meta = rs.case_metadata or {}
    eligible_discount = meta.get("eligible_discount")
    discount_guidance = (
        f"Pre-approved concession ceiling: {eligible_discount}%."
        if eligible_discount is not None
        else "Call 'calculate_discount_offer' to check margin approval."
    )

    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    incident_date = meta.get("initial_failure_date") or (rs.first_seen_at.strftime('%Y-%m-%d') if rs.first_seen_at else today_str)
    cumulative_grace_used = meta.get("cumulative_grace_days_used", 0)
    remaining_grace = max(0, settings.max_grace_period - cumulative_grace_used)

    return f"""You are an empathetic, intelligent revenue recovery concierge for Renvue.
    
=== CURRENT CASE ===
Customer              : {rs.customer.get('name', 'Unknown')}
Amount owed           : ₹{rs.amount_inr:,.0f}
Case type             : {rs.case_type}
Attempt Count         : {rs.attempt_count}
Language              : {rs.language}
Today's Date          : {today_str}
Incident Date         : {incident_date}
Cumulative Grace Used : {cumulative_grace_used} days (Remaining grace: {remaining_grace} days)
Max Grace Period      : {settings.max_grace_period} days from incident
Max Discount          : {settings.max_discount}%
Min Discount          : {settings.min_discount}%

=== CORE RECOVERY RULES ===
1. STOPPING RULE: If Attempt Count >= 3 (and not explicitly authorized by human approval), you MUST call 'escalate_to_human' and STOP. If Human Approved, proceed with the requested recovery action.

2. PROMISE TO PAY & CUSTOMER COMMITMENTS:
   - Customers may respond in ANY language (English, Hindi, Hinglish, Tamil, etc.) or informal text with typos and slang (e.g., "5th of spet", "kal pay kar dunga", "will clear this friday", "parso karta hu", "pay on 10th").
   - Intelligently extract the customer's intended commitment date:
     * Today's reference date is {today_str}.
     * Resolve typos and slang (e.g., "5th of spet" -> {now.year}-09-05, "tomrw" -> tomorrow, "kal" -> tomorrow, "parso" -> +2 days) into the ISO format YYYY-MM-DD.
   - Policy & Grace Period Validation:
     * Check if the date is in the past (< Today) or exceeds the cumulative policy grace period of {settings.max_grace_period} days from the original incident date ({incident_date}).
     * When a customer specifies a date, call 'log_promise_to_pay(date_str="YYYY-MM-DD", reason=..., sentiment=...)'.
   - If NO specific date could be extracted, or customer is vague (e.g., "I will pay soon", "give me time", or ambiguous typo):
     * DO NOT escalate to human operations for minor typos or lack of a date!
     * Call 'log_promise_to_pay(date_str=None, reason=..., sentiment=...)'. The system will automatically schedule standard follow-up (+3 days from now).

3. NEGOTIATION & DISCOUNTS: If abandoned checkout and customer hesitates, objects to price, or asks for a concession:
   - You MUST call 'calculate_discount_offer' to obtain deterministic margin approval ({discount_guidance}).
   - NEVER invent or promise a discount percentage without calling 'calculate_discount_offer'.
   - Once approved, call 'create_payment_link(discount_pct=...)' with the approved discount percentage to generate the discounted checkout link.

4. OUTREACH: If customer asks a question or replies, use 'send_whatsapp_msg' to reply. Any payment link generated will automatically be attached to your message. You may also explicitly position it using the placeholder '{{payment_link}}'.

5. ESCALATION: Call 'escalate_to_human' ONLY if:
   - Customer is hostile, threatening, or abusive.
   - Customer explicitly refuses to pay ("I will never pay", "sue me").
   - Customer proposes a date far in the past or absurdly out-of-bounds (e.g. year 2078) to deliberately evade payment, or cumulative grace period is exhausted.
   - Attempt Count >= 3 (and not explicitly authorized by human approval).
   DO NOT escalate for polite negotiation, minor typos, or normal questions.

=== B2B COMMERCIAL INVOICE RULES ===
- If Case type is 'overdue_invoice': You are communicating with an Accounts Payable (AP) / Finance Manager. Maintain formal corporate finance decorum.
- If they mention TDS deduction (Section 194C 2% or 194J 10%) or Form 16A, acknowledge it and request the TDS challan / certificate.
- If they state 'cheque will be issued Friday' or 'payment runs on 10th', record this via 'log_promise_to_pay' and thank them for confirming the billing cycle.

=== PAYMENT CONCIERGE & OBJECTION FAQ ===
- Double-Debit / Money Deducted Fear: If customer states money was deducted from bank but order failed, reassure them warmly: 'If your bank debited the amount, RBI rules mandate an auto-reversal within T+2 to T+5 working days, or Razorpay will auto-reconcile within 2 hours. If not settled, please share the bank UTR so our finance desk can claim it immediately.'
- UPI / Mandate Guidance: If customer asks how to approve UPI autopay, instruct them to open Google Pay / PhonePe / Paytm and tap 'Autopay' or 'Mandates' to authorize with UPI PIN.
- Link Safety: If customer questions link legitimacy, assure them that the payment link is served on official Razorpay PCI-DSS Level 1 compliant infrastructure (rzp.io) with 128-bit bank-grade encryption.
- Tone Progression:
  * Attempt 1: Helpful concierge, assuming technical bank glitch.
  * Attempt 2: Firm and urgent, warning of 24-hour service suspension.
  * Attempt 3: Final notice before account transfer to human operations.

=== OUTPUT FORMAT RULES ===
- NEVER output placeholder template brackets like '[Service/Subscription]', '[Product Name]', '[Insert Link]', '[Your Company]'.
- Refer to the transaction naturally as 'your order' or 'your subscription'.
- Keep replies concise, professional, and ready for immediate customer delivery.
"""
