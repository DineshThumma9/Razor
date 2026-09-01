import asyncio
from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.models import RecoveryState
from agent.graph import build_agent
from agent.tools import _schedule_task
from service.states import load_state, save_state
from background.worker import invoke_agent_task, abandoned_cart_timer, revoke_active_task

from service.parsers import parse_webhook, extract_ids_from_payload
from service.downtime import process_downtime_event


async def kill_all_tasks(case_id: str, db: AsyncSession):
    state = await load_state(case_id, db)
    if state and state.active_task_id:
        print(f"[TASKIQ] Revoking active task {state.active_task_id} for case {case_id}")
        await revoke_active_task(state.active_task_id)
        state.active_task_id = None
        await save_state(state, db)


async def mark_resolved_kill_tasks():
    pass 


async def change_pursit(case_id: str, amount_paid: float, db: AsyncSession):
    state = await load_state(case_id, db)
    if state:
        state.amount_inr -= amount_paid
        state.audit_log.append({
            "event_triggered": "partial_payment_received",
            "amount": str(amount_paid),
            "recovery_status": state.recovery_status,
            "customer": state.customer,
            "next_contact": datetime.now().isoformat()
        })
        await save_state(state, db)
        print(f"[RECOVERY] Case {case_id} balance updated. Remaining: {state.amount_inr}")


async def handle_payment_event(payload: dict, db: AsyncSession) -> dict:
    event = payload.get("event", "")
    SUCCESS_EVENTS = ["payment.captured", "invoice.paid", "subscription.charged", "order.paid"]
    FAIL_EVENTS = ["payment.failed", "invoice.expired", "subscription.halted", "payment_link.expired"]

    # 1. Environment / Downtime Awareness
    if event.startswith("payment.downtime"):
        return process_downtime_event(payload)

    # 2. Lifecycle Interception (Kill Switch for Success or Dispute)
    if event in SUCCESS_EVENTS or event == "payment.dispute.created":
        extracted_case_id, extracted_source_id = extract_ids_from_payload(payload)
        
        result = await db.execute(
            select(RecoveryState).where(
                RecoveryState.recovery_status.notin_(["recovered", "closed", "escalated"])
            )
        )
        cases = result.scalars().all()
            
        matched_case = None
        for case in cases:
            if case.case_id == extracted_case_id:
                matched_case = case
                break
            elif case.source_id != "unknown" and case.source_id == extracted_source_id:
                matched_case = case
                break
            
        if matched_case:
            if event == "payment.dispute.created":
                matched_case.recovery_status = "escalated"
                matched_case.failure_reason = "Customer filed a dispute"
            else:
                matched_case.recovery_status = "recovered"
                amount = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("amount", 0) / 100.0
                matched_case.recovered_amount = amount
            
            db.add(matched_case)
            await db.commit()
                
            await kill_all_tasks(matched_case.case_id, db)
                
            if event == "payment.dispute.created":
                # Trigger the graph so it can invoke escalate_to_human
                agent = build_agent(matched_case)
                config = {"configurable": {"thread_id": matched_case.case_id}}
                await agent.ainvoke({"messages": [], "recovery_state": matched_case, "event_source": "inbound.webhook"}, config=config)
                
            return {"status": f"Case {matched_case.case_id} marked as {matched_case.recovery_status}!"}
                
        return {"status": "ok, but no active case matched this event ID"}
    
    # 3. Partial Payments (Delaying notifications)
    elif event == "invoice.partially_paid":
        extracted_case_id, _ = extract_ids_from_payload(payload)
        amount_paid = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("amount", 0) / 100.0
        if extracted_case_id:
            state = await load_state(extracted_case_id, db)
            if state:
                state.recovered_amount += amount_paid
                state.amount_inr -= amount_paid
                target_date = datetime.now() + timedelta(days=3)
                
                await _schedule_task(state, target_date, db)
                
                state.audit_log.append({
                    "event_triggered": "partial_payment_received",
                    "amount": str(amount_paid),
                    "recovery_status": state.recovery_status,
                    "customer": state.customer,
                    "next_contact": target_date.isoformat()
                })
                await save_state(state, db)
        return {"status": "partial payment logged"}

    # 4. Triggers (Lost Revenue)
    elif event in FAIL_EVENTS or event == "subscription.cancelled":
        new_state = await parse_webhook(payload, db)
        if new_state:
            await save_state(new_state, db)
            agent = build_agent(new_state)
            config = {"configurable": {"thread_id": new_state.case_id}}
            await agent.ainvoke({"messages": [], "recovery_state": new_state, "event_source": "automated.webhook"}, config=config)
            return {"status": "lost revenue case created and agent invoked!"}
            
    # 5. Order Creation (15-Minute Abandoned Cart Timer)
    elif event == "order.created":
        extracted_case_id, extracted_source_id = extract_ids_from_payload(payload)
        if extracted_source_id != "unknown":
            customer_data = payload.get("payload", {}).get("order", {}).get("entity", {}).get("customer", {})
            # Taskiq .kiq() instead of celery .apply_async()
            await abandoned_cart_timer.kiq(extracted_source_id, customer_data)
            return {"status": "abandoned cart timer scheduled"}

    return {"status": "ignored"}


async def handle_inbound_email(payload: dict, db: AsyncSession) -> dict:
    recipient = payload.get("to", "")
    try:
        case_id = recipient.split("+")[1].split("@")[0]
    except IndexError:
        return {"status": "ignored", "reason": "No valid case_id in recipient"}
        
    state = await load_state(case_id, db)
    if not state or state.recovery_status in ["recovered", "closed", "escalated"]:
        return {"status": "ignored", "reason": "Case not active"}

    customer_reply_text = payload.get("text", "")
    new_message = HumanMessage(content=f"Customer Replied via Email: {customer_reply_text}")

    agent = build_agent(state)
    config = {"configurable": {"thread_id": case_id}}
    await agent.ainvoke(
        {"messages": [new_message], "recovery_state": state, "event_source": "inbound.email"}, 
        config=config
    )

    return {"status": "Agent woken up successfully"}


async def handle_inbound_whatsapp(from_number: str, body: str, db: AsyncSession) -> dict:
    print(f"\n[INBOUND WHATSAPP] Received message from {from_number}: {body}")
    
    contact_number = from_number.replace("whatsapp:", "")
    if contact_number.startswith("+91"):
        contact_number = contact_number[3:]
        
    print(f"[INBOUND WHATSAPP] Looking for active case for contact: {contact_number}")
    
    active_case = None
    result = await db.execute(select(RecoveryState).where(RecoveryState.recovery_status.notin_(["recovered", "closed", "escalated"])))
    cases = result.scalars().all()
    
    for case in cases:
        case_contact = case.customer.get("contact", "")
        if case_contact == contact_number or case_contact.endswith(contact_number):
            active_case = case
            break
                
    if not active_case:
        print(f"[INBOUND WHATSAPP] Ignored: No active case found for {contact_number}")
        return {"status": "ignored", "reason": "No active case found for this number"}
        
    print(f"[INBOUND WHATSAPP] Matched case {active_case.case_id}. Waking up agent!")
        
    new_message = HumanMessage(content=f"Customer Replied via WhatsApp: {body}")
    agent = build_agent(active_case)
    config = {"configurable": {"thread_id": active_case.case_id}}
    
    await agent.ainvoke(
        {"messages": [new_message], "recovery_state": active_case, "event_source": "inbound.whatsapp"}, 
        config=config
    )
    
    return {"status": "Agent woken up successfully"}