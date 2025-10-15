from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload

from database import get_db
from database.models.movies import Movie, Genre, Star, Director
from schemas.movies import (
    MovieListResponseSchema,
    MovieDetailResponseSchema,
    PaginatedMoviesResponse,
    MovieCreateSchema,
)

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get(
    "/",
    response_model=PaginatedMoviesResponse,
    summary="Get a paginated list of movies",
    status_code=status.HTTP_200_OK,
)
async def get_movie_list(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=20, description="Movies per page"),
    year: int | None = Query(None, description="Filter by release year"),
    min_imdb: float | None = Query(
        None, ge=0, le=10, description="Minimum IMDb rating"
    ),
    max_imdb: float | None = Query(
        None, ge=0, le=10, description="Maximum IMDb rating"
    ),
    sort_by: str = Query(
        "year", description="Sort by field: year, imdb, price, votes"
    ),
    order: str = Query(
        "desc", pattern="^(asc|desc)$", description="Sort order (asc or desc)"
    ),
    search: str | None = Query(
        None, description="Search in title, description, actor or director"
    ),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page

    stmt = select(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.stars),
        selectinload(Movie.directors),
    )

    if year:
        stmt = stmt.where(Movie.year == year)
    if min_imdb:
        stmt = stmt.where(Movie.imdb >= min_imdb)
    if max_imdb:
        stmt = stmt.where(Movie.imdb <= max_imdb)

    if search:
        stmt = (
            stmt.join(Movie.stars, isouter=True)
            .join(Movie.directors, isouter=True)
            .where(
                Movie.name.ilike(f"%{search}%")
                | Movie.description.ilike(f"%{search}%")
                | Star.name.ilike(f"%{search}%")
                | Director.name.ilike(f"%{search}%")
            )
        )

    count_stmt = stmt.with_only_columns(func.count(Movie.id)).order_by(None)
    total_items = (await db.execute(count_stmt)).scalar() or 0
    if total_items == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No movies found."
        )

    allowed_sort_fields = {"year", "imdb", "price", "votes"}
    if sort_by not in allowed_sort_fields:
        sort_by = "year"
    sort_column = getattr(Movie, sort_by)
    stmt = stmt.order_by(
        sort_column.desc() if order == "desc" else sort_column.asc()
    )

    stmt = stmt.offset(offset).limit(per_page)
    result = await db.execute(stmt)
    movies = result.scalars().all()

    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No movies match the given criteria.",
        )

    total_pages = (total_items + per_page - 1) // per_page

    return PaginatedMoviesResponse(
        movies=[MovieListResponseSchema.model_validate(m) for m in movies],
        prev_page=(
            f"/movies/?page={page-1}&per_page={per_page}" if page > 1 else None
        ),
        next_page=(
            f"/movies/?page={page+1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get(
    "/{movie_id}",
    response_model=MovieDetailResponseSchema,
    summary="Get movie details by ID",
    status_code=status.HTTP_200_OK,
)
async def get_movie_by_id(movie_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Movie)
        .options(
            joinedload(Movie.genres),
            joinedload(Movie.stars),
            joinedload(Movie.directors),
        )
        .where(Movie.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    return MovieDetailResponseSchema.model_validate(movie)


@router.post(
    "/",
    response_model=MovieDetailResponseSchema,
    summary="Create new movie",
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
    movie_data: MovieCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    existing_stmt = select(Movie).where(
        Movie.name == movie_data.name,
        Movie.year == movie_data.year,
        Movie.time == movie_data.time,
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Movie '{movie_data.name}' ({movie_data.year}) already exists.",
        )

    try:
        movie = Movie(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=movie_data.certification,
        )

        if movie_data.genres:
            result = await db.execute(
                select(Genre).where(Genre.id.in_(movie_data.genres))
            )
            movie.genres.extend(result.scalars().all())

        if movie_data.stars:
            result = await db.execute(
                select(Star).where(Star.id.in_(movie_data.stars))
            )
            movie.stars.extend(result.scalars().all())

        if movie_data.directors:
            result = await db.execute(
                select(Director).where(Director.id.in_(movie_data.directors))
            )
            movie.directors.extend(result.scalars().all())

        db.add(movie)
        await db.commit()

        stmt = (
            select(Movie)
            .options(
                selectinload(Movie.genres),
                selectinload(Movie.stars),
                selectinload(Movie.directors),
            )
            .where(Movie.id == movie.id)
        )
        result = await db.execute(stmt)
        movie_full = result.scalars().first()

        return MovieDetailResponseSchema.model_validate(movie_full)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input data.",
        )
