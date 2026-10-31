from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from herz.models.base import Base


class CrawlMark(Base):
    """クローラが処理済みの対象（チャートやアーティスト）。再起動しても続きから進めるために使う。

    kind は "chart"（target は "{country}:{genre_id}"）か "artist"（target はアーティストID）。
    """

    __tablename__ = "crawl_marks"

    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    target: Mapped[str] = mapped_column(String(128), primary_key=True)
    added: Mapped[int] = mapped_column(default=0)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
