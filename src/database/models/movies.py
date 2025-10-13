from sqlalchemy import String, Integer, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    rating: Mapped[float | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<Movie id={self.id} title={self.title!r}>"
