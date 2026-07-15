from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.anime import Anime

_UPSERT_COLUMNS = [
    "title",
    "synopsis",
    "genres",
    "tags",
    "episodes",
    "status",
    "aired_from",
    "score",
    "score_stddev",
    "popularity_rank",
    "image_url",
]


def upsert_anime(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    # The year-sliced crawl pads adjacent windows by a day to avoid missing fuzzy year-only
    # dates, which can occasionally yield the same id twice in one batch -- ON CONFLICT DO
    # UPDATE can't touch a row twice in one statement, so keep only the last occurrence per id.
    deduped = {row["id"]: row for row in rows}
    rows = list(deduped.values())

    stmt = insert(Anime).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={col: getattr(stmt.excluded, col) for col in _UPSERT_COLUMNS},
    )
    db.execute(stmt)
    db.commit()


def finalize_popularity_ranks(db: Session) -> None:
    """AniList's `popularity` field (loaded into popularity_rank during ingest) is a raw
    favorite/list count, not a rank like Jikan's was -- convert it to an actual rank (1 = most
    popular) in one pass now that the full catalog is loaded. Safe to re-run any time."""
    db.execute(
        text(
            """
            UPDATE anime
            SET popularity_rank = ranked.rank
            FROM (
                SELECT id, ROW_NUMBER() OVER (ORDER BY popularity_rank DESC NULLS LAST) AS rank
                FROM anime
            ) AS ranked
            WHERE anime.id = ranked.id
            """
        )
    )
    db.commit()
