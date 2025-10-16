from typing import List, Optional

from pydantic import BaseModel, Field


class CreatePaymentIntentRequest(BaseModel):
    order_id: int = Field(..., gt=0)


class CreatePaymentIntentResponse(BaseModel):
    client_secret: str = Field(...)
    amount: float = Field(..., gt=0)
    order_id: int = Field(...)
    currency: str = Field(default="usd")


class PaymentHistoryItem(BaseModel):
    id: int
    order_id: int
    amount: str
    status: str
    created_at: str
    external_payment_id: Optional[str] = None


class PaymentHistoryResponse(BaseModel):
    payments: List[PaymentHistoryItem]
    count: int
