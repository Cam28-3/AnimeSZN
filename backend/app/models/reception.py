import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CommunityFlag(str, enum.Enum):
    none = "none"
    mixed = "mixed"
    widely_criticized = "widely_criticized"


class ReceptionSignal(Base):
    __tablename__ = "reception_signals"

    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.id"), primary_key=True)
    review_sentiment_ratio: Mapped[float | None] = mapped_column(Numeric)
    reception_summary: Mapped[str | None] = mapped_column(Text)
    community_flag: Mapped[CommunityFlag] = mapped_column(
        Enum(CommunityFlag, name="community_flag"), default=CommunityFlag.none
    )
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
