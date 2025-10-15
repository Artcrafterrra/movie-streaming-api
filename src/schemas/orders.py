from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator, ConfigDict

from database.models.orders import OrderStatusEnum


class OrderItemCreateSchema(BaseModel):
    movie_id: int

    @field_validator("movie_id")
    @classmethod
    def validate_movie_id(cls, movie_id):
        if movie_id <= 0:
            raise ValueError("Movie ID must be a positive integer")
        return movie_id


class OrderItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    movie_id: int
    price: float


class OrderItemDetailSchema(OrderItemResponseSchema):
    movie_title: Optional[str] = None
    movie_year: Optional[int] = None
    movie_genre: Optional[str] = None


class OrderBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: float


class OrderCreateSchema(BaseModel):
    movie_ids: List[int]

    @field_validator("movie_ids")
    @classmethod
    def validate_cart_items(cls, movie_ids):
        if not movie_ids:
            raise ValueError("Cart cannot be empty")
        if len(movie_ids) != len(set(movie_ids)):
            raise ValueError("Duplicate movie ids in cart")
        if any(movie_id <= 0 for movie_id in movie_ids):
            raise ValueError("Movie IDs must be a positive integer")


class OrderUpdateSchema(BaseModel):
    status: OrderStatusEnum


class OrderResponseSchema(OrderBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    order_items: List[OrderItemResponseSchema]


class OrderDetailResponseSchema(OrderResponseSchema):
    order_items: List[OrderItemDetailSchema]


class OrderListItemSchema(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: float
    order_items: List[OrderItemResponseSchema]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 13,
                    "created_at": "2025-10-14T15:34:23Z",
                    "status": "pending",
                    "total_amount": 134.50,
                    "order_items": [
                        {"id": 1, "movie_id": 42, "price": 9.99},
                        {"id": 2, "movie_id": 43, "price": 12.50},
                    ],
                }
            ]
        },
    )


class OrderListResponseSchema(BaseModel):
    orders: List[OrderResponseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "orders": [
                        {
                            "id": 13,
                            "user_id": 2,
                            "created_at": "2025-10-14 15:34:23",
                            "status": "pending",
                            "total_amount": 134.50,
                            "order_items": [
                                {"id": 1, "movie_id": 42, "price": 9.99},
                                {"id": 2, "movie_id": 43, "price": 12.50},
                            ],
                        }
                    ],
                    "prev_page": "/theater/movies/?page=1&per_page=1",
                    "next_page": "/theater/movies/?page=3&per_page=1",
                    "total_pages": 456,
                    "total_items": 456,
                }
            ]
        },
    )


class OrderCancelRequestSchema(BaseModel):
    reason: Optional[str] = None


class OrderCancelResponseSchema(OrderResponseSchema):
    message: str


class OrderConfirmPaymentSchema(BaseModel):
    payment_id: str
