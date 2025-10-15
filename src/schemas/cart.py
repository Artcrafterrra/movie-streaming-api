from pydantic import BaseModel, ConfigDict
from typing import List


class CartBase(BaseModel):
    user_id: int


class CartItemRead(BaseModel):
    id: int
    movie_id: int

    model_config = ConfigDict(from_attributes=True)


class CartRead(CartBase):
    id: int
    items: List[CartItemRead]

    model_config = ConfigDict(from_attributes=True)


class CartCreate(BaseModel):
    user_id: int


class CartUpdate(BaseModel):
    movie_ids: List[int]
