from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List
from database.models.orders import OrderStatusEnum


class OrderItemResponseSchema(BaseModel):
    movie_id: int
    title: str
    price_at_order: Decimal


class OrderResponseSchema(BaseModel):
    id: int
    total_amount: Decimal
    status: OrderStatusEnum
    created_at: datetime
    movies: List[OrderItemResponseSchema]


class OrderCreateSchema(BaseModel):
    movie_ids: List[int] = Field(..., min_length=1)


class OrderMovieSchema(BaseModel):
    movie_id: int
    title: str
    price_at_order: Decimal


class OrderListResponseSchema(BaseModel):
    id: int
    total_amount: Decimal
    status: str
    created_at: datetime
    movies: List[OrderMovieSchema]
