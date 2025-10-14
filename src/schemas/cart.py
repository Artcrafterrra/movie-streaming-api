from pydantic import BaseModel, ConfigDict
from typing import List


class CartBase(BaseModel):
    user_id: int
    items_ids: List[int]


class CartRead(CartBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CartCreate(CartRead):
    pass


class CartUpdate(BaseModel):
    items_ids = List[int]
