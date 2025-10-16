from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload

from database import get_db
from database.models import OrderItemModel, UserModel
from database.models.movies import (
    Movie,
    Genre,
    Star,
    Director,
    MovieRating,
    MovieComment,
    MovieLike,
    movie_genres,
    Favorite,
)
from routes.accounts import get_current_user, moderator_required
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
    RatingCreateSchema,
    RatingResponseSchema,
    CommentResponseSchema,
    CommentCreateSchema,
    MovieLikeResponseSchema,
    MovieLikeRequestSchema,
    GenreWithCountSchema,
    FavoriteResponseSchema,
    FavoriteMovieSchema,
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
    _: UserModel = Depends(moderator_required),
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
        await db.refresh(movie)

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
    _: UserModel = Depends(moderator_required),
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
        await db.refresh(movie_for_update)

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
    _: UserModel = Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    purchased = await db.scalar(
        select(OrderItemModel).where(OrderItemModel.movie_id == movie_id)
    )
    if purchased:
        raise HTTPException(
            status_code=400, detail="Cannot delete purchased movie."
        )

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
    response_model=list[GenreWithCountSchema],
    summary="Get list of all genres with movie count",
    status_code=status.HTTP_200_OK,
)
async def get_genres_list(
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Genre.id,
            Genre.name,
            func.count(movie_genres.c.movie_id).label("movie_count"),
        )
        .outerjoin(movie_genres, Genre.id == movie_genres.c.genre_id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )

    result = await db.execute(stmt)
    genres = result.all()

    if not genres:
        return []

    return [
        GenreWithCountSchema(
            id=row.id, name=row.name, movie_count=row.movie_count
        )
        for row in genres
    ]


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
    _: UserModel = Depends(moderator_required),
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
    _: UserModel = Depends(moderator_required),
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
    _: UserModel = Depends(moderator_required),
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


@router.post(
    "/directors/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new director",
)
async def create_director(
    name: str,
    _: UserModel = Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):
    name = name.strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="Director name cannot be empty"
        )

    existing_director = await db.scalar(
        select(Director).where(Director.name == name)
    )
    if existing_director:
        raise HTTPException(status_code=400, detail="Director already exists")

    director = Director(name=name)
    db.add(director)
    await db.commit()
    await db.refresh(director)
    return {
        "message": f"Director '{name}' created successfully",
        "id": director.id,
    }


@router.get(
    "/directors/",
    summary="Get list of all directors",
    status_code=status.HTTP_200_OK,
)
async def get_directors_list(db: AsyncSession = Depends(get_db)):
    stmt = select(Director).order_by(Director.name)
    result = await db.execute(stmt)
    directors = result.scalars().all()

    if not directors:
        raise HTTPException(status_code=404, detail="No directors found")

    return [{"id": d.id, "name": d.name} for d in directors]


@router.patch(
    "/directors/{director_id}/",
    status_code=status.HTTP_200_OK,
    summary="Update a director",
)
async def update_director(
    director_id: int,
    name: str,
    _: UserModel = Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):
    name = name.strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="Director name cannot be empty"
        )

    director = await db.scalar(
        select(Director).where(Director.id == director_id)
    )
    if not director:
        raise HTTPException(status_code=404, detail="Director not found")

    duplicate = await db.scalar(select(Director).where(Director.name == name))
    if duplicate and duplicate.id != director.id:
        raise HTTPException(
            status_code=400, detail="Director with this name already exists"
        )

    director.name = name
    await db.commit()
    await db.refresh(director)
    return {
        "message": "Director updated successfully",
        "id": director.id,
        "name": director.name,
    }


@router.delete(
    "/directors/{director_id}/",
    status_code=status.HTTP_200_OK,
    summary="Delete a director",
)
async def delete_director(
    director_id: int,
    _: UserModel = Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):
    director = await db.scalar(
        select(Director).where(Director.id == director_id)
    )
    if not director:
        raise HTTPException(status_code=404, detail="Director not found")

    await db.delete(director)
    await db.commit()
    return {"message": "Director deleted successfully"}


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


@router.post(
    "/{movie_id}/rating/",
    summary="Rate a movie (create or update)",
)
async def rate_movie(
    movie_id: int,
    rating_data: RatingCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    movie_stmt = select(Movie).where(Movie.id == movie_id)
    movie = (await db.execute(movie_stmt)).scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    stmt = select(MovieRating).where(
        MovieRating.user_id == current_user.id,
        MovieRating.movie_id == movie_id,
    )
    existing = (await db.execute(stmt)).scalars().first()

    if existing:
        existing.rating = rating_data.rating
        await db.commit()
        return {
            "message": "Rating updated successfully.",
            "movie_id": movie_id,
            "rating": rating_data.rating,
        }

    new_rating = MovieRating(
        user_id=current_user.id,
        movie_id=movie_id,
        rating=rating_data.rating,
    )
    db.add(new_rating)
    await db.commit()
    return {
        "message": "Rating created successfully.",
        "movie_id": movie_id,
        "rating": rating_data.rating,
    }


@router.get(
    "/{movie_id}/rating/",
    response_model=RatingResponseSchema,
    summary="Get average rating and total count for a movie",
)
async def get_movie_rating(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(
        func.avg(MovieRating.rating).label("average_rating"),
        func.count(MovieRating.id).label("total_ratings"),
    ).where(MovieRating.movie_id == movie_id)

    result = await db.execute(stmt)
    avg, total = result.first()

    if not total or total == 0:
        return RatingResponseSchema(
            movie_id=movie_id,
            average_rating=0.0,
            total_ratings=0,
        )

    return RatingResponseSchema(
        movie_id=movie_id,
        average_rating=round(float(avg), 1),
        total_ratings=total,
    )


@router.delete(
    "/{movie_id}/rating/",
    summary="Remove your rating for a movie",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_movie_rating(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    stmt = select(MovieRating).where(
        MovieRating.movie_id == movie_id,
        MovieRating.user_id == current_user.id,
    )
    rating = (await db.execute(stmt)).scalars().first()

    if not rating:
        raise HTTPException(
            status_code=404, detail="Rating not found for this user."
        )

    await db.delete(rating)
    await db.commit()
    return None


@router.post(
    "/{movie_id}/comments/",
    response_model=CommentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    movie_id: int,
    comment_data: CommentCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    stmt = select(Movie).where(Movie.id == movie_id)
    movie = (await db.execute(stmt)).scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    comment = MovieComment(
        user_id=current_user.id,
        movie_id=movie_id,
        body=comment_data.body,
    )

    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.get(
    "/{movie_id}/comments/",
    response_model=list[CommentResponseSchema],
    summary="Get all comments for a movie",
)
async def get_comments(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MovieComment)
        .where(MovieComment.movie_id == movie_id)
        .order_by(MovieComment.created_at.desc())
    )

    result = await db.execute(stmt)
    comments = result.scalars().unique().all()

    if not comments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No comments found."
        )

    return comments


@router.delete(
    "/comments/{comment_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete your comment by ID",
)
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    stmt = select(MovieComment).where(MovieComment.id == comment_id)
    comment = (await db.execute(stmt)).scalars().first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can delete only your own comments."
        )

    await db.delete(comment)
    await db.commit()
    return None


@router.post(
    "/{movie_id}/reaction/",
    response_model=MovieLikeResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Add, change, or remove a movie reaction.",
    description="(1 = like / - 1 = dislike / 0 =  neutral)",
)
async def react_to_movie(
    movie_id: int,
    data: MovieLikeRequestSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id))
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    existing = await db.scalar(
        select(MovieLike).where(
            MovieLike.user_id == current_user.id,
            MovieLike.movie_id == movie_id,
        )
    )

    message = ""
    if existing:
        if data.value == 0:
            await db.delete(existing)
            message = "Reaction removed."
        else:
            existing.value = data.value
            message = "Reaction updated."
    else:
        if data.value == 0:
            message = "No reaction to remove."
        else:
            db.add(
                MovieLike(
                    user_id=current_user.id,
                    movie_id=movie_id,
                    value=data.value,
                )
            )
            message = "Reaction added."

    await db.commit()

    likes = (
        await db.scalar(
            select(func.count()).where(
                MovieLike.movie_id == movie_id, MovieLike.value == 1
            )
        )
        or 0
    )
    dislikes = (
        await db.scalar(
            select(func.count()).where(
                MovieLike.movie_id == movie_id, MovieLike.value == -1
            )
        )
        or 0
    )
    total_score = likes + dislikes

    return MovieLikeResponseSchema(
        movie_id=movie_id,
        likes_count=likes,
        dislikes_count=dislikes,
        total_score=total_score,
        message=message,
    )


@router.get(
    "/{movie_id}/reactions/",
    response_model=MovieLikeResponseSchema,
    summary="Get like/dislike statistics for a movie",
)
async def get_movie_reactions(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id))
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    likes = (
        await db.scalar(
            select(func.count()).where(
                MovieLike.movie_id == movie_id, MovieLike.value == 1
            )
        )
        or 0
    )
    dislikes = (
        await db.scalar(
            select(func.count()).where(
                MovieLike.movie_id == movie_id, MovieLike.value == -1
            )
        )
        or 0
    )
    total_score = likes + dislikes

    return MovieLikeResponseSchema(
        movie_id=movie_id,
        likes_count=likes,
        dislikes_count=dislikes,
        total_score=total_score,
        message="Reaction stats fetched successfully.",
    )


@router.get(
    "/genres/{genre_id}/movies/",
    response_model=PaginatedMoviesResponse,
    summary="Get all movies related to a specific genre",
    status_code=status.HTTP_200_OK,
)
async def get_movies_by_genre(
    genre_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=20, description="Movies per page"),
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
    genre = await db.scalar(select(Genre).where(Genre.id == genre_id))
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre not found.",
        )

    offset = (page - 1) * per_page

    stmt = (
        select(Movie)
        .join(movie_genres)
        .where(movie_genres.c.genre_id == genre_id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
    )

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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No movies found for this genre.",
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
    movies = result.scalars().unique().all()

    total_pages = (total_items + per_page - 1) // per_page

    return PaginatedMoviesResponse(
        movies=[MovieListResponseSchema.model_validate(m) for m in movies],
        prev_page=(
            f"/movies/genres/{genre_id}/movies/?page={page-1}&per_page={per_page}"
            if page > 1
            else None
        ),
        next_page=(
            f"/movies/genres/{genre_id}/movies/?page={page+1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post(
    "/favorites/{movie_id}/",
    status_code=status.HTTP_201_CREATED,
    summary="Add movie to favorites",
)
async def add_to_favorites(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id))
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    existing = await db.scalar(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.movie_id == movie_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Movie already in favorites"
        )

    favorite = Favorite(user_id=current_user.id, movie_id=movie_id)
    db.add(favorite)
    await db.commit()
    return {"message": "Movie added to favorites successfully"}


@router.delete(
    "/favorites/{movie_id}/",
    status_code=status.HTTP_200_OK,
    summary="Remove movie from favorites",
)
async def remove_from_favorites(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorite = await db.scalar(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.movie_id == movie_id,
        )
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Movie not in favorites")

    await db.delete(favorite)
    await db.commit()
    return {"message": "Movie removed from favorites successfully"}


@router.get(
    "/favorites/",
    response_model=FavoriteResponseSchema,
    summary="Get user's favorite movies with pagination, filters, and sorting",
)
async def get_favorites(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=20, description="Movies per page"),
    sort_by: str = Query(
        "year", description="Sort by field: year, imdb, price"
    ),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Search movies in favorites"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    offset = (page - 1) * per_page

    stmt = (
        select(Favorite)
        .join(Favorite.movie)
        .where(Favorite.user_id == current_user.id)
        .options(
            selectinload(Favorite.movie).selectinload(Movie.genres),
            selectinload(Favorite.movie).selectinload(Movie.directors),
            selectinload(Favorite.movie).selectinload(Movie.stars),
        )
    )

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

    count_stmt = stmt.with_only_columns(func.count(Favorite.id)).order_by(None)
    total_items = (await db.execute(count_stmt)).scalar() or 0
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No favorites found.")

    allowed_sort_fields = {"year", "imdb", "price"}
    if sort_by not in allowed_sort_fields:
        sort_by = "year"
    sort_column = getattr(Movie, sort_by)
    stmt = stmt.order_by(
        sort_column.desc() if order == "desc" else sort_column.asc()
    )

    stmt = stmt.offset(offset).limit(per_page)
    result = await db.execute(stmt)
    favorites = result.scalars().unique().all()

    total_pages = (total_items + per_page - 1) // per_page

    return FavoriteResponseSchema(
        favorites=[
            FavoriteMovieSchema.model_validate(fav) for fav in favorites
        ],
        total_items=total_items,
        total_pages=total_pages,
        page=page,
        per_page=per_page,
    )
