from pydantic import BaseModel
from typing import List


class CartBase(BaseModel):
    user_id: int
    items_ids: List[int]


class CartRead(CartBase):
    id: int

    class Config:
        from_attributes = True
