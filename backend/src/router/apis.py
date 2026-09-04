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

from sqlalchemy import delete
@api_router.delete("/cases/clear")
async def clear_cases(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(RecoveryState))
    await db.commit()
    return {"status": "ok", "message": "All cases cleared"}

@api_router.get("/cases")
async def list_cases(db: AsyncSession = Depends(get_db)):
    cases = (await db.execute(select(RecoveryState))).scalars().all()
    sorted_cases = sorted(cases, key=lambda c: STATUS_ORDER.get(c.recovery_status, 99))
    return [c.model_dump(mode="json") for c in sorted_cases]


@api_router.get("/cases/{case_id}")
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    state = await load_state(case_id, db)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found")
    return state.model_dump(mode="json")





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
