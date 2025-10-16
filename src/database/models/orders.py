import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Integer,
    DateTime,
    func,
    DECIMAL,
    ForeignKey,
    UniqueConstraint,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models.base import Base


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderModel(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_user_order_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[OrderStatusEnum] = mapped_column(
        Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.PENDING
    )

    total_amount: Mapped[Decimal | None] = mapped_column(
        DECIMAL(10, 2), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["UserModel"] = relationship(back_populates="orders")  # noqa
    order_items: Mapped[list["OrderItemModel"]] = relationship(
        "OrderItemModel",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id}, user={self.user_id}, status={self.status}>"
        )


class OrderItemModel(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "movie_id", name="uq_order_movie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    price_at_order: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False
    )

    order: Mapped["OrderModel"] = relationship(back_populates="order_items")
    movie: Mapped["Movie"] = relationship(back_populates="order_items")  # noqa

    def __repr__(self) -> str:
        return (
            f"<OrderItem order={self.order_id}, "
            f"movie={self.movie_id}, price={self.price_at_order}>"
        )
