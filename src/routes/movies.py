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
    MovieUpdateSchema,
    GenreResponseSchema,
    GenreCreateSchema,
    StarResponseSchema,
    StarCreateSchema,
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


@router.patch(
    "/{movie_id}/",
    summary="Update the movie",
    response_model=MovieDetailResponseSchema,
)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
        .where(Movie.id == movie_id)
    )
    result = await db.execute(stmt)
    movie_for_update = result.scalars().first()

    if not movie_for_update:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    data = movie_data.model_dump(exclude_unset=True)

    for field, value in data.items():
        if field not in {"genres", "stars", "directors"}:
            setattr(movie_for_update, field, value)

    if "genres" in data:
        result = await db.execute(
            select(Genre).where(Genre.id.in_(data["genres"]))
        )
        movie_for_update.genres.clear()
        movie_for_update.genres.extend(result.scalars().all())

    if "stars" in data:
        result = await db.execute(
            select(Star).where(Star.id.in_(data["stars"]))
        )
        movie_for_update.stars.clear()
        movie_for_update.stars.extend(result.scalars().all())

    if "directors" in data:
        result = await db.execute(
            select(Director).where(Director.id.in_(data["directors"]))
        )
        movie_for_update.directors.clear()
        movie_for_update.directors.extend(result.scalars().all())

    try:
        await db.commit()

        stmt = (
            select(Movie)
            .options(
                selectinload(Movie.genres),
                selectinload(Movie.stars),
                selectinload(Movie.directors),
            )
            .where(Movie.id == movie_for_update.id)
        )
        refreshed = (await db.execute(stmt)).scalars().first()

        return MovieDetailResponseSchema.model_validate(refreshed)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input data.",
        )


@router.delete(
    "/{movie_id}/",
    summary="Delete a movie by ID",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    await db.delete(movie)
    await db.commit()
    return None


@router.get(
    "/genres/",
    response_model=list[GenreResponseSchema],
    summary="Get list of all genres",
    status_code=status.HTTP_200_OK,
)
async def get_genres_list(db: AsyncSession = Depends(get_db)):
    stmt = select(Genre).order_by(Genre.id.asc())
    result = await db.execute(stmt)
    genres = result.scalars().all()

    if not genres:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genres found.",
        )

    return [GenreResponseSchema.model_validate(g) for g in genres]


@router.get(
    "/genres/{genre_id}/",
    response_model=GenreResponseSchema,
    summary="Get genre by id",
    status_code=status.HTTP_200_OK,
)
async def get_genre_by_id(genre_id: int, db: AsyncSession = Depends(get_db)):

    stmt = select(Genre).where(Genre.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre with the given ID was not found.",
        )

    return GenreResponseSchema.model_validate(genre)


@router.post(
    "/genres/",
    response_model=GenreResponseSchema,
    summary="Create a new genre",
    status_code=status.HTTP_201_CREATED,
)
async def create_new_genre(
    genre_data: GenreCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    existing_stmt = select(Genre).where(Genre.name == genre_data.name)
    existing_result = await db.execute(existing_stmt)
    existing_genre = existing_result.scalars().first()

    if existing_genre:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Genre '{genre_data.name}' already exists.",
        )

    new_genre = Genre(name=genre_data.name)

    db.add(new_genre)
    await db.commit()
    await db.refresh(new_genre)

    return GenreResponseSchema.model_validate(new_genre)


@router.patch(
    "/genres/{genre_id}/",
    response_model=GenreResponseSchema,
    summary="Update genre by ID",
    status_code=status.HTTP_200_OK,
)
async def update_genre(
    genre_id: int,
    genre_data: GenreCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Genre).where(Genre.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre with the given ID was not found.",
        )

    genre.name = genre_data.name
    await db.commit()
    await db.refresh(genre)
    return GenreResponseSchema.model_validate(genre)


@router.delete(
    "/genres/{genre_id}/",
    summary="Delete genre by ID",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_genre(
    genre_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Genre).where(Genre.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre with the given ID was not found.",
        )

    await db.delete(genre)
    await db.commit()
    return None


@router.get(
    "/actors/",
    response_model=list[StarResponseSchema],
    summary="Get list of all actors",
    status_code=status.HTTP_200_OK,
)
async def get_actors_list(db: AsyncSession = Depends(get_db)):
    stmt = select(Star).order_by(Star.id)
    result = await db.execute(stmt)
    actors = result.scalars().all()

    if not actors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No actors found.",
        )

    return [StarResponseSchema.model_validate(a) for a in actors]


@router.get(
    "/actors/{actor_id}/",
    response_model=StarResponseSchema,
    summary="Get actor by id",
    status_code=status.HTTP_200_OK,
)
async def get_actor_by_id(
    actor_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Star).where(Star.id == actor_id)
    result = await db.execute(stmt)
    actor = result.scalars().first()

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor with the given ID was not found.",
        )

    return StarResponseSchema.model_validate(actor)


@router.post(
    "/actors/",
    response_model=StarResponseSchema,
    summary="Create a new actor",
    status_code=status.HTTP_201_CREATED,
)
async def create_new_actor(
    actor_data: StarCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    existing_stmt = select(Star).where(Star.name == actor_data.name)
    existing_result = await db.execute(existing_stmt)
    existing_actor = existing_result.scalars().first()

    if existing_actor:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Actor '{actor_data.name}' already exists.",
        )

    new_actor = Star(name=actor_data.name)

    db.add(new_actor)
    await db.commit()
    await db.refresh(new_actor)

    return StarResponseSchema.model_validate(new_actor)


@router.patch(
    "/actors/{actor_id}/",
    response_model=StarResponseSchema,
    summary="Update actor by ID",
    status_code=status.HTTP_200_OK,
)
async def update_actor(
    actor_id: int,
    actor_data: StarCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Star).where(Star.id == actor_id)
    result = await db.execute(stmt)
    actor = result.scalars().first()

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor with the given ID was not found.",
        )

    actor.name = actor_data.name
    await db.commit()
    await db.refresh(actor)
    return StarResponseSchema.model_validate(actor)


@router.delete(
    "/actors/{actor_id}/",
    summary="Delete actor by ID",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_actor(
    actor_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Star).where(Star.id == actor_id)
    result = await db.execute(stmt)
    actor = result.scalars().first()

    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actor with the given ID was not found.",
        )

    await db.delete(actor)
    await db.commit()
    return None
