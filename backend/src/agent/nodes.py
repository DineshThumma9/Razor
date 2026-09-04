from datetime import timedelta
import uuid
import random
import asyncio
import operator
from datetime import datetime
from typing import Annotated, Sequence, TypedDict
import json
import logging
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
from langgraph.prebuilt import ToolNode
from langchain_mistralai import ChatMistralAI
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from config.config import settings
from config.clients import get_redis_client
from config.constants import hard_declines
import config.db
from models.models import RecoveryState
from service.states import save_state
from agent.tools import tools


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    recovery_state: RecoveryState
    event_source: str


def get_discount():    
    prob = random.random()
    discounted = 0
    if prob <= 0.3:
        discounted = settings.max_discount 
    elif prob <= 0.7:
        discounted = random.randint(settings.min_discount, max(settings.min_discount, settings.max_discount-5))
    elif prob <= 1:
        discounted = settings.min_discount

    return discounted


def cant_resolve(rs: RecoveryState):
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


def get_escalation_tone(rs: RecoveryState) -> tuple[str, str, str]:
    """
    Returns (whatsapp_msg, email_urgency, voice_msg) dynamically based on attempt_count,
    language (English/Hinglish), and case_type (B2C order vs B2B commercial invoice).
    Includes short reference ticket code (#RNV-XXXX) for multi-case disambiguation.
    """
    attempt = rs.attempt_count or 1
    name = rs.customer.get("name", "Customer")
    amount_str = f"₹{rs.amount_inr:,.0f}"
    lang = getattr(rs, "language", "english").lower()
    ref_code = rs.case_id[-4:].upper() if len(rs.case_id) >= 4 else rs.case_id

    # B2B Corporate Invoice Path
    if rs.case_type == "overdue_invoice":
        inv_num = rs.error_details.get("invoice_number", f"INV-2026-{ref_code}")
        po_num = rs.error_details.get("po_number", f"PO-{ref_code}")
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
    card_net = rs.error_details.get("card_network")
    card_last4 = rs.error_details.get("card_last4")
    card_str = f" on your {card_net} (••{card_last4})" if card_net and card_last4 else ""
    rrn = rs.error_details.get("rrn")
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


logger = logging.getLogger("renvue.nodes")

async def mark_case_escalated(rs: RecoveryState, reason: str):
    """
    Persists escalation status to DB, cancels pending background tasks,
    logs the audit trail, and broadcasts an SSE update to the dashboard.
    """
    rs.recovery_status = "escalated"
    rs.last_action_taken = "escalate_to_human"
    rs.next_retry_at = None

    async with config.db.AsyncSessionLocal() as db:
        if getattr(rs, "active_task_id", None):
            try:
                from background.worker import revoke_active_task
                await revoke_active_task(rs.active_task_id)
                rs.active_task_id = None
            except Exception as e:
                logger.warning(f"[HIL] Could not revoke task: {e}")

        from agent.tools import _log_audit
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


async def decide_event(state: AgentState):
    """
    Phase 1: Deterministic fast-path for standard automated cases.
    """
    rs = state["recovery_state"]
    tools_to_call = []

    target_method = rs.method 
    through = rs.through
    ref_code = rs.case_id[-4:].upper() if len(rs.case_id) >= 4 else rs.case_id

    redis = get_redis_client()
    if target_method and await redis.sismember("downtimes:method", target_method):
        is_down = (through and await redis.exists(f"downtimes:{target_method}:{through}")) or (through and await redis.exists(f"downtimes:{target_method}:{through.upper()}"))
        if is_down:
            customer_name = rs.customer.get("name", "Customer")
            bank_name = through.upper()
            downtime_msg = (
                f"Hi {customer_name}, we noticed {bank_name} servers are temporarily experiencing gateway downtime. "
                f"We have paused your payment deadline. We'll update you as soon as your bank resolves this. (Ref: #RNV-{ref_code})"
            )
            rs.next_retry_at = datetime.now() + timedelta(hours=2)
            ai_msg = AIMessage(
                content="Circuit breaker open: gateway downtime active.",
                tool_calls=[{
                    "name": "send_whatsapp_msg",
                    "args": {"msg": downtime_msg},
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "tool_call"
                }]
            )
            return {"messages": [ai_msg]}

    # Check if this error is fundamentally unrecoverable via automated retries
    is_unresolvable, empathetic_msg = cant_resolve(rs)
    if is_unresolvable:
        print(f"[ROUTER] Unresolvable error detected: {rs.error_details}")
        ai_msg = AIMessage(content="Unresolvable error.", tool_calls=[
            {"name": "send_whatsapp_msg", "args": {"msg": f"{empathetic_msg} (Ref: #RNV-{ref_code})"}, "id": f"call_{uuid.uuid4().hex[:8]}", "type": "tool_call"},
            {"name": "complete_case", "args": {"summary": "Unresolvable error. Empathic message sent."}, "id": f"call_{uuid.uuid4().hex[:8]}", "type": "tool_call"}
        ])
        return {"messages": [ai_msg]}
        
    wa_msg, email_urg, voice_msg = get_escalation_tone(rs)

    if rs.attempt_count >= 3:
        context_str = f"Context: Name={rs.customer.get('name', 'Unknown')}, Amount=₹{rs.amount_inr:,.0f}, Case={rs.case_type}, Last Action={rs.last_action_taken}"
        reason = f"Max attempts ({rs.attempt_count}) reached. {context_str}"
        tools_to_call.append({"name": "escalate_to_human", "args": {"reason": reason}})
        await mark_case_escalated(rs, reason)
    elif rs.case_type == 'dispute':
        reason = "Customer raised a dispute"
        tools_to_call.append({"name": "escalate_to_human", "args": {"reason": reason}})
        await mark_case_escalated(rs, reason)
        
    elif rs.case_type == 'subscription_cancelled':
        if should_send_channel(rs, "whatsapp"):
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": wa_msg}})
        elif should_send_channel(rs, "email"):
            tools_to_call.append({"name": "send_email_reminder", "args": {"urgency": email_urg}})
        
    elif rs.case_type in ['failed_payment', 'failed_subscription']:
        if should_send_channel(rs, "email"):
            tools_to_call.append({"name": "send_email_reminder", "args": {"urgency": email_urg}})

        if rs.amount_inr > 15000 and rs.case_type == "failed_subscription":
            # The Above ₹15,000 EMI Rule
            tools_to_call.append({"name": "create_payment_link", "args": {}})
            if should_send_channel(rs, "whatsapp"):
                tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"Your auto-debit for ₹{rs.amount_inr:,.0f} failed. Under RBI rules, amounts over ₹15,000 require an OTP. Please click the link to authorize. (Ref: #RNV-{ref_code})"}})
        elif rs.decline_type == "soft":
            if (rs.attempt_count or 0) == 0:
                tools_to_call.append({"name": "get_next_salary_date", "args": {}})
            if should_send_channel(rs, "whatsapp"):
                tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": wa_msg}})
        else:
            tools_to_call.append({"name": "create_payment_link", "args": {}})
            if should_send_channel(rs, "voice"):
                tools_to_call.append({"name": "get_voice_call", "args": {"msg": voice_msg}})
            elif should_send_channel(rs, "whatsapp"):
                tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": wa_msg}})
                
    elif rs.case_type == 'abandoned_checkout':
        tools_to_call.append({"name": "create_payment_link", "args": {"discount_pct": 10.0}})
        if should_send_channel(rs, "whatsapp"):
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": f"You left something in your cart! Complete your checkout now and enjoy a 10% discount. Click the payment link to complete your order. (Ref: #RNV-{ref_code})"}})
        elif should_send_channel(rs, "email"):
            tools_to_call.append({"name": "send_email_reminder", "args": {"urgency": email_urg}})

    elif rs.case_type == 'overdue_invoice':
        tools_to_call.append({"name": "create_payment_link", "args": {}})
        if should_send_channel(rs, "email"):
            tools_to_call.append({"name": "send_email_reminder", "args": {"urgency": email_urg}})
        if should_send_channel(rs, "whatsapp"):
            tools_to_call.append({"name": "send_whatsapp_msg", "args": {"msg": wa_msg}})

    if tools_to_call:
        langchain_tool_calls = []
        for t in tools_to_call:
            langchain_tool_calls.append({
                "name": t["name"],
                "args": t["args"],
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "tool_call"
            })
            
        print(f"\n[ROUTER] Deterministic Fast-Path triggered for case: {rs.case_id}")
        ai_msg = AIMessage(content="Deterministic routing applied.", tool_calls=langchain_tool_calls)
        return {"messages": [ai_msg]}

    print(f"\n[ROUTER] Warning: No deterministic rules matched for automated event in case {rs.case_id}")
    return {"messages": []}


async def decide_reply(state: AgentState):
    """
    Phase 2: LLM routing for conversational replies (WhatsApp, Email).
    """
    rs = state["recovery_state"]
    print(f"\n[ROUTER] LLM routing conversational reply for case: {rs.case_id}")
    
    if rs.attempt_count >= 3 and state.get("event_source") != "inbound.human_approval":
        print(f"\n[ROUTER] Deterministic stop in decide_reply: attempt count {rs.attempt_count} >= 3")
        context_str = f"Context: Name={rs.customer.get('name', 'Unknown')}, Amount=₹{rs.amount_inr:,.0f}, Case={rs.case_type}, Last Action={rs.last_action_taken}"
        reason = f"Max attempts ({rs.attempt_count}) reached. {context_str}"
        ai_msg = AIMessage(
            content="Max attempts reached.", 
            tool_calls=[{
                "name": "escalate_to_human", 
                "args": {"reason": reason},
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "tool_call"
            }]
        )
        await mark_case_escalated(rs, reason)
        return {"messages": [ai_msg]}
    
    system_prompt = f"""You are an empathetic, intelligent revenue recovery concierge for Renvue.
    
=== CURRENT CASE ===
Customer     : {rs.customer.get('name', 'Unknown')}
Amount owed  : ₹{rs.amount_inr:,.0f}
Case type    : {rs.case_type}
Attempt Count: {rs.attempt_count}
Language     : {rs.language}
Today's Date : {datetime.now().strftime('%Y-%m-%d')}
Max Discount : {settings.max_discount}%
Min Discount : {settings.min_discount}%

=== CORE RECOVERY RULES ===
1. STOPPING RULE: If Attempt Count >= 3 (and not explicitly authorized by human approval), you MUST call 'escalate_to_human' and STOP. If Human Approved, proceed with the requested recovery action.
2. PROMISE TO PAY & COMMITMENTS: When a customer proposes, promises, or mentions ANY date or commitment to pay (e.g., 'on 18th', 'next monday', '1st of 2078', 'yesterday', 'after salary', '5th of this month'):
   - You MUST extract the date in YYYY-MM-DD format and call 'log_promise_to_pay(date_str=..., reason=..., sentiment=...)'.
   - The backend enforces strict policy guardrails (validates future date, ensures within {settings.max_grace_period}-day max grace period, and rejects past or absurd dates like 2078).
   - If the customer gives an absurd date, past date, or refuses to give a valid date, you may also directly call 'escalate_to_human(reason=...)'.
   - NEVER output plain conversational text asking for clarification when a customer specifies a date. You MUST call 'log_promise_to_pay' or 'escalate_to_human'.
3. NEGOTIATION: If abandoned checkout and user hesitates, negotiate between {settings.min_discount}% and {settings.max_discount}% discount. When agreeing on a discount, call 'create_payment_link' with 'discount_pct' to generate the discounted payment link.
4. OUTREACH: If customer asks a question or replies, use 'send_whatsapp_msg' to reply. Any payment link generated will automatically be attached to your message. You may also explicitly position it using the placeholder '{{payment_link}}'.
5. ESCALATION: Call 'escalate_to_human' if:
   - Customer proposes an invalid, past, or absurd promise-to-pay date (> {settings.max_grace_period} days from today).
   - Customer is hostile, abusive, or explicitly requests a human manager.
   - Attempt Count >= 3 (and not explicitly authorized by human approval).
   DO NOT escalate for polite negotiation or normal questions.

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
    
    first_human_idx = next((i for i, m in enumerate(state["messages"]) if getattr(m, "type", "") == "human"), None)
    
    if first_human_idx is not None:
        recent_messages = state["messages"][first_human_idx:]
    else:
        recent_messages = []
        
    clean_messages = [SystemMessage(content=system_prompt)] + recent_messages
    
    llm = ChatMistralAI(model=settings.model, temperature=0, max_retries=2, timeout=25)
    llm_with_tools = llm.bind_tools(tools)
    
    await asyncio.sleep(random.uniform(0.3, 1.0))
    
    for attempt in range(5):
        try:
            response = await llm_with_tools.ainvoke(clean_messages)
            if getattr(response, "tool_calls", None):
                for call in response.tool_calls:
                    if call["name"] == "escalate_to_human":
                        reason = call.get("args", {}).get("reason", "Escalated by conversational agent")
                        await mark_case_escalated(rs, reason)
                        break
                return {"messages": [response]}

            # Fallback Guardrail: If customer message expressed intent to pay on a date, but LLM produced no tool calls
            last_user_text = ""
            for m in reversed(clean_messages):
                if getattr(m, "type", "") == "human":
                    last_user_text = str(getattr(m, "content", ""))
                    break

            ptp_kws = ["pay", "clear", "settle", "transfer", "promise", "send money", "tomorrow", "yesterday", "month", "friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday"]
            if any(k in last_user_text.lower() for k in ptp_kws):
                import re
                from dateutil.parser import parse
                from agent.tools import sanity_date
                
                text_lower = last_user_text.lower()
                candidate_date = None
                now = datetime.now()
                
                if "yesterday" in text_lower:
                    candidate_date = now - timedelta(days=1)
                elif "tomorrow" in text_lower:
                    candidate_date = now + timedelta(days=1)
                else:
                    temporal_pattern = r'(?:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b|\b(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b|\b\d{1,2}(?:st|nd|rd|th)\b|\b(?:on|by|before)\s+\d{1,2}\b|\b\d{4}\b|\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b(?:this|next)\s+month\b)'
                    if re.search(temporal_pattern, text_lower):
                        try:
                            candidate_date = parse(last_user_text, fuzzy=True, default=datetime(now.year, now.month, now.day, 10, 0))
                        except Exception:
                            candidate_date = None

                if candidate_date:
                    valid, v_reason = sanity_date(candidate_date)
                    if not valid:
                        esc_reason = f"Customer proposed invalid/past promise date: {candidate_date.strftime('%Y-%m-%d')} ({v_reason})"
                        esc_call = {
                            "name": "escalate_to_human",
                            "args": {"reason": esc_reason},
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call"
                        }
                        await mark_case_escalated(rs, esc_reason)
                        return {"messages": [AIMessage(content="", tool_calls=[esc_call])]}
                    else:
                        ptp_call = {
                            "name": "log_promise_to_pay",
                            "args": {
                                "date_str": candidate_date.strftime("%Y-%m-%d"),
                                "reason": f"Customer committed to pay: {last_user_text.strip()}",
                                "sentiment": "Neutral"
                            },
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call"
                        }
                        return {"messages": [AIMessage(content="", tool_calls=[ptp_call])]}

            return {"messages": [response]}
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate_limited" in err_str:
                backoff = random.uniform(2.0, 5.0) * (attempt + 1)
                print(f"[RATE LIMIT] Mistral 429 hit. Retrying in {backoff:.1f}s (Attempt {attempt+1}/5)...")
                await asyncio.sleep(backoff)
            elif "connecterror" in err_str or "name resolution" in err_str or "temporary failure" in err_str or "timeout" in err_str:
                print(f"[LLM NETWORK WARNING] Mistral unreachable ({e}). Attempt {attempt+1}/5.")
                if attempt < 2:
                    await asyncio.sleep(2.0 * (attempt + 1))
                else:
                    # Graceful deterministic fallback so Taskiq background workers never crash on DNS drops
                    print(f"[LLM RESILIENCE] Network/DNS connection failed. Falling back to deterministic escalation tone.")
                    wa_msg, _, _ = get_escalation_tone(rs)
                    fallback_ai = AIMessage(
                        content="Deterministic recovery fallback applied due to upstream LLM connectivity timeout.",
                        tool_calls=[{
                            "name": "send_whatsapp_msg",
                            "args": {"msg": wa_msg},
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "tool_call"
                        }]
                    )
                    return {"messages": [fallback_ai]}
            else:
                raise e
                
    # Final safety fallback
    wa_msg, _, _ = get_escalation_tone(rs)
    fallback_ai = AIMessage(
        content="Deterministic recovery fallback applied after retries exhausted.",
        tool_calls=[{
            "name": "send_whatsapp_msg",
            "args": {"msg": wa_msg},
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "tool_call"
        }]
    )
    return {"messages": [fallback_ai]}


execute = ToolNode(tools)

def escalate_gate(state: AgentState):
    """
    Dummy node that serves as a Human-in-the-Loop breakpoint.
    The graph will be configured to interrupt_before this node.
    """
    return state


async def audit(state: AgentState):
    """
    Saves the final outcome to the SQLite database.
    
    IMPORTANT: Tools each open their own DB session and write next_retry_at / last_action_taken
    directly. The in-memory `rs` in state["recovery_state"] is the ORIGINAL pre-tool-run snapshot.
    We must reload from DB before saving so we don't overwrite those tool-written fields.
    """
    rs_snapshot = state["recovery_state"]
    messages = state["messages"]
    
    last_ai_msg = next((m for m in reversed(messages) if m.type == "ai" and getattr(m, "tool_calls", None)), None)
    
    CHANNEL_TOOLS = {"send_whatsapp_msg", "send_email_reminder", "get_voice_call", "escalate_to_human"}

    async with config.db.AsyncSessionLocal() as db:
        # Reload the CURRENT DB state — tools wrote next_retry_at / last_action_taken here already
        from service.states import load_state as _load_state
        rs = await _load_state(rs_snapshot.case_id, db)
        if not rs:
            # Fallback: use snapshot if somehow not found
            rs = rs_snapshot

        if last_ai_msg and last_ai_msg.tool_calls:
            if any(call["name"] == "complete_case" for call in last_ai_msg.tool_calls):
                rs.recovery_status = "closed"
            elif any(call["name"] == "escalate_to_human" for call in last_ai_msg.tool_calls) or rs.recovery_status == "escalated":
                rs.recovery_status = "escalated"

            # Don't increment beyond 3 if escalated or closed
            if rs.recovery_status not in ["escalated", "closed"]:
                rs.attempt_count = max(rs.attempt_count, rs_snapshot.attempt_count + 1)
            # Only update last_action_taken if a channel tool was used and tools didn't already set it
            if not rs.last_action_taken:
                for call in reversed(last_ai_msg.tool_calls):
                    if call["name"] in CHANNEL_TOOLS or call["name"] in ["complete_case"]:
                        rs.last_action_taken = call["name"]
                        break

        import logging
        logger = logging.getLogger("renvue.audit")
        logger.info(f"[AUDIT] case={rs.case_id} attempt={rs.attempt_count} "
                    f"last_action={rs.last_action_taken} next_retry_at={rs.next_retry_at} "
                    f"status={rs.recovery_status}")

        await save_state(rs, db)
    
    return {"recovery_state": rs}



def should_continue(state: AgentState):
    """
    Decides whether to execute tools or go to the audit phase.
    """
    last_message = state["messages"][-1]
    
    if getattr(last_message, "tool_calls", None):
        if any(call["name"] == "escalate_to_human" for call in last_message.tool_calls):
            return "escalate_gate"
        return "execute"
        
    return "audit"

def after_execute(state: AgentState):
    """
    Decides where to go after executing tools.
    
    Rules:
    - Terminal/message tools (complete_case, escalate_to_human, log_promise_to_pay, send_whatsapp_msg, send_email_reminder) → always audit
    - Other tools for inbound conversational events → decide_reply (LLM loop)
    - Automated (webhook, scheduled follow-up) → audit immediately
    """
    messages = state["messages"]
    
    # Check if a conclusive action has been taken in this tool batch
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", "")
        msg_name = getattr(msg, "name", None)
        if msg_type == "tool":
            if msg_name == "log_promise_to_pay" and "PROMISE_REJECTED" in str(getattr(msg, "content", "")):
                # Rejected promise has already been directly escalated to human in tool
                return "audit"
            if msg_name in ("complete_case", "escalate_to_human", "log_promise_to_pay", "send_whatsapp_msg", "send_email_reminder"):
                return "audit"
        # Stop looking once we pass the current tool results batch
        if msg_type == "ai":
            break
    
    event_source = state.get("event_source", "")
    
    # Only inbound conversational events without a message sent get an LLM reply loop
    if event_source.startswith("inbound."):
        return "decide_reply"
    
    # Automated (webhook, scheduled follow-up) → one-shot, go straight to audit
    return "audit"
