from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.models import RecoveryState
from agent.graph import build_agent
from config.constants import STATUS_ORDER
from service.states import load_state, save_state


api_router = APIRouter(prefix="/api")

@api_router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    cases = (await db.execute(select(RecoveryState))).scalars().all()
    total_at_risk = sum(c.amount_inr for c in cases)
    recovered = [c for c in cases if c.recovery_status == "recovered"]
    escalated = [c for c in cases if c.recovery_status == "escalated"]
    return {
        "total_cases": len(cases),
        "total_at_risk_inr": total_at_risk,
        "recovered_count": len(recovered),
        "recovered_amount_inr": sum(c.recovered_amount for c in recovered),
        "recovery_rate_pct": round(len(recovered) / len(cases) * 100, 1) if cases else 0,
        "escalated_count": len(escalated),
        "still_active": len(cases) - len(recovered) - len(escalated),
    }

    
@api_router.get("/cases")
async def list_cases(db: AsyncSession = Depends(get_db)):
    cases = (await db.execute(select(RecoveryState))).scalars().all()
    sorted_cases = sorted(cases, key=lambda c: STATUS_ORDER.get(c.recovery_status, 99))
    
    return [
        {
            "case_id": c.case_id,
            "case_type": c.case_type,
            "decline_type": c.decline_type,
            "failure_reason": c.failure_reason,
            "amount_inr": c.amount_inr,
            "recovered_amount": c.recovered_amount,
            "customer": c.customer,
            "recovery_status": c.recovery_status,
            "attempt_count": c.attempt_count,
            "last_action_taken": c.last_action_taken,
            "first_seen_at": c.first_seen_at.isoformat() if c.first_seen_at else None,
            "next_retry_at": c.next_retry_at.isoformat() if c.next_retry_at else None,
            "language": c.language,
        }
        for c in sorted_cases
    ]


@api_router.get("/cases/{case_id}")
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    state = await load_state(case_id, db)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case_id": state.case_id,
        "source_id": state.source_id,
        "case_type": state.case_type,
        "decline_type": state.decline_type,
        "failure_reason": state.failure_reason,
        "amount_inr": state.amount_inr,
        "recovered_amount": state.recovered_amount,
        "customer": state.customer,
        "contact_preference": state.contact_preference,
        "language": state.language,
        "recovery_status": state.recovery_status,
        "attempt_count": state.attempt_count,
        "last_action_taken": state.last_action_taken,
        "first_seen_at": state.first_seen_at.isoformat() if state.first_seen_at else None,
        "next_retry_at": state.next_retry_at.isoformat() if state.next_retry_at else None,
        "audit_log": state.audit_log,
    }


@api_router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    cases = (await db.execute(select(RecoveryState))).scalars().all()
    total_cases = len(cases)
    total_at_risk = sum(c.amount_inr for c in cases if c.recovery_status not in ["recovered", "closed"])
    total_recovered = sum(c.recovered_amount for c in cases)
    total_money = sum(c.amount_inr for c in cases)
    recovery_rate = round((total_recovered / total_money * 100), 1) if total_money > 0 else 0.0
    by_status = {}
    for c in cases:
        by_status[c.recovery_status] = by_status.get(c.recovery_status, 0) + 1
    by_type = {}
    for c in cases:
        by_type[c.case_type] = by_type.get(c.case_type, 0) + 1
    return {
        "total_cases": total_cases,
        "total_at_risk_inr": round(total_at_risk, 2),
        "total_recovered_inr": round(total_recovered, 2),
        "recovery_rate_pct": recovery_rate,
        "escalated_count": by_status.get("escalated", 0),
        "pending_count": by_status.get("pending", 0),
        "in_progress_count": by_status.get("in_progress", 0),
        "recovered_count": by_status.get("recovered", 0),
        "by_status": by_status,
        "by_type": by_type,
    }


@api_router.post("/cases/{case_id}/approve")
async def approve_escalation(case_id: str, db: AsyncSession = Depends(get_db)):
    state = await load_state(case_id, db)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found")
    if state.recovery_status != "escalated":
        raise HTTPException(status_code=400, detail=f"Case is not escalated (current: {state.recovery_status})")
    state.recovery_status = "in_progress"
    await save_state(state, db)
    agent = build_agent(state)
    config = {"configurable": {"thread_id": case_id}}
    await agent.ainvoke(
        {"messages": [HumanMessage(content="Human approved. Proceed with next recovery action.")],
         "recovery_state": state,
         "event_source": "inbound.human_approval"},
        config=config,
    )
    return {"status": "approved", "case_id": case_id}


@api_router.post("/cases/{case_id}/close")
async def close_case(case_id: str, db: AsyncSession = Depends(get_db)):
    state = await load_state(case_id, db)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found")
    state.recovery_status = "closed"
    await save_state(state, db)
    return {"status": "closed", "case_id": case_id}
