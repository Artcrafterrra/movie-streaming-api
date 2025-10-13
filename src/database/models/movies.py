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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base


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

    def __repr__(self) -> str:
        return f"<Movie name={self.name!r}, year={self.year}, cert={self.certification}>"
