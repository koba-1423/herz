import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from herz.core.config import Settings
from herz.crawl import Crawler
from herz.models import CrawlMark, TrackRecord
from herz.schemas.ingest import IngestResponse
from herz.services.itunes import ITunesClient, PreviewTrack


def _song(track_id: int, artist_id: int) -> dict[str, object]:
    return {
        "kind": "song",
        "trackId": track_id,
        "trackName": f"Song {track_id}",
        "artistId": artist_id,
        "artistName": f"Artist {artist_id}",
        "previewUrl": f"https://audio.example/{track_id}.m4a",
        "trackViewUrl": f"https://music.apple.com/us/song/{track_id}",
    }


def _handler(request: httpx.Request) -> httpx.Response:
    if "/rss/topsongs/" in request.url.path:
        return httpx.Response(200, json={"feed": {"entry": [{"id": {"attributes": {"im:id": "1"}}}]}})
    if request.url.params.get("entity") == "song":  # アーティスト7の曲
        return httpx.Response(200, json={"results": [_song(1, 7), _song(2, 7)]})
    ids = [int(i) for i in request.url.params["id"].split(",")]
    return httpx.Response(200, json={"results": [_song(i, 7) for i in ids]})


async def test_crawler_walks_charts_then_artists(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("herz.crawl.CHART_GENRES", {11: "ジャズ"})

    async def ingest(previews: list[PreviewTrack]) -> IngestResponse:
        async with session_factory() as session:
            existing = set(await session.scalars(select(TrackRecord.source_track_id)))
            new = [p for p in previews if p.source_track_id not in existing]
            session.add_all(
                TrackRecord(
                    id=f"itunes:{p.source_track_id}",
                    source="itunes",
                    source_track_id=p.source_track_id,
                    title=p.title,
                    artist=p.artist,
                    source_artist_id=p.artist_id,
                    external_url=p.external_url,
                )
                for p in new
            )
            await session.commit()
        return IngestResponse(ingested=[], skipped_track_ids=[], failed=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as http_client:
        itunes = ITunesClient(Settings(), http_client)
        crawler = Crawler(session_factory, itunes, ingest, ["US"], chart_limit=1, artist_songs=10)
        assert await crawler.step()  # チャート
        assert await crawler.step()  # チャートで見つかったアーティスト
        assert not await crawler.step()  # どちらも処理済み

    async with session_factory() as session:
        tracks = set(await session.scalars(select(TrackRecord.source_track_id)))
        marks = set(await session.execute(select(CrawlMark.kind, CrawlMark.target)))

    assert tracks == {"1", "2"}
    assert marks == {("chart", "US:11"), ("artist", "7")}
