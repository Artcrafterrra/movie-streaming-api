from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from database.session_postgresql import get_postgresql_db as get_db
from database.models import UserModel, OrderModel
from routes.accounts import get_current_user
from payments.service import PaymentService
from schemas.payments import PaymentCreateSchema, PaymentResponseSchema
import stripe
import os

router = APIRouter(prefix="/payments", tags=["payments"])
service = PaymentService()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


@router.post(
    "/orders/{order_id}/session",
    summary="Створити платіжну сесію",
)
async def create_payment_session(
    order_id: int,
    payment_data: PaymentCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    # Завантажуємо замовлення
    order = await db.get(OrderModel, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        # Створюємо checkout‑сесію у Stripe
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Order #{order.id}"},
                        "unit_amount": int(float(order.total_amount) * 100),
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"https://yourapp.com/orders/{order.id}/success",
            cancel_url=f"https://yourapp.com/orders/{order.id}/cancel",
            metadata={"order_id": str(order.id), "user_id": str(current_user.id)},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook", summary="Webhook від платіжної системи")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = int(session["metadata"]["order_id"])
        user_id = int(session["metadata"]["user_id"])
        amount = float(session["amount_total"]) / 100

        await service.create_payment(
            db,
            user_id=user_id,
            order_id=order_id,
            amount=amount,
            external_payment_id=session["id"],
        )

    return {"status": "ok"}
