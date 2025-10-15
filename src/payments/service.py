from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from database.models.orders import OrderModel, OrderStatusEnum
from database.models.payments import (
    PaymentModel,
    PaymentItemModel,
    PaymentStatusEnum,
)
from .exceptions import (
    OrderNotFoundError,
    OrderOwnershipError,
    OrderStatusError,
    AmountMismatchError,
    DuplicateExternalPaymentError,
    PaymentNotFoundError,
)
from .interfaces import PaymentServiceInterface
from .repository import PaymentRepository


def _to_decimal(value: Decimal | float | int) -> Decimal:
    """Normalize numeric values to Decimal for money-safe calculations."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class PaymentService(PaymentServiceInterface):
    """Business logic for creating, canceling and refunding payments."""

    def __init__(self, repository: Optional[PaymentRepository] = None) -> None:
        self.repo = repository or PaymentRepository()

    def _load_order(self, session: Session, order_id: int) -> OrderModel:
        """Fetch order with items or raise."""
        order = self.repo.get_order_with_items(session, order_id)
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return order

    def _assert_order_belongs_to_user(self, order: OrderModel, user_id: int) -> None:
        """Ensure the order is owned by the acting user."""
        if order.user_id != user_id:
            raise OrderOwnershipError("Order does not belong to the user")

    def _assert_order_payable(self, order: OrderModel) -> None:
        """Ensure the order can be paid in its current state."""
        if order.status == OrderStatusEnum.CANCELED:
            raise OrderStatusError("Order is canceled and cannot be paid")

    def _recalculate_and_update_order_status(self, session: Session, order: OrderModel) -> None:
        """Recompute aggregate payment state and update order status accordingly."""
        paid_total = self.repo.sum_successful_payments(session, order.id)
        order_total = _to_decimal(order.total_amount)
        if paid_total >= order_total and order.status != OrderStatusEnum.PAID:
            order.status = OrderStatusEnum.PAID
            session.add(order)
        elif paid_total == Decimal("0") and order.status == OrderStatusEnum.PAID:
            order.status = OrderStatusEnum.PENDING
            session.add(order)

    def create_payment(
        self,
        session: Session,
        *,
        user_id: int,
        order_id: int,
        amount: Decimal | float | int,
        external_payment_id: Optional[str] = None,
        status: PaymentStatusEnum = PaymentStatusEnum.SUCCESSFUL,
    ) -> PaymentModel:
        """Create a payment, persist snapshot items, and update order status if necessary."""
        if external_payment_id and self.repo.external_payment_exists(session, external_payment_id):
            raise DuplicateExternalPaymentError(
                "Payment with this external_payment_id already exists"
            )

        order = self._load_order(session, order_id)
        self._assert_order_belongs_to_user(order, user_id)
        self._assert_order_payable(order)

        requested_amount = _to_decimal(amount)
        if requested_amount <= 0:
            raise AmountMismatchError("Amount must be greater than zero")

        already_paid = self.repo.sum_successful_payments(session, order.id)
        remaining = _to_decimal(order.total_amount) - already_paid
        if requested_amount > remaining:
            raise AmountMismatchError(
                f"Amount exceeds remaining to pay: requested={requested_amount}, remaining={remaining}"
            )

        payment = PaymentModel(
            user_id=user_id,
            order_id=order_id,
            amount=requested_amount,
            status=status,
            external_payment_id=external_payment_id,
        )
        self.repo.save_payment(session, payment)

        for oi in order.items:
            self.repo.save_payment_item(
                session,
                PaymentItemModel(
                    payment_id=payment.id,
                    order_item_id=oi.id,
                    price_at_payment=_to_decimal(oi.price_at_order),
                ),
            )

        if status == PaymentStatusEnum.SUCCESSFUL:
            self._recalculate_and_update_order_status(session, order)

        session.flush()
        return payment

    def cancel_payment(self, session: Session, *, payment_id: int) -> PaymentModel:
        """Mark a non-refunded payment as canceled and recalculate order status."""
        payment = self.repo.get_payment_by_id(session, payment_id)
        if not payment:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")

        if payment.status == PaymentStatusEnum.REFUNDED:
            return payment  # No-op: already refunded.

        payment.status = PaymentStatusEnum.CANCELED
        session.add(payment)

        order = self._load_order(session, payment.order_id)
        self._recalculate_and_update_order_status(session, order)

        session.flush()
        return payment

    def refund_payment(self, session: Session, *, payment_id: int) -> PaymentModel:
        """Perform a full refund for a payment and recalculate order status."""
        payment = self.repo.get_payment_by_id(session, payment_id)
        if not payment:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")

        payment.status = PaymentStatusEnum.REFUNDED
        session.add(payment)

        order = self._load_order(session, payment.order_id)
        self._recalculate_and_update_order_status(session, order)

        session.flush()
        return payment

    def get_user_payments(self, session: Session, *, user_id: int) -> list[PaymentModel]:
        """Return all payments for the given user."""
        return self.repo.list_user_payments(session, user_id)

    def get_order_payments(self, session: Session, *, order_id: int) -> list[PaymentModel]:
        """Return all payments linked to the given order."""
        return self.repo.list_order_payments(session, order_id)

    def compute_order_remaining_to_pay(self, session: Session, *, order_id: int) -> Decimal:
        """Compute remaining amount to pay for a given order."""
        order = self._load_order(session, order_id)
        already_paid = self.repo.sum_successful_payments(session, order.id)
        return _to_decimal(order.total_amount) - already_paid
