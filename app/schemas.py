from pydantic import BaseModel, Field


class HistoryRecommendationIn(BaseModel):
    anime_id: int
    title: str


class HistoryTurnIn(BaseModel):
    query: str
    message: str
    recommendations: list[HistoryRecommendationIn] = []


class RecommendRequest(BaseModel):
    query: str
    history: list[HistoryTurnIn] = Field(default_factory=list, max_length=20)


class RecommendationOut(BaseModel):
    anime_id: int
    title: str
    rationale: str
    caveat: str | None
    score: float | None
    community_flag: str | None
    image_url: str | None


class RecommendResponse(BaseModel):
    message: str
    recommendations: list[RecommendationOut]


class DiscoverItemOut(BaseModel):
    anime_id: int
    title: str
    score: float | None
    image_url: str | None
    genres: list[str]


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
    image_url: str | None
    streaming: list[StreamingPlatformOut]
