import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import base_app_settings
from database.session_postgresql import get_postgresql_db
from routes.accounts import get_current_user
from database.models.accounts import UserModel
from payments.stripe_service import (
    create_payment_intent,
    get_user_payments,
    confirm_payment,
)
from schemas.payments import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
    WebhookAck,
)
from schemas.payments import (
    CreateStripeSessionRequest,
    CreateStripeSessionResponse,
)

stripe.api_key = base_app_settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("/create-session/", response_model=CreateStripeSessionResponse)
async def create_stripe_session_endpoint(
    request: CreateStripeSessionRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    payment = await StripePaymentService().create_stripe_session(
        db=db,
        user_id=current_user.id,
        order_id=request.order_id,
    )
    return CreateStripeSessionResponse(
        session_id=payment.external_payment_id,
        session_url=payment.external_payment_link,
        amount=float(payment.amount),
        order_id=payment.order_id,
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
