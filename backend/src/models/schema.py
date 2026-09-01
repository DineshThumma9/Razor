
from pydantic import BaseModel,Field
from typing import Optional,Dict,Any
from datetime import datetime

class AuditEntry(BaseModel):
    event_triggered: str 
    amount: str 
    recovery_status: str 
    customer: Dict[str, str]
    next_contact: Optional[datetime] = None


class Invoice(BaseModel):
    pass 

class Instrument(BaseModel):
    flow:Optional[str] = None
    psp:Optional[str] = None
    vpa_handle:Optional[str] = None
    network:Optional[str] = None
    type:Optional[str] = None
    issuer:Optional[str] = None
    bank:Optional[str] = None
    model_config = {"extra": "ignore"}

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

# Webhook Payload Partial Mapping Models
class CustomerDetails(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    model_config = {"extra": "ignore"}

class Notes(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_contact: Optional[str] = None
    language: Optional[str] = None
    model_config = {"extra": "ignore"}

class PaymentEntity(BaseModel):
    id: str
    order_id: Optional[str] = None
    amount: float
    currency: Optional[str] = None
    status: Optional[str] = None
    captured: Optional[bool] = None
    amount_refunded: Optional[float] = None
    method: Optional[str] = None
    bank: Optional[str] = None
    vpa: Optional[str] = None
    wallet: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    name: Optional[str] = None
    model_config = {"extra": "ignore"}

class SubscriptionEntity(BaseModel):
    id: str
    customer_id: str
    status: Optional[str] = None
    plan_id: Optional[str] = None
    charge_at: Optional[int] = None
    start_at: Optional[int] = None
    end_at: Optional[int] = None
    total_count: Optional[int] = None
    paid_count: Optional[int] = None
    remaining_count: Optional[int] = None
    auth_attempts: Optional[int] = None
    short_url: Optional[str] = None
    notes: Optional[Notes] = None
    model_config = {"extra": "ignore"}

class InvoiceEntity(BaseModel):
    id: str
    amount: float
    amount_paid: Optional[float] = None
    amount_due: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    order_id: Optional[str] = None
    subscription_id: Optional[str] = None
    expire_by: Optional[int] = None
    issued_at: Optional[int] = None
    customer_details: Optional[CustomerDetails] = None
    model_config = {"extra": "ignore"}

class PaymentLinkEntity(BaseModel):
    id: str
    amount: float
    customer: Optional[CustomerDetails] = None
    model_config = {"extra": "ignore"}

class OrderEntity(BaseModel):
    id: str
    amount: Optional[float] = None
    amount_paid: Optional[float] = None
    amount_due: Optional[float] = None
    currency: Optional[str] = None
    receipt: Optional[str] = None
    status: Optional[str] = None
    attempts: Optional[int] = None
    model_config = {"extra": "ignore"}

class DisputeEntity(BaseModel):
    id: str
    payment_id: str
    amount: float
    currency: Optional[str] = None
    status: str
    reason_code: Optional[str] = None
    phase: Optional[str] = None
    respond_by: Optional[int] = None
    model_config = {"extra": "ignore"}

class PaymentWrapper(BaseModel):
    entity: PaymentEntity
    
class SubscriptionWrapper(BaseModel):
    entity: SubscriptionEntity
    
class InvoiceWrapper(BaseModel):
    entity: InvoiceEntity
    
class PaymentLinkWrapper(BaseModel):
    entity: PaymentLinkEntity

class OrderWrapper(BaseModel):
    entity: OrderEntity

class DisputeWrapper(BaseModel):
    entity: DisputeEntity

class PaymentDowntimeWrapper(BaseModel):
    entity: PaymentDowntime



class EmailReminderArgs(BaseModel):
    urgency: str = Field(description="MUST be one of: 'gentle', 'urgent', 'final'")


class PromiseToPayArgs(BaseModel):
    sentiment:str=Field(description="Sentiment of the reply user sent Gentle? Angry?")
    reason: str = Field(description="The reason the user gave for the delay.")
    date_str: str = Field(description="The ISO format date (YYYY-MM-DD) the user promised to pay by.")


class CompleteCaseArgs(BaseModel):
    summary: str = Field(default="Case completed.", description="Summary of actions taken to resolve the case.")

class PaymentLinkArgs(BaseModel):
    pass # No arguments needed!

class EscalateArgs(BaseModel):
    reason: str = Field(description="Detailed reason for why this case is being escalated.")

class SalaryDateArgs(BaseModel):
    pass


class PayloadContainer(BaseModel):
    payment: Optional[PaymentWrapper] = None
    subscription: Optional[SubscriptionWrapper] = None
    invoice: Optional[InvoiceWrapper] = None
    payment_link: Optional[PaymentLinkWrapper] = None
    order: Optional[OrderWrapper] = None
    dispute: Optional[DisputeWrapper] = None
    payment_downtime: Optional[PaymentDowntimeWrapper] = None
    model_config = {"extra": "ignore"}

class RazorpayWebhook(BaseModel):
    event: str
    contains: list[str] = []
    payload: PayloadContainer
    model_config = {"extra": "ignore"} 
