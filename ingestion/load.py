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
]


def upsert_anime(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(Anime).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={col: getattr(stmt.excluded, col) for col in _UPSERT_COLUMNS},
    )
    db.execute(stmt)
    db.commit()
