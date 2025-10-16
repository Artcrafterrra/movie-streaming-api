from datetime import datetime
from enum import Enum
from typing import List

from sqlalchemy import (
    Integer,
    DateTime,
    DECIMAL,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLAlchemyEnum

from database.models.base import Base
from database.models.accounts import UserModel
from database.models.orders import OrderItemModel, OrderModel


class PaymentStatusEnum(str, Enum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    PENDING = "pending"


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SQLAlchemyEnum(PaymentStatusEnum),
        nullable=False,
        default=PaymentStatusEnum.SUCCESSFUL,
    )
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255))

    user: Mapped["UserModel"] = relationship("UserModel")
    order: Mapped["OrderModel"] = relationship(
        "OrderModel", backref="payments"
    )
    items: Mapped[List["PaymentItemModel"]] = relationship(
        "PaymentItemModel",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PaymentItemModel(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    price_at_payment: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False
    )

    payment: Mapped["PaymentModel"] = relationship(
        "PaymentModel", back_populates="items"
    )
    order_item: Mapped["OrderItemModel"] = relationship("OrderItemModel")
