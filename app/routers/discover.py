from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.anime import Anime
from app.schemas import DiscoverItemOut

router = APIRouter()


@router.get("/discover", response_model=list[DiscoverItemOut])
def discover(limit: int = 12, db: Session = Depends(get_db)) -> list[DiscoverItemOut]:
    """Currently-airing titles, most popular first -- shown on the homepage before any query."""
    stmt = (
        select(Anime)
        .where(Anime.status == "airing")
        .order_by(Anime.popularity_rank.asc().nulls_last())
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    return [
        DiscoverItemOut(
            anime_id=a.id,
            title=a.title,
            score=float(a.score) if a.score is not None else None,
            image_url=a.image_url,
            genres=a.genres,
        )
        for a in rows
    ]
