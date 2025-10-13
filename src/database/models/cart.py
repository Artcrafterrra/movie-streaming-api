from base import Base
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), null=False, unique=True)
    items = Column(Integer, ForeignKey("cart_items.id"))


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), null=True)
    movies_id = Column(Integer, ForeignKey("movies.id"), null=True)
    added_at = Column(DateTime, default=datetime.now)
