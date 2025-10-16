import enum
import uuid as uuid_pkg
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    Text,
    DECIMAL,
    UniqueConstraint,
    Float,
    Enum,
    Table,
    Column,
    ForeignKey,
    DateTime,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models.base import Base


movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "star_id", ForeignKey("stars.id", ondelete="CASCADE"), primary_key=True
    ),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class CertificationEnum(str, enum.Enum):
    G = "G"
    PG = "PG"
    PG13 = "PG-13"
    R = "R"
    NC17 = "NC-17"


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint(
            "name", "time", "year", name="uq_movie_name_time_year"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_uuid: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid_pkg.uuid4, unique=True
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[float | None] = mapped_column(Float)
    gross: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 2), nullable=False)

    certification: Mapped[CertificationEnum] = mapped_column(
        Enum(CertificationEnum), nullable=False
    )

    genres: Mapped[list["Genre"]] = relationship(
        "Genre", secondary=movie_genres, back_populates="movies"
    )
    stars: Mapped[list["Star"]] = relationship(
        "Star", secondary=movie_stars, back_populates="movies"
    )
    directors: Mapped[list["Director"]] = relationship(
        "Director", secondary=movie_directors, back_populates="movies"
    )

    likes: Mapped[list["MovieLike"]] = relationship(
        "MovieLike", back_populates="movie", cascade="all, delete-orphan"
    )
    comments: Mapped[list["MovieComment"]] = relationship(
        "MovieComment", back_populates="movie", cascade="all, delete-orphan"
    )
    ratings: Mapped[list["MovieRating"]] = relationship(
        "MovieRating", back_populates="movie", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite", back_populates="movie", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItemModel"]] = relationship(
        "OrderItemModel", back_populates="movie", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Movie name={self.name!r}, year={self.year}, cert={self.certification}>"


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        "Movie", secondary=movie_genres, back_populates="genres"
    )


class Star(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        "Movie", secondary=movie_stars, back_populates="stars"
    )


class Director(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        "Movie", secondary=movie_directors, back_populates="directors"
    )


class MovieLike(Base):
    __tablename__ = "movie_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_like"),
        CheckConstraint("value IN (-1, 0, 1)", name="check_like_value_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["UserModel"] = relationship(  # noqa
        back_populates="movie_likes"
    )
    movie: Mapped["Movie"] = relationship(back_populates="likes")


class MovieComment(Base):
    __tablename__ = "movie_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["UserModel"] = relationship(  # noqa
        back_populates="movie_comments"
    )
    movie: Mapped["Movie"] = relationship(back_populates="comments")


class MovieRating(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_rating"),
        CheckConstraint(
            "rating >= 1 AND rating <= 10", name="check_rating_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["UserModel"] = relationship(  # noqa
        back_populates="movie_ratings"
    )
    movie: Mapped["Movie"] = relationship(back_populates="ratings")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_favorite"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["UserModel"] = relationship(  # noqa
        back_populates="favorites"
    )
    movie: Mapped["Movie"] = relationship(back_populates="favorites")
