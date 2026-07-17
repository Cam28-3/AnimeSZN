import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import embed_query
from app.models.anime import Anime

# Pure cosine similarity lets obscure titles that happen to match query text literally
# outrank far more famous, canonical matches (e.g. dozens of niche ninja anime outranking
# Naruto). Blend in a log-scaled popularity boost so well-known titles aren't crowded out.
POPULARITY_WEIGHT = 0.25
POPULARITY_RANK_CEILING = 50_000  # soft normalization ceiling; doesn't need to match catalog size exactly
CANDIDATE_POOL_MULTIPLIER = 5  # rerank within a wider pool than the final requested limit


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


# Convenience wrapper for query-text-based search: embeds the text, then delegates to the
# vector-based search below. Used when the caller only has a natural-language query, not a
# precomputed embedding.
def semantic_search(db: Session, query_text: str, filters: SearchFilters | None = None, limit: int = 10) -> list[SearchResult]:
    query_vector = embed_query(query_text)
    return semantic_search_by_vector(db, query_vector, filters=filters, limit=limit)


def _popularity_boost(popularity_rank: int | None) -> float:
    """0..1, higher for lower (better) ranks. log-scaled so it fades gently, not a cliff."""
    if popularity_rank is None or popularity_rank < 1:
        return 0.0
    return max(0.0, 1 - math.log(popularity_rank) / math.log(POPULARITY_RANK_CEILING))


# Core retrieval: pgvector cosine-distance search against an already-embedded query vector,
# with optional structured filters (status/score/episodes/year), then reranked by a blend of
# similarity and popularity. This is what both semantic_search and find_similar ultimately call.
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

    # Pull a wider candidate pool by pure similarity, then rerank it with a popularity blend --
    # keeps relevance dominant while still letting well-known titles win close calls.
    stmt = stmt.order_by(distance).limit(limit * CANDIDATE_POOL_MULTIPLIER)
    rows = db.execute(stmt).all()

    def blended_score(row) -> float:
        _, dist = row
        similarity = 1 - dist
        return similarity * (1 - POPULARITY_WEIGHT) + _popularity_boost(row[0].popularity_rank) * POPULARITY_WEIGHT

    rows = sorted(rows, key=blended_score, reverse=True)[:limit]

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
