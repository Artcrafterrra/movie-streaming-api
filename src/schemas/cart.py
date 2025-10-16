from re import I
from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime


class CartBase(BaseModel):
    user_id: int


class CartItemCreate(BaseModel):
    id: int
    cart_id: int
    movie_id: int


class CartItemRead(BaseModel):
    id: int
    movie_id: int

    model_config = ConfigDict(from_attributes=True)


class CartItemDelete(BaseModel):
    id: int


class CartRead(CartBase):
    id: int
    items: List[CartItemRead]

    model_config = ConfigDict(from_attributes=True)


class CartCreate(BaseModel):
    user_id: int


class CartUpdate(BaseModel):
    movie_ids: List[int]
