from base import Base
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, UniqueConstraint, func
from typing import List


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    items = Mapped[List["CartItem"]] = relationship(back_populate="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Mapped[int] = mapped_column(primary_key=True)
    cart: Mapped["Cart"] = relationship(back_populates="items")
    cart_id = Mapped[int] = mapped_column(ForeignKey("carts.id"), nullable=False)
    movie_id = Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    added_at = Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("cart_id", "movie_id", "cart_movie_unique")
    )
