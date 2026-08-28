

from pydantic import BaseModel
from typing import Optional,Dict
from datetime import datetime 





class AuditEntry(BaseModel):
    event_triggered:str 
    amount:str 
    recovery_status:str 
    customer:Dict[str,str]
    next_contact:Optional[datetime]



class RecoveryState(BaseModel):
    # Identity
    case_id: str               # our internal ID (uuid)
    source_id: str             # Razorpay order/sub/invoice ID

    # What happened
    case_type: str             # failed_payment | abandoned_checkout | ...
    decline_type: str | None   # hard | soft | None
    failure_reason: str | None # "Insufficient funds" | "Card expired" | None

    # Money
    amount_inr: float
    recovered_amount: float = 0.0

    # Customer
    customer: dict             # name, email, contact
    contact_preference: str = "email"   # email | sms | whatsapp | call
    language: str = "english"           # english | hinglish

    # Lifecycle
    recovery_status: str = "pending"   # pending | in_progress | recovered | escalated | closed
    attempt_count: int = 0
    last_action_taken: str | None = None
    first_seen_at: datetime
    next_retry_at: datetime | None = None

    # History
    audit_log: list[AuditEntry] = []



