from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from database.models.orders import OrderModel
from database.models.payments import (
    PaymentModel,
    PaymentItemModel,
    PaymentStatusEnum,
)


class PaymentRepository:
    """Data-access layer for payments and related order data."""

    def get_order_with_items(
        self, session: Session, order_id: int
    ) -> Optional[OrderModel]:
        """Load order with its items for payment operations."""
        return session.execute(
            select(OrderModel)
            .where(OrderModel.id == order_id)
            .options(selectinload(OrderModel.items))
        ).scalar_one_or_none()

    def sum_successful_payments(
        self, session: Session, order_id: int
    ) -> Decimal:
        """Sum amounts of all successful payments for the order."""
        total = session.execute(
            select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                PaymentModel.order_id == order_id,
                PaymentModel.status == PaymentStatusEnum.SUCCESSFUL,
            )
        ).scalar_one()
        return Decimal(str(total))

    def external_payment_exists(
        self, session: Session, external_payment_id: str
    ) -> bool:
        """Check if a payment with the given external id already exists."""
        if not external_payment_id:
            return False
        exists = session.execute(
            select(PaymentModel.id).where(
                PaymentModel.external_payment_id == external_payment_id
            )
        ).first()
        return exists is not None

    def get_payment_by_id(
        self, session: Session, payment_id: int
    ) -> Optional[PaymentModel]:
        """Fetch payment by id."""
        return session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        ).scalar_one_or_none()

    def list_user_payments(
        self, session: Session, user_id: int
    ) -> List[PaymentModel]:
        """List payments for a specific user (most recent first)."""
        return list(
            session.execute(
                select(PaymentModel)
                .where(PaymentModel.user_id == user_id)
                .options(selectinload(PaymentModel.items))
                .order_by(PaymentModel.created_at.desc())
            ).scalars()
        )

    def list_order_payments(
        self, session: Session, order_id: int
    ) -> List[PaymentModel]:
        """List payments for a specific order (chronological)."""
        return list(
            session.execute(
                select(PaymentModel)
                .where(PaymentModel.order_id == order_id)
                .options(selectinload(PaymentModel.items))
                .order_by(PaymentModel.created_at.asc())
            ).scalars()
        )

    def save_payment(
        self, session: Session, payment: PaymentModel
    ) -> PaymentModel:
        """Persist a payment and flush to obtain its id."""
        session.add(payment)
        session.flush()
        return payment

    def save_payment_item(
        self, session: Session, item: PaymentItemModel
    ) -> PaymentItemModel:
        """Persist a payment item."""
        session.add(item)
        return item
