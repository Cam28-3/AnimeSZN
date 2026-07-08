import re
from datetime import date, datetime

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

_STATUS_MAP = {
    "Currently Airing": "airing",
    "Finished Airing": "finished",
    "Not yet aired": "upcoming",
}


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def parse_aired_from(aired: dict | None) -> date | None:
    if not aired or not aired.get("from"):
        return None
    return datetime.fromisoformat(aired["from"]).date()


def transform_anime(entry: dict) -> dict:
    genres = [g["name"] for g in entry.get("genres", [])]
    tags = [t["name"] for t in entry.get("themes", [])] + [
        d["name"] for d in entry.get("demographics", [])
    ]

    return {
        "id": entry["mal_id"],
        "title": entry["title"],
        "synopsis": clean_text(entry.get("synopsis")),
        "genres": genres,
        "tags": tags,
        "episodes": entry.get("episodes"),
        "status": _STATUS_MAP.get(entry.get("status"), None),
        "aired_from": parse_aired_from(entry.get("aired")),
        "score": entry.get("score"),
        "score_stddev": None,  # requires /anime/{id}/statistics; not fetched at this stage
        "popularity_rank": entry.get("popularity"),
    }
