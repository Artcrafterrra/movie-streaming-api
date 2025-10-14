from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Integer,
    DateTime,
    func,
    DECIMAL,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLAlchemyEnum

from database.models import Movie, UserModel
from database.models.base import Base


class OrderStatusEnum(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[OrderStatusEnum] = mapped_column(
        SQLAlchemyEnum(OrderStatusEnum),
        nullable=False,
        default=OrderStatusEnum.PENDING,
    )
    total_amount: Mapped[float] = mapped_column(DECIMAL(10, 2))

    user: Mapped[UserModel] = relationship(
        "UserModel",
    )

    items: Mapped[list["OrderItemModel"]] = relationship(
        "OrderItemModel",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    price_at_order: Mapped[float] = mapped_column(
        DECIMAL(10, 2), nullable=False
    )

    order: Mapped["OrderModel"] = relationship(
        "OrderModel", back_populates="items"
    )
    movie: Mapped["Movie"] = relationship(
        "Movie",
    )

    __table_args__ = (
        UniqueConstraint(
            "order_id", "movie_id", name="unique_order_movie_constraint"
        ),
    )
