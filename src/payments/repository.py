from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession as Session

from database.models.orders import OrderModel
from database.models.payments import (
    PaymentModel,
    PaymentItemModel,
    PaymentStatusEnum,
)


class PaymentRepository:
    """Data-access layer for payments and related order data."""

    async def get_order_with_items(
        self, session: Session, order_id: int
    ) -> Optional[OrderModel]:
        """Load order with its items for payment operations."""
        result = await session.execute(
            select(OrderModel)
            .where(OrderModel.id == order_id)
            .options(selectinload(OrderModel.items))
        )
        return result.scalar_one_or_none()

    async def sum_successful_payments(
        self, session: Session, order_id: int
    ) -> Decimal:
        """Sum amounts of all successful payments for the order."""
        result = await session.execute(
            select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                PaymentModel.order_id == order_id,
                PaymentModel.status == PaymentStatusEnum.SUCCESSFUL,
            )
        )
        total = result.scalar_one()
        return Decimal(str(total))

    async def external_payment_exists(
        self, session: Session, external_payment_id: str
    ) -> bool:
        """Check if a payment with the given external id already exists."""
        if not external_payment_id:
            return False
        result = await session.execute(
            select(PaymentModel.id).where(
                PaymentModel.external_payment_id == external_payment_id
            )
        )
        exists = result.first()
        return exists is not None

    async def get_payment_by_id(
        self, session: Session, payment_id: int
    ) -> Optional[PaymentModel]:
        """Fetch payment by id."""
        result = await session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def list_user_payments(
        self, session: Session, user_id: int
    ) -> List[PaymentModel]:
        """List payments for a specific user (most recent first)."""
        result = await session.execute(
            select(PaymentModel)
            .where(PaymentModel.user_id == user_id)
            .options(selectinload(PaymentModel.items))
            .order_by(PaymentModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_order_payments(
        self, session: Session, order_id: int
    ) -> List[PaymentModel]:
        """List payments for a specific order (chronological)."""
        result = await session.execute(
            select(PaymentModel)
            .where(PaymentModel.order_id == order_id)
            .options(selectinload(PaymentModel.items))
            .order_by(PaymentModel.created_at.asc())
        )
        return list(result.scalars().all())

    async def save_payment(
        self, session: Session, payment: PaymentModel
    ) -> PaymentModel:
        """Persist a payment and flush to obtain its id."""
        session.add(payment)
        await session.flush()
        return payment

    async def save_payment_item(
        self, session: Session, item: PaymentItemModel
    ) -> PaymentItemModel:
        """Persist a payment item."""
        session.add(item)
        return item
