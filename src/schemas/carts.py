from datetime import datetime
from typing import List
from pydantic import BaseModel, field_validator, ConfigDict

from schemas.movies import MovieListResponseSchema


class CartItemWithMovie(BaseModel):

    id: int
    movie_id: int
    added_at: datetime
    movie: MovieListResponseSchema

    model_config = ConfigDict(from_attributes=True)


class AddToCartRequest(BaseModel):

    movie_id: int

    @field_validator("movie_id")
    @classmethod
    def validate_movie_id(cls, movie_id):
        if movie_id <= 0:
            raise ValueError("Movie ID must be a positive integer")
        return movie_id


class CartWithMovies(BaseModel):

    id: int
    user_id: int
    items: List[CartItemWithMovie]
    total_items: int
    total_price: float = 0.0

    @field_validator("total_items", mode="before")
    @classmethod
    def calculate_total_items(cls, v, info):
        if "items" in info.data:
            return len(info.data["items"])
        return 0

    model_config = ConfigDict(from_attributes=True)


class CartSummary(BaseModel):

    id: int
    user_id: int
    total_items: int
    total_price: float

    model_config = ConfigDict(from_attributes=True)


class CartValidationResponse(BaseModel):

    is_valid: bool
    errors: List[str] = []
    valid_items_count: int
    total_price: float

    model_config = ConfigDict(from_attributes=True)


class AllCartsResponse(BaseModel):

    carts: List[CartSummary]
    total_carts: int
    page: int
    per_page: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
