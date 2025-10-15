from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from database.models.payments import PaymentStatusEnum


class PaymentCreateRequestSchema(BaseModel):

    order_id: int = Field(..., gt=0, description="ID of the order to pay for")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    external_payment_id: Optional[str] = Field(
        None,
        max_length=255,
        description="External payment ID from payment provider (e.g., Stripe)",
    )


class PaymentResponseSchema(BaseModel):
    id: int
    user_id: int
    order_id: int
    amount: Decimal
    status: PaymentStatusEnum
    external_payment_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
