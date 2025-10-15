from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from database.models.movies import CertificationEnum


class GenreSchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class StarSchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class DirectorSchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class MovieListResponseSchema(BaseModel):
    id: int
    movie_uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    price: float = Field(
        ...,
    )
    certification: CertificationEnum
    genres: List[GenreSchema] = []
    stars: List[StarSchema] = []
    directors: List[DirectorSchema] = []

    model_config = ConfigDict(from_attributes=True)


class MovieDetailResponseSchema(BaseModel):
    id: int
    movie_uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    price: float = Field(
        ...,
    )
    certification: CertificationEnum
    genres: List[GenreSchema] = []
    stars: List[StarSchema] = []
    directors: List[DirectorSchema] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedMoviesResponse(BaseModel):
    movies: list[MovieListResponseSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int


class MovieCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=250)
    year: int = Field(..., ge=1888, le=datetime.now().year + 1)
    time: int = Field(..., gt=0)
    imdb: float = Field(..., ge=0, le=10)
    votes: int = Field(..., ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None, ge=0)
    description: str = Field(..., min_length=10)
    price: float = Field(..., ge=0)
    certification: CertificationEnum
    genres: List[int] = []
    stars: List[int] = []
    directors: List[int] = []

    @field_validator("genres", "stars", "directors")
    def validate_ids(cls, v):
        if any(i <= 0 for i in v):
            raise ValueError("IDs must be positive integers")
        return v


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(min_length=1, max_length=250)
    year: Optional[int] = Field(ge=1888, le=datetime.now().year + 1)
    time: Optional[int] = Field(gt=0)
    imdb: Optional[float] = Field(ge=0, le=10)
    votes: Optional[int] = Field(ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None, ge=0)
    description: Optional[str] = Field(min_length=10)
    price: Optional[float] = Field(ge=0)
    certification: Optional[CertificationEnum]
    genres: List[int] = []
    stars: List[int] = []
    directors: List[int] = []


class GenreBaseSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class GenreCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class GenreUpdateSchema(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)


class GenreResponseSchema(BaseModel):
    id: int
    name: str = Field(..., min_length=2, max_length=100)
    model_config = ConfigDict(from_attributes=True)


class StarBaseSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class StarCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class StarUpdateSchema(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)


class StarResponseSchema(BaseModel):
    id: int
    name: str = Field(..., min_length=2, max_length=100)
    model_config = ConfigDict(from_attributes=True)


class RatingCreateSchema(BaseModel):
    rating: int = Field(
        ..., ge=1, le=10, description="User rating between 1 and 10"
    )


class RatingResponseSchema(BaseModel):
    movie_id: int
    average_rating: float
    total_ratings: int
