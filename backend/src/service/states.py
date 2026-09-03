from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from models.models import RecoveryState

async def save_state(state: RecoveryState, db: AsyncSession):
    """Save or update the RecoveryState to the database using an atomic Postgres upsert."""
    state_dict = state.model_dump()
    stmt = insert(RecoveryState).values(**state_dict)
        
    update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
    stmt = stmt.on_conflict_do_update(
            index_elements=['case_id'],
            set_=update_dict
    )
    await db.execute(stmt)
    await db.commit()

    try:
        from service.broadcast import broadcast_case_update
        await broadcast_case_update(state)
    except Exception:
        pass

async def load_state(case_id: str, db: AsyncSession) -> Optional[RecoveryState]:
    """Load a RecoveryState by case_id."""
    return await db.get(RecoveryState, case_id)
