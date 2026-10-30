"""ジャンル別チャートの人気曲をまとめて取り込み、ライブラリの土台を作るコマンド。

    uv run python -m herz.seed                # 全ジャンル (各ジャンル最大100曲)
    uv run python -m herz.seed --genre 27 --genre 11 --limit 50

取り込み済みの曲はスキップするので、途中で止めても再実行すれば続きから進む。
"""

import argparse
import asyncio
import time

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from herz.core.config import get_settings
from herz.core.dependencies import get_audio_text_embedder
from herz.services.dsp_analysis import DspAudioFeatureExtractor
from herz.services.ingest import TrackIngestor
from herz.services.itunes import CHART_GENRES, ITunesClient

# iTunesのAPIは1分あたり20回程度でレート制限がかかるため、ジャンルごとに間を空ける
_PAUSE_BETWEEN_GENRES_SEC = 5.0


async def seed(genre_ids: list[int], limit: int) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    extractor = DspAudioFeatureExtractor()
    embedder = get_audio_text_embedder(settings)
    print(f"embedder: {embedder.model_name if embedder else '無効（自然文検索の埋め込みは算出しない）'}")

    total_ingested = 0
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            itunes = ITunesClient(settings=settings, http_client=http_client)
            for index, genre_id in enumerate(genre_ids, start=1):
                label = CHART_GENRES.get(genre_id, str(genre_id))
                genre_started = time.monotonic()
                try:
                    async with session_factory() as session:
                        ingestor = TrackIngestor(session, itunes, extractor, embedder)
                        result = await ingestor.ingest_chart(genre_id, limit)
                except httpx.HTTPError as exc:
                    print(f"[{index}/{len(genre_ids)}] {label}: チャート取得に失敗 ({exc})", flush=True)
                    continue

                total_ingested += len(result.ingested)
                print(
                    f"[{index}/{len(genre_ids)}] {label}: 追加 {len(result.ingested)} / "
                    f"取り込み済み {len(result.skipped_track_ids)} / 失敗 {len(result.failed)} "
                    f"({time.monotonic() - genre_started:.0f}秒)",
                    flush=True,
                )
                await asyncio.sleep(_PAUSE_BETWEEN_GENRES_SEC)
    finally:
        await engine.dispose()

    print(f"完了: {total_ingested}曲を追加 ({(time.monotonic() - started) / 60:.1f}分)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--genre",
        type=int,
        action="append",
        choices=sorted(CHART_GENRES),
        help="取り込むジャンルID（複数指定可。省略時は全ジャンル）",
    )
    parser.add_argument("--limit", type=int, default=100, help="ジャンルごとの最大曲数 (最大200)")
    args = parser.parse_args()

    asyncio.run(seed(args.genre or list(CHART_GENRES), args.limit))


if __name__ == "__main__":
    main()
