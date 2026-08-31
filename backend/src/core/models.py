
from pydantic import BaseModel,Any 
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




class Invoice(BaseModel):
    pass 

class Order(BaseModel):
    pass 

class Payment(BaseModel):
    pass 

class PaymentLink(BaseModel):
    pass


class Customer(BaseModel):
    customer_id:Optional[str] 
    name:Optional[str] 
    email:Optional[str] 
    contact:Optional[str]
    prefreed_lang:Optional[str]
    notes:Optional[List[str]]



class PaymentError(BaseModel):
    code:str 
    desc:str 
    reason:str 
    step:str 
    source:str 


class Card(BaseModel):
    id:str 
    type:str 
    network:str 
    issuer:str 
    international:bool
    last4:str 
    sub_type:str 
    iin:str 
    emi:bool 


class UPI(BaseModel):
    payer:str 
    vpa:str 
    flow:str 


class NetBanking(BaseModel):
    pass 

class Wallet(BaseModel):
    pass 


class PaymentMethod(BaseModel):
    card:Optional[Card] 
    upi:Optional[UPI]
    net_banking:Optional[NetBanking]
    wallet:Optional[Wallet]



class AdditionalInformation(BaseModel):
    info:Dict[str,str]

class AmountInvolved(BaseModel):
    amount:str 
    currency:str 
    base_amount:str 
    amount_in_paise:str 
    amount_paid:Optional[str]
    amount_due:Optional[str]

class AcquirerData(BaseModel):
    transaction_id:str 
    rrn:str 


class Subscription(BaseModel):
    pass 

class PayementIDs(BaseModel):
    order_id:Optional[str]
    payment_id:Optional[str]
    invoice_id:Optional[str]
    plan_id:Optional[str]
    offer_id:Optional[str]
    token_id:Optional[str]



class Instrument(BaseModel):
    pass 

class PaymentDowntime(BaseModel):
    id:str 
    method:str 
    begin:int
    end:Optional[int]
    status:str 
    scheduled:bool 
    severity: str 
    instrument:Instrument 
    instrument_schema:Any 
    created_at: int 
    updated_at: int 


class RazorPayEvent(BaseModel):
    entities: Invoice | Order | PaymentLink | Payment | Subscription 
    payment_method:PaymentMethod
    error:PaymentError
    customer:Customer
    amount:AmountInvolved

    pass 
