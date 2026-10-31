"""ライブラリを止まらずに広げ続けるクローラ。

    uv run python -m herz.crawl
    uv run python -m herz.crawl --countries JP,US,KR --artist-songs 30

次の順で取り込み対象を選び、やることが無くなっても一定時間おきに見直して回り続ける。
  1. アーティストIDが未記録の取り込み済み曲を lookup してIDを埋める（初回のみ）
  2. 各国 × ジャンル別チャート（1日おきに取り直す）
  3. ライブラリにいるアーティストの他の曲（アーティストごとに1回）
新しく入った曲のアーティストも 3 の対象に加わるので、チャートを起点に芋づる式に広がる。
処理済みの対象は crawl_marks テーブルに残すため、止めても再実行すれば続きから進む。
"""

import argparse
import asyncio
import importlib.util
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from herz.core.config import get_settings
from herz.core.dependencies import get_audio_text_embedder
from herz.models import CrawlMark, TrackRecord
from herz.schemas.ingest import IngestResponse
from herz.services.dsp_analysis import DspAudioFeatureExtractor
from herz.services.ingest import TrackIngestor
from herz.services.itunes import CHART_GENRES, ITunesClient, PreviewTrack

DEFAULT_COUNTRIES = (
    "JP", "US", "GB", "KR", "TW", "CA", "AU", "FR", "DE", "BR",
    "MX", "ES", "IT", "SE", "NL", "IN", "ID", "TH", "PH", "ZA",
)  # fmt: skip

# iTunesのAPIは1分あたり20回程度でレート制限がかかる
_MIN_API_INTERVAL_SEC = 3.5
_CHART_REFRESH = timedelta(days=1)
_IDLE_SLEEP_SEC = 3600.0
_DEFAULT_CONCURRENCY = 4
_ERROR_SLEEP_SEC = 60.0

IngestFn = Callable[[list[PreviewTrack]], Awaitable[IngestResponse]]

_STORE_COUNTRY = re.compile(r"music\.apple\.com/([a-z]{2})/")


def _store_country(external_url: str | None) -> str | None:
    match = _STORE_COUNTRY.search(external_url or "")
    return match.group(1).upper() if match else None


class Crawler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        itunes: ITunesClient,
        ingest: IngestFn,
        countries: list[str],
        chart_limit: int,
        artist_songs: int,
    ) -> None:
        self._session_factory = session_factory
        self._itunes = itunes
        self._ingest = ingest
        self._countries = countries
        self._chart_limit = chart_limit
        self._artist_songs = artist_songs

    async def run_forever(self) -> None:
        await self.fill_artist_ids()
        while True:
            if not await self.step():
                print(f"対象が無いので{_IDLE_SLEEP_SEC / 60:.0f}分待ちます", flush=True)
                await asyncio.sleep(_IDLE_SLEEP_SEC)

    async def step(self) -> bool:
        """取り込み対象を1つ処理する。対象が無ければ False。"""
        if chart := await self._next_chart():
            country, genre_id = chart
            label = f"チャート {country} {CHART_GENRES[genre_id]}"
            await self._crawl("chart", f"{country}:{genre_id}", label, self._chart_ingest(country, genre_id))
            return True

        if artist := await self._next_artist():
            artist_id, artist_name, country = artist
            label = f"アーティスト {artist_name} ({country})"
            await self._crawl("artist", artist_id, label, self._artist_ingest(artist_id, country))
            return True

        return False

    async def fill_artist_ids(self) -> None:
        """アーティストIDを記録する前に取り込んだ曲のIDを lookup で埋める。"""
        async with self._session_factory() as session:
            records = list(
                await session.scalars(select(TrackRecord).where(TrackRecord.source_artist_id.is_(None)))
            )
            if not records:
                return
            by_country: dict[str, list[TrackRecord]] = {}
            for record in records:
                country = _store_country(record.external_url) or self._countries[0]
                by_country.setdefault(country, []).append(record)
            filled = 0
            for country, group in by_country.items():
                previews = await self._itunes.lookup_previews(
                    [r.source_track_id for r in group], country=country
                )
                artist_ids = {preview.source_track_id: preview.artist_id for preview in previews}
                for record in group:
                    if artist_id := artist_ids.get(record.source_track_id):
                        record.source_artist_id = artist_id
                        filled += 1
            await session.commit()
            print(f"アーティストIDを補完: {filled}/{len(records)}曲", flush=True)

    async def _next_chart(self) -> tuple[str, int] | None:
        async with self._session_factory() as session:
            marks = await session.execute(
                select(CrawlMark.target, CrawlMark.crawled_at).where(CrawlMark.kind == "chart")
            )
            crawled = {target: crawled_at for target, crawled_at in marks}
        stale_before = datetime.now(UTC) - _CHART_REFRESH
        # 国ごとに全ジャンルを回すより、ジャンルを先に回すほうが早い段階で多様な曲が揃う
        for genre_id in CHART_GENRES:
            for country in self._countries:
                crawled_at = crawled.get(f"{country}:{genre_id}")
                if crawled_at is None or crawled_at.replace(tzinfo=UTC) < stale_before:
                    return country, genre_id
        return None

    async def _next_artist(self) -> tuple[str, str, str] | None:
        """まだ曲を集めていないアーティストのうち、ライブラリに早く入ったものから選ぶ。"""
        crawled = select(CrawlMark.target).where(CrawlMark.kind == "artist")
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(
                        TrackRecord.source_artist_id,
                        func.min(TrackRecord.artist),
                        func.min(TrackRecord.external_url),
                    )
                    .where(TrackRecord.source_artist_id.is_not(None))
                    .where(TrackRecord.source_artist_id.not_in(crawled))
                    .group_by(TrackRecord.source_artist_id)
                    .order_by(func.min(TrackRecord.created_at))
                    .limit(1)
                )
            ).first()
        if row is None:
            return None
        artist_id, artist_name, external_url = row
        return artist_id, artist_name, _store_country(external_url) or self._countries[0]

    async def _chart_ingest(self, country: str, genre_id: int) -> IngestResponse:
        previews = await self._itunes.chart_previews(genre_id, self._chart_limit, country=country)
        return await self._ingest(previews)

    async def _artist_ingest(self, artist_id: str, country: str) -> IngestResponse:
        previews = await self._itunes.artist_previews(artist_id, self._artist_songs, country=country)
        return await self._ingest(previews)

    async def _crawl(self, kind: str, target: str, label: str, work: Awaitable[IngestResponse]) -> None:
        started = time.monotonic()
        added = 0
        try:
            result = await work
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # 1件の失敗で止まらないよう処理済みにして先へ進む（チャートは翌日また取り直される）
            print(f"{label}: 失敗 ({type(exc).__name__}: {exc})", flush=True)
            await asyncio.sleep(_ERROR_SLEEP_SEC)
        else:
            added = len(result.ingested)
            total = await self._total_tracks()
            print(
                f"{label}: 追加 {added} / 取り込み済み {len(result.skipped_track_ids)} / "
                f"失敗 {len(result.failed)} ({time.monotonic() - started:.0f}秒) 計 {total}曲",
                flush=True,
            )

        async with self._session_factory() as session:
            mark = await session.get(CrawlMark, (kind, target))
            if mark is None:
                session.add(CrawlMark(kind=kind, target=target, added=added))
            else:
                mark.added = added
                mark.crawled_at = datetime.now(UTC)
            await session.commit()

    async def _total_tracks(self) -> int:
        async with self._session_factory() as session:
            return await session.scalar(select(func.count()).select_from(TrackRecord)) or 0


async def crawl(countries: list[str], chart_limit: int, artist_songs: int, threads: int | None) -> None:
    if threads and importlib.util.find_spec("torch") is not None:
        # PCへの負荷（発熱）を抑えたいとき用。曲の並列処理もスレッド数に合わせて絞る
        import torch

        torch.set_num_threads(threads)
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    if engine.dialect.name == "sqlite":
        # 検索サーバーが同じDBを読みながら書き込めるようにする（設定はDBファイルに残る）
        async with engine.begin() as connection:
            await connection.execute(text("PRAGMA journal_mode=WAL"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    extractor = DspAudioFeatureExtractor()
    embedder = get_audio_text_embedder(settings)
    print(f"embedder: {embedder.model_name if embedder else '無効（自然文検索の埋め込みは算出しない）'}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            itunes = ITunesClient(settings, http_client, min_api_interval_sec=_MIN_API_INTERVAL_SEC)

            async def ingest(previews: list[PreviewTrack]) -> IngestResponse:
                async with session_factory() as session:
                    return await TrackIngestor(
                        session, itunes, extractor, embedder, concurrency=threads or _DEFAULT_CONCURRENCY
                    ).ingest_previews(previews)

            crawler = Crawler(session_factory, itunes, ingest, countries, chart_limit, artist_songs)
            await crawler.run_forever()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--countries",
        default=",".join(DEFAULT_COUNTRIES),
        help="チャートを取る国（カンマ区切り。先頭が既定の国）",
    )
    parser.add_argument("--chart-limit", type=int, default=200, help="チャートごとの最大曲数 (最大200)")
    parser.add_argument("--artist-songs", type=int, default=50, help="アーティストごとに集める最大曲数")
    parser.add_argument(
        "--threads",
        type=int,
        help="使うCPUスレッド数の上限（PCが熱くなるときに小さくする。省略時は制限なし）",
    )
    args = parser.parse_args()

    countries = [country.strip().upper() for country in args.countries.split(",") if country.strip()]
    asyncio.run(crawl(countries, args.chart_limit, args.artist_songs, args.threads))


if __name__ == "__main__":
    main()
