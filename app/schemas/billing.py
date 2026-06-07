from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any


class PlanResponse(BaseModel):
    id: UUID
    name: str
    price: float
    currency: str
    description: Optional[str] = None
    features: List[str]
    daily_limits: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(BaseModel):
    id: UUID
    user_id: UUID
    plan_id: UUID
    status: str
    start_date: datetime
    end_date: datetime
    plan: Optional[PlanResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: UUID
    user_id: UUID
    subscription_id: UUID
    amount: float
    currency: str
    provider: str
    provider_transaction_id: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: UUID
    user_id: UUID
    payment_id: UUID
    invoice_number: str
    pdf_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionCreateRequest(BaseModel):
    plan_id: UUID
    provider: str  # stripe, paypal, orange_money, mtn_momo


class SubscriptionUpgradeRequest(BaseModel):
    plan_id: UUID
    provider: str  # stripe, paypal, orange_money, mtn_momo
