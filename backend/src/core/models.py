

from pydantic import BaseModel
from typing import Optional,Dict
from datetime import datetime 





from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from typing import Optional, Dict, List
from datetime import datetime

class AuditEntry(BaseModel):
    event_triggered: str 
    amount: str 
    recovery_status: str 
    customer: Dict[str, str]
    next_contact: Optional[datetime] = None

class RecoveryState(SQLModel, table=True):
    __tablename__ = "recovery_cases"

    # Identity
    case_id: str = Field(primary_key=True)  # our internal ID (uuid)
    source_id: str                          # Razorpay order/sub/invoice ID

    # What happened
    case_type: str                          # failed_payment | abandoned_checkout | ...
    decline_type: Optional[str] = None      # hard | soft | None
    failure_reason: Optional[str] = None    # "Insufficient funds" | "Card expired" | None

    # Money
    amount_inr: float
    recovered_amount: float = 0.0

    # Customer (JSON)
    customer: dict = Field(default_factory=dict, sa_column=Column(JSON))
    contact_preference: str = "email"       # email | sms | whatsapp | call
    language: str = "english"               # english | hinglish

    # Lifecycle
    recovery_status: str = "pending"        # pending | in_progress | recovered | escalated | closed
    attempt_count: int = 0
    last_action_taken: Optional[str] = None
    first_seen_at: datetime
    next_retry_at: Optional[datetime] = None

    # History (JSON)
    audit_log: List[dict] = Field(default_factory=list, sa_column=Column(JSON))



