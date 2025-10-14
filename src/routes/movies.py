from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from database.models.movies import Movie
from schemas.movies import MovieListResponseSchema

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("/", response_model=list[MovieListResponseSchema])
async def list_movies(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
        .order_by(Movie.year.desc())
    )

    result = await db.execute(stmt)
    movies = result.scalars().all()

    return movies
