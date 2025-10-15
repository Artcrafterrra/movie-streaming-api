from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional, Any

from sqlalchemy.orm import Session

from database.models.payments import PaymentStatusEnum


class PaymentServiceInterface(ABC):
    """Interface describing the payment service contract."""

    @abstractmethod
    def create_payment(
        self,
        session: Session,
        *,
        user_id: int,
        order_id: int,
        amount: Decimal | float | int,
        external_payment_id: Optional[str] = None,
        status: PaymentStatusEnum = PaymentStatusEnum.SUCCESSFUL,
    ) -> Any:
        """Create a payment and persist a snapshot of order items at payment time."""
        pass

    @abstractmethod
    def cancel_payment(self, session: Session, *, payment_id: int) -> Any:
        """Mark a payment as canceled."""
        pass

    @abstractmethod
    def refund_payment(self, session: Session, *, payment_id: int) -> Any:
        """Perform a full refund for the given payment."""
        pass

    @abstractmethod
    def get_user_payments(
        self, session: Session, *, user_id: int
    ) -> list[Any]:
        """Return all payments belonging to the given user."""
        pass

    @abstractmethod
    def get_order_payments(
        self, session: Session, *, order_id: int
    ) -> list[Any]:
        """Return all payments associated with the given order."""
        pass

    @abstractmethod
    def compute_order_remaining_to_pay(
        self, session: Session, *, order_id: int
    ) -> Decimal:
        """Compute the remaining amount to be paid for the order."""
        pass
