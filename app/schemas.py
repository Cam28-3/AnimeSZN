from pydantic import BaseModel


class RecommendRequest(BaseModel):
    query: str


class RecommendationOut(BaseModel):
    anime_id: int
    title: str
    rationale: str
    caveat: str | None
    score: float | None
    community_flag: str | None


class RecommendResponse(BaseModel):
    message: str
    recommendations: list[RecommendationOut]


class StreamingPlatformOut(BaseModel):
    name: str
    url: str


class AnimeDetailOut(BaseModel):
    id: int
    title: str
    synopsis: str | None
    genres: list[str]
    tags: list[str]
    episodes: int | None
    status: str | None
    score: float | None
    popularity_rank: int | None
    reception_summary: str | None
    review_sentiment_ratio: float | None
    community_flag: str | None
    streaming: list[StreamingPlatformOut]
