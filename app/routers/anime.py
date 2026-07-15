import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.anilist_client import fetch_streaming
from app.db import get_db
from app.models.anime import Anime
from app.models.reception import ReceptionSignal
from app.schemas import AnimeDetailOut, StreamingPlatformOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/anime/{anime_id}", response_model=AnimeDetailOut)
def get_anime(anime_id: int, db: Session = Depends(get_db)) -> AnimeDetailOut:
    anime = db.get(Anime, anime_id)
    if anime is None:
        raise HTTPException(status_code=404, detail="Anime not found")
    reception = db.get(ReceptionSignal, anime_id)

    streaming_unavailable = False
    try:
        streaming = fetch_streaming(anime_id)
    except httpx.HTTPError:
        logger.warning("AniList streaming lookup failed for anime_id %s", anime_id, exc_info=True)
        streaming = []
        streaming_unavailable = True

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
        image_url=anime.image_url,
        streaming=[StreamingPlatformOut(**s) for s in streaming],
        streaming_unavailable=streaming_unavailable,
        anilist_url=f"https://anilist.co/anime/{anime.id}",
    )
