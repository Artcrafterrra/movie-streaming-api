import enum
import uuid as uuid_pkg
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
    G = "G"  # General Audience
    PG = "PG"  # Parental Guidance Suggested
    PG13 = "PG-13"  # Parents Strongly Cautioned
    R = "R"  # Restricted
    NC17 = "NC-17"  # Adults Only


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
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)

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
