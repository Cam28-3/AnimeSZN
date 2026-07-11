from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.loop import run_agent
from app.db import get_db
from app.schemas import RecommendationOut, RecommendRequest, RecommendResponse

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest, db: Session = Depends(get_db)) -> RecommendResponse:
    history = [turn.model_dump() for turn in request.history]
    result = run_agent(db, request.query, history=history)
    return RecommendResponse(
        message=result.message,
        recommendations=[
            RecommendationOut(
                anime_id=rec.anime_id,
                title=rec.title,
                rationale=rec.rationale,
                caveat=rec.caveat,
                score=rec.score,
                community_flag=rec.community_flag,
                image_url=rec.image_url,
            )
            for rec in result.recommendations
        ],
    )
