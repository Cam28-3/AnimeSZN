from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EMBEDDING_DIM = 1024  # voyage-4 output dimension


class Anime(Base):
    __tablename__ = "anime"

    id: Mapped[int] = mapped_column(primary_key=True)  # AniList id
    title: Mapped[str] = mapped_column(String, nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    episodes: Mapped[int | None] = mapped_column()
    status: Mapped[str | None] = mapped_column(String)
    aired_from: Mapped[date | None] = mapped_column(Date)
    score: Mapped[float | None] = mapped_column(Numeric)
    score_stddev: Mapped[float | None] = mapped_column(Numeric)
    popularity_rank: Mapped[int | None] = mapped_column()
    image_url: Mapped[str | None] = mapped_column(String)
    synopsis_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
