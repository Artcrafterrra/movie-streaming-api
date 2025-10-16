import stripe
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from config.settings import base_app_settings
from database.models.orders import OrderModel, OrderStatusEnum
from database.models.payments import (
    PaymentModel,
    PaymentItemModel,
    PaymentStatusEnum,
)


stripe.api_key = base_app_settings.STRIPE_SECRET_KEY


def to_decimal(value: Decimal | float | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def stripe_amount_to_dollars(cents: int) -> Decimal:
    return Decimal(str(cents / 100))


def dollars_to_stripe_amount(dollars: Decimal) -> int:
    return int(dollars * 100)


async def get_order_with_items(
    session: AsyncSession, order_id: int
) -> Optional[OrderModel]:
    result = await session.execute(
        select(OrderModel)
        .where(OrderModel.id == order_id)
        .options(selectinload(OrderModel.items))
    )
    return result.scalar_one_or_none()


async def sum_successful_payments(
    session: AsyncSession, order_id: int
) -> Decimal:
    result = await session.execute(
        select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
            PaymentModel.order_id == order_id,
            PaymentModel.status == PaymentStatusEnum.SUCCESSFUL,
        )
    )
    total = result.scalar_one()
    return Decimal(str(total))


async def create_stripe_payment_intent(
    amount: Decimal, order_id: int, user_id: int
) -> dict:
    try:
        intent = stripe.PaymentIntent.create(
            amount=dollars_to_stripe_amount(amount),
            currency="usd",
            metadata={
                "order_id": str(order_id),
                "user_id": str(user_id),
            },
            automatic_payment_methods={"enabled": True},
        )

        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "amount": amount,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


async def create_payment(
    session: AsyncSession,
    user_id: int,
    order_id: int,
    amount: Decimal,
    external_payment_id: Optional[str] = None,
) -> PaymentModel:

    order = await get_order_with_items(session, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Order does not belong to user"
        )

    if order.status == OrderStatusEnum.CANCELED:
        raise HTTPException(status_code=400, detail="Order is canceled")

    amount = to_decimal(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    already_paid = await sum_successful_payments(session, order_id)
    remaining = to_decimal(order.total_amount) - already_paid

    if amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Amount {amount} exceeds remaining {remaining}",
        )

    payment = PaymentModel(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        status=PaymentStatusEnum.SUCCESSFUL,
        external_payment_id=external_payment_id,
    )

    session.add(payment)
    await session.flush()

    for order_item in order.items:
        payment_item = PaymentItemModel(
            payment_id=payment.id,
            order_item_id=order_item.id,
            price_at_payment=to_decimal(order_item.price_at_order),
        )
        session.add(payment_item)

    new_total_paid = already_paid + amount
    if new_total_paid >= to_decimal(order.total_amount):
        order.status = OrderStatusEnum.PAID
        session.add(order)

    await session.commit()
    return payment


async def create_payment_intent(
    session: AsyncSession, user_id: int, order_id: int
) -> dict:
    order = await get_order_with_items(session, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Order does not belong to user"
        )

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Order is not pending")

    already_paid = await sum_successful_payments(session, order_id)
    remaining = to_decimal(order.total_amount) - already_paid

    if remaining <= 0:
        raise HTTPException(status_code=400, detail="Order is already paid")

    stripe_intent = await create_stripe_payment_intent(
        remaining, order_id, user_id
    )

    return {
        "client_secret": stripe_intent["client_secret"],
        "amount": remaining,
        "order_id": order_id,
    }


async def confirm_payment(
    session: AsyncSession, stripe_payment_intent_id: str
):
    try:
        intent = stripe.PaymentIntent.retrieve(stripe_payment_intent_id)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

    if intent.status != "succeeded":
        raise HTTPException(status_code=400, detail="Payment not succeeded")

    order_id = int(intent.metadata["order_id"])
    user_id = int(intent.metadata["user_id"])
    amount = stripe_amount_to_dollars(intent.amount)

    payment = await create_payment(
        session=session,
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        external_payment_id=stripe_payment_intent_id,
    )

    return payment


async def get_user_payments(
    session: AsyncSession, user_id: int
) -> List[PaymentModel]:
    result = await session.execute(
        select(PaymentModel)
        .where(PaymentModel.user_id == user_id)
        .options(selectinload(PaymentModel.items))
        .order_by(PaymentModel.created_at.desc())
    )
    return list(result.scalars().all())


async def refund_payment(
    session: AsyncSession, payment_id: int
) -> PaymentModel:

    result = await session.execute(
        select(PaymentModel).where(PaymentModel.id == payment_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatusEnum.SUCCESSFUL:
        raise HTTPException(
            status_code=400, detail="Payment is not successful"
        )

    if payment.external_payment_id:
        try:
            stripe.Refund.create(payment_intent=payment.external_payment_id)
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=400, detail=f"Stripe refund error: {str(e)}"
            )

    payment.status = PaymentStatusEnum.REFUNDED
    session.add(payment)

    order = await get_order_with_items(session, payment.order_id)
    if order:
        remaining_paid = await sum_successful_payments(session, order.id)
        if remaining_paid == 0:
            order.status = OrderStatusEnum.PENDING
            session.add(order)

    await session.commit()
    return payment
