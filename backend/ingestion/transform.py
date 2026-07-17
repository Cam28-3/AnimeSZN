import re
from datetime import date

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

_STATUS_MAP = {
    "RELEASING": "airing",
    "FINISHED": "finished",
    "NOT_YET_RELEASED": "upcoming",
    "HIATUS": "airing",  # ongoing series between seasons/arcs, closest existing status
    "CANCELLED": "finished",  # ended, just not by completion
}

MAX_TAGS = 10
MIN_TAG_RANK = 40  # AniList tag relevance is 0-100; drop low-confidence tags as noise


# Strips HTML tags (AniList descriptions often contain <br>/<i>/etc.) and collapses whitespace.
def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


# Converts AniList's {year, month, day} FuzzyDate (month/day can be missing) into a concrete
# date, defaulting missing month/day to the 1st.
def parse_fuzzy_date(fuzzy: dict | None) -> date | None:
    if not fuzzy or not fuzzy.get("year"):
        return None
    return date(fuzzy["year"], fuzzy.get("month") or 1, fuzzy.get("day") or 1)


def select_tags(raw_tags: list[dict]) -> list[str]:
    # Never surface spoiler tags -- they'd leak plot details into the semantic-search embedding
    # text and undermine spoiler-free mode. Cap to the highest-relevance tags so a title with 30+
    # AniList tags doesn't drown the embedding text in low-signal noise.
    candidates = [t for t in raw_tags if not t.get("isMediaSpoiler") and not t.get("isGeneralSpoiler")]
    candidates.sort(key=lambda t: t.get("rank") or 0, reverse=True)
    return [t["name"] for t in candidates if (t.get("rank") or 0) >= MIN_TAG_RANK][:MAX_TAGS]


# Main entry point: converts one raw AniList media entry into the dict shape ingestion/load.py
# upserts into the anime table (title preference, score-scale conversion, tag filtering, etc.).
def transform_anime(entry: dict) -> dict:
    title = entry.get("title") or {}
    display_title = title.get("english") or title.get("romaji") or f"Untitled ({entry['id']})"

    score = entry.get("averageScore")

    return {
        "id": entry["id"],
        "title": display_title,
        "synopsis": clean_text(entry.get("description")),
        "genres": entry.get("genres") or [],
        "tags": select_tags(entry.get("tags") or []),
        "episodes": entry.get("episodes"),
        "status": _STATUS_MAP.get(entry.get("status"), None),
        "aired_from": parse_fuzzy_date(entry.get("startDate")),
        "score": (score / 10.0) if score is not None else None,
        "score_stddev": None,  # not exposed by AniList's Media type
        "popularity_rank": entry.get("popularity"),  # raw favorite/list count; ranked in a later pass
        "image_url": (entry.get("coverImage") or {}).get("large"),
    }
