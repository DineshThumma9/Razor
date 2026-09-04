
from pydantic import BaseModel,Field
from typing import Optional,Dict,Any
from datetime import datetime

class AuditEntry(BaseModel):
    event_triggered: str 
    amount: str 
    recovery_status: str 
    customer: Dict[str, Any]
    next_contact: Optional[datetime] = None
    message: Optional[str] = None
    channel: Optional[str] = None
    direction: Optional[str] = None  # outbound | inbound | system
    meta_compliance: Optional[str] = None
    hsm_template: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    model_config = {"extra": "allow"}

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
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_contact: Optional[str] = None
    model_config = {"extra": "allow"}

class Notes(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_contact: Optional[str] = None
    language: Optional[str] = None
    failure_reason: Optional[str] = None
    halt_reason: Optional[str] = None
    amount: Optional[float] = None
    scenario: Optional[str] = None
    model_config = {"extra": "allow"}

class CardEntity(BaseModel):
    id: Optional[str] = None
    entity: str = "card"
    name: Optional[str] = None
    last4: Optional[str] = None
    network: Optional[str] = None  # Visa, MasterCard, RuPay, Bajaj Finserv, Amex
    type: Optional[str] = None     # debit, credit, prepaid
    issuer: Optional[str] = None   # HDFC, ICICI, UTIB, SBIN, KKBK
    international: Optional[bool] = False
    emi: Optional[bool] = False
    sub_type: Optional[str] = "consumer"
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
    card_id: Optional[str] = None
    card: Optional[CardEntity] = None
    bank: Optional[str] = None
    vpa: Optional[str] = None
    wallet: Optional[str] = None
    acquirer_data: Optional[Dict[str, Any]] = None
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
    customer_id: Optional[str] = None
    amount: Optional[float] = None
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
    sentiment: str = Field(default="neutral", description="Sentiment of the reply user sent (e.g. 'gentle', 'neutral', 'angry', 'hostile').")
    reason: str = Field(default="Customer commitment regarding payment", description="The reason or context the user gave for the delay.")
    date_str: Optional[str] = Field(
        default=None,
        description="The ISO format date (YYYY-MM-DD) the user promised to pay by, or None if no specific valid date could be extracted."
    )


class CompleteCaseArgs(BaseModel):
    summary: str = Field(default="Case completed.", description="Summary of actions taken to resolve the case.")

class PaymentLinkArgs(BaseModel):
    discount_pct: float = Field(
        default=0.0,
        description="Optional concession/discount percentage to apply (must be bounded between MIN_DISCOUNT and MAX_DISCOUNT, e.g. 5% to 30%)."
    )

class EscalateArgs(BaseModel):
    reason: str = Field(description="Detailed reason for why this case is being escalated.")

class SalaryDateArgs(BaseModel):
    pass


class DiscountOfferArgs(BaseModel):
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
    account_id: Optional[str] = "acc_default"
    contains: list[str] = []
    payload: PayloadContainer
    model_config = {"extra": "ignore"} 


class SimulationEvent(BaseModel):
    event_type:str 
    decline_reason:str 
    email:str
    phone:str 
    name:str 
    amount:int 
    language:str = "english"
    account_id: Optional[str] = "acc_default"


class CustomerAction(BaseModel):
    actions: str
    case_id: str
    messages: Optional[str] = ""
    customer: Optional[CustomerDetails] = None
    
    