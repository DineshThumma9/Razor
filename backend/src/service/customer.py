from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from models.models import CustomerProfile

async def save_customer_profile(customer: CustomerProfile, db: AsyncSession):
    """Save or update the CustomerProfile using an atomic Postgres upsert."""
    cust_dict = customer.model_dump(exclude_none=True)
    stmt = insert(CustomerProfile).values(**cust_dict)
    
    update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
    stmt = stmt.on_conflict_do_update(
        index_elements=['id'],
        set_=update_dict
    )
    await db.execute(stmt)
    await db.commit()

async def get_customer_profile(customer_id: str, db: AsyncSession) -> Optional[CustomerProfile]:
    """Load a CustomerProfile by id."""
    return await db.get(CustomerProfile, customer_id)
