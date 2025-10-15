from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.payments import PaymentStatusEnum, PaymentModel


class PaymentServiceInterface(ABC):
    """Interface describing the payment service contract."""

    @abstractmethod
    async def create_payment(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        order_id: int,
        amount: Decimal | float | int,
        external_payment_id: Optional[str] = None,
        status: PaymentStatusEnum = PaymentStatusEnum.SUCCESSFUL,
    ) -> PaymentModel:
        """Create a payment and persist a snapshot of order items at payment time."""
        pass

    @abstractmethod
    async def cancel_payment(
        self, session: AsyncSession, *, payment_id: int
    ) -> PaymentModel:
        """Mark a payment as canceled."""
        pass

    @abstractmethod
    async def refund_payment(
        self, session: AsyncSession, *, payment_id: int
    ) -> PaymentModel:
        """Perform a full refund for the given payment."""
        pass

    @abstractmethod
    async def get_user_payments(
        self, session: AsyncSession, *, user_id: int
    ) -> list[PaymentModel]:
        """Return all payments belonging to the given user."""
        pass

    @abstractmethod
    async def get_order_payments(
        self, session: AsyncSession, *, order_id: int
    ) -> list[PaymentModel]:
        """Return all payments associated with the given order."""
        pass

    @abstractmethod
    async def compute_order_remaining_to_pay(
        self, session: AsyncSession, *, order_id: int
    ) -> Decimal:
        """Compute the remaining amount to be paid for the order."""
        pass
