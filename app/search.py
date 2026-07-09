from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import embed_query
from app.models.anime import Anime


@dataclass
class SearchFilters:
    status: str | None = None  # airing / finished / upcoming
    min_score: float | None = None
    max_episodes: int | None = None
    min_episodes: int | None = None
    min_year: int | None = None
    max_year: int | None = None


@dataclass
class SearchResult:
    id: int
    title: str
    synopsis: str | None
    score: float | None
    genres: list[str]
    tags: list[str]
    similarity: float  # 1 - cosine distance; higher is more similar


def semantic_search(db: Session, query_text: str, filters: SearchFilters | None = None, limit: int = 10) -> list[SearchResult]:
    query_vector = embed_query(query_text)
    return semantic_search_by_vector(db, query_vector, filters=filters, limit=limit)


def semantic_search_by_vector(
    db: Session, query_vector: list[float], filters: SearchFilters | None = None, limit: int = 10
) -> list[SearchResult]:
    filters = filters or SearchFilters()

    distance = Anime.synopsis_embedding.cosine_distance(query_vector)
    stmt = select(Anime, distance.label("distance")).where(Anime.synopsis_embedding.is_not(None))

    if filters.status:
        stmt = stmt.where(Anime.status == filters.status)
    if filters.min_score is not None:
        stmt = stmt.where(Anime.score >= filters.min_score)
    if filters.max_episodes is not None:
        stmt = stmt.where(Anime.episodes <= filters.max_episodes)
    if filters.min_episodes is not None:
        stmt = stmt.where(Anime.episodes >= filters.min_episodes)
    if filters.min_year is not None:
        stmt = stmt.where(Anime.aired_from.is_not(None)).where(
            Anime.aired_from >= f"{filters.min_year}-01-01"
        )
    if filters.max_year is not None:
        stmt = stmt.where(Anime.aired_from.is_not(None)).where(
            Anime.aired_from <= f"{filters.max_year}-12-31"
        )

    stmt = stmt.order_by(distance).limit(limit)
    rows = db.execute(stmt).all()

    return [
        SearchResult(
            id=anime.id,
            title=anime.title,
            synopsis=anime.synopsis,
            score=float(anime.score) if anime.score is not None else None,
            genres=anime.genres,
            tags=anime.tags,
            similarity=1 - dist,
        )
        for anime, dist in rows
    ]
