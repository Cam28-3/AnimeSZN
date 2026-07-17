from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agent.loop import run_agent
from app.db import get_db
from app.rate_limit import limiter
from app.schemas import RecommendationOut, RecommendRequest, RecommendResponse

router = APIRouter()


# Main app entry point: runs the full agent tool-use loop for a user query and shapes the
# result into the response schema. The only route that spends real Anthropic money, hence
# the rate limit.
@router.post("/recommend", response_model=RecommendResponse)
@limiter.limit("10/minute")
def recommend(request: Request, body: RecommendRequest, db: Session = Depends(get_db)) -> RecommendResponse:
    history = [turn.model_dump() for turn in body.history]
    result = run_agent(db, body.query, history=history, spoiler_free=body.spoiler_free)
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
