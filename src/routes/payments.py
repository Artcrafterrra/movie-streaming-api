from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database.session_postgresql import get_postgresql_db
from routes.accounts import get_current_user
from database.models.accounts import UserModel
from payments.stripe_service import create_payment_intent, get_user_payments
from schemas.payments import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("/create-intent/", response_model=CreatePaymentIntentResponse)
async def create_payment_intent_endpoint(
    request: CreatePaymentIntentRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    result = await create_payment_intent(
        session=db,
        user_id=current_user.id,
        order_id=request.order_id,
    )

    return CreatePaymentIntentResponse(
        client_secret=result["client_secret"],
        amount=result["amount"],
        order_id=result["order_id"],
        currency="usd",
    )


@router.get("/my-payments/")
async def get_my_payments_endpoint(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    payments = await get_user_payments(db, current_user.id)

    payment_items = []
    for payment in payments:
        payment_items.append(
            PaymentHistoryItem(
                id=payment.id,
                order_id=payment.order_id,
                amount=str(payment.amount),
                status=payment.status.value,
                created_at=payment.created_at.isoformat(),
                external_payment_id=payment.external_payment_id,
            )
        )

    return PaymentHistoryResponse(
        payments=payment_items, count=len(payment_items)
    )
