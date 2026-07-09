from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.anime import Anime
from app.models.reception import ReceptionSignal
from app.schemas import AnimeDetailOut

router = APIRouter()


@router.get("/anime/{anime_id}", response_model=AnimeDetailOut)
def get_anime(anime_id: int, db: Session = Depends(get_db)) -> AnimeDetailOut:
    anime = db.get(Anime, anime_id)
    if anime is None:
        raise HTTPException(status_code=404, detail="Anime not found")
    reception = db.get(ReceptionSignal, anime_id)

    return AnimeDetailOut(
        id=anime.id,
        title=anime.title,
        synopsis=anime.synopsis,
        genres=anime.genres,
        tags=anime.tags,
        episodes=anime.episodes,
        status=anime.status,
        score=float(anime.score) if anime.score is not None else None,
        popularity_rank=anime.popularity_rank,
        reception_summary=reception.reception_summary if reception else None,
        review_sentiment_ratio=(
            float(reception.review_sentiment_ratio)
            if reception and reception.review_sentiment_ratio is not None
            else None
        ),
        community_flag=reception.community_flag.value if reception else None,
    )
