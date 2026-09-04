



from typing import Optional
from datetime import datetime 
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from typing import Optional,List
from datetime import datetime


class CustomerProfile(SQLModel, table=True):
    __tablename__ = "customers"
    
    id: str = Field(primary_key=True) # customer_id from Razorpay
    name: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    language: str = "english"
    contact_preference: str = "whatsapp"
    trust_score: int = 100
    total_spend: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class RecoveryState(SQLModel, table=True):
    __tablename__ = "recovery_cases"

    # Identity & Multi-Tenancy
    case_id: str = Field(primary_key=True)  # our internal ID (uuid)
    source_id: str                          # Razorpay order/sub/invoice ID
    account_id: str = Field(default="acc_default", index=True)  # Razorpay merchant account ID
    
    method:Optional[str] = None 
    through:Optional[str] = None 
    case_type: str                          # failed_payment | abandoned_checkout | ...
    decline_type: Optional[str] = None      # hard | soft | None
    failure_reason: Optional[str] = None    # "Insufficient funds" | "Card expired" | None
    error_details: dict = Field(default_factory=dict, sa_column=Column(JSON))
    case_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))

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
    first_seen_at: datetime = Field(default_factory=datetime.now)
    next_retry_at: Optional[datetime] = None

    # History (JSON)
    audit_log: List[dict] = Field(default_factory=list, sa_column=Column(JSON))
    
    # Background Tasks
    active_task_id: Optional[str] = Field(default=None,exclude=True)

