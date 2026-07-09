from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.anime import Anime
from app.models.reception import ReceptionSignal
from app.search import SearchFilters, semantic_search, semantic_search_by_vector

_FILTER_PROPERTIES = {
    "status": {"type": "string", "enum": ["airing", "finished", "upcoming"]},
    "min_score": {"type": "number"},
    "max_episodes": {"type": "integer"},
    "min_episodes": {"type": "integer"},
    "min_year": {"type": "integer"},
    "max_year": {"type": "integer"},
}

TOOL_DEFINITIONS = [
    {
        "name": "search_by_title",
        "description": "Fuzzy/substring title lookup. Use when the user names a specific anime.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Title text to search for"}},
            "required": ["query"],
        },
    },
    {
        "name": "semantic_search",
        "description": (
            "Mood/theme/description-based search over anime synopses and tags. "
            "Use for requests like 'something like a psychological thriller'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {"type": "string", "description": "Natural-language description of what the user wants"},
                **_FILTER_PROPERTIES,
            },
            "required": ["query_text"],
        },
    },
    {
        "name": "find_similar",
        "description": (
            "Find anime similar to a known anime by embedding nearest-neighbor. "
            "Use for 'more like X' requests -- resolve X with search_by_title first if needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"anime_id": {"type": "integer"}, **_FILTER_PROPERTIES},
            "required": ["anime_id"],
        },
    },
    {
        "name": "check_reception",
        "description": (
            "Look up community reception (sentiment ratio, summary, widely_criticized/mixed/none flag) "
            "for a candidate anime. Must be called on every candidate before it is recommended."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"anime_id": {"type": "integer"}},
            "required": ["anime_id"],
        },
    },
    {
        "name": "respond",
        "description": (
            "Finalize the answer to the user. Always end the conversation by calling this tool -- "
            "never answer in plain text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Short framing message for the overall answer"},
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "anime_id": {"type": "integer"},
                            "rationale": {"type": "string", "description": "Why this title matches the request"},
                            "caveat": {
                                "type": "string",
                                "description": "Reception caveat if reception is mixed/widely_criticized, otherwise omit",
                            },
                        },
                        "required": ["anime_id", "rationale"],
                    },
                },
            },
            "required": ["message", "recommendations"],
        },
    },
]


def _filters_from_input(input: dict) -> SearchFilters:
    return SearchFilters(
        status=input.get("status"),
        min_score=input.get("min_score"),
        max_episodes=input.get("max_episodes"),
        min_episodes=input.get("min_episodes"),
        min_year=input.get("min_year"),
        max_year=input.get("max_year"),
    )


def _serialize_results(results) -> list[dict]:
    return [
        {
            "anime_id": r.id,
            "title": r.title,
            "score": r.score,
            "genres": r.genres,
            "tags": r.tags,
            "similarity": round(r.similarity, 3),
        }
        for r in results
    ]


def tool_search_by_title(db: Session, query: str, limit: int = 5) -> list[dict]:
    stmt = (
        select(Anime)
        .where(Anime.title.ilike(f"%{query}%"))
        .order_by(Anime.popularity_rank.asc().nulls_last())
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    return [
        {"anime_id": a.id, "title": a.title, "score": float(a.score) if a.score is not None else None, "episodes": a.episodes, "status": a.status}
        for a in rows
    ]


def tool_semantic_search(db: Session, query_text: str, **filter_kwargs) -> list[dict]:
    results = semantic_search(db, query_text, filters=_filters_from_input(filter_kwargs), limit=8)
    return _serialize_results(results)


def tool_find_similar(db: Session, anime_id: int, **filter_kwargs) -> list[dict] | dict:
    anime = db.get(Anime, anime_id)
    if anime is None or anime.synopsis_embedding is None:
        return {"error": f"No embedding available for anime_id {anime_id}"}
    results = semantic_search_by_vector(db, anime.synopsis_embedding, filters=_filters_from_input(filter_kwargs), limit=9)
    results = [r for r in results if r.id != anime_id][:8]
    return _serialize_results(results)


def tool_check_reception(db: Session, anime_id: int) -> dict:
    rs = db.get(ReceptionSignal, anime_id)
    if rs is None:
        return {
            "anime_id": anime_id,
            "reception_summary": None,
            "sentiment_ratio": None,
            "community_flag": "none",
            "note": "No reception data available for this title yet.",
        }
    return {
        "anime_id": anime_id,
        "reception_summary": rs.reception_summary,
        "sentiment_ratio": float(rs.review_sentiment_ratio) if rs.review_sentiment_ratio is not None else None,
        "community_flag": rs.community_flag.value,
    }


TOOL_EXECUTORS = {
    "search_by_title": tool_search_by_title,
    "semantic_search": tool_semantic_search,
    "find_similar": tool_find_similar,
    "check_reception": tool_check_reception,
}


def execute_tool(db: Session, name: str, tool_input: dict):
    executor = TOOL_EXECUTORS[name]
    return executor(db, **tool_input)
