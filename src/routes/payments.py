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


@router.post(
    "/webhook", response_model=WebhookAck, status_code=status.HTTP_200_OK
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_postgresql_db),
):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(
            status_code=400, detail="Missing Stripe-Signature header"
        )

    endpoint_secret = getattr(base_app_settings, "STRIPE_WEBHOOK_SECRET", None)
    if not endpoint_secret:
        raise HTTPException(
            status_code=500, detail="Webhook secret is not configured"
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig_header, secret=endpoint_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "payment_intent.succeeded":
        intent_id = data_object.get("id")
        if not intent_id:
            raise HTTPException(
                status_code=400, detail="Missing PaymentIntent id"
            )
        payment = await confirm_payment(db, intent_id)
        return WebhookAck(received=True)

    if event_type in {"payment_intent.payment_failed", "charge.refunded"}:
        return WebhookAck(received=True)

    return WebhookAck(received=True)
