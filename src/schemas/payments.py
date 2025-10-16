from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from database.models.payments import PaymentStatusEnum


class PaymentBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    user_id: int
    amount: Decimal
    status: PaymentStatusEnum
    created_at: datetime
    external_payment_id: Optional[str] = None


class PaymentCreateSchema(BaseModel):
    amount: Decimal
    external_payment_id: Optional[str] = None


class PaymentResponseSchema(PaymentBaseSchema):
    pass


class PaymentListResponseSchema(BaseModel):
    payments: List[PaymentResponseSchema]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "payments": [
                        {
                            "id": 1,
                            "order_id": 42,
                            "user_id": 5,
                            "amount": "19.99",
                            "status": "successful",
                            "created_at": "2025-10-16T12:34:56Z",
                            "external_payment_id": "pi_123456789",
                        }
                    ]
                }
            ]
        },
    )

class PaymentCancelResponseSchema(PaymentResponseSchema):
    message: str


class PaymentRefundResponseSchema(PaymentResponseSchema):
    message: str
