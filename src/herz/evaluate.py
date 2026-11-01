"""雰囲気検索の精度を測るコマンド。

    uv run python -m herz.evaluate
    uv run python -m herz.evaluate --limit 30 --verbose

「この検索文ならこのジャンルの曲が上位に来てほしい」という例ごとに、上位N曲のうち期待した
ジャンルの曲の割合 (precision@N) を出す。ジャンルは雰囲気の正解そのものではないが、
変更の前後で精度が上がったか下がったかを比べる物差しとしては十分使える。
"""

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from herz.core.config import get_settings
from herz.core.dependencies import get_audio_text_embedder, get_query_translator
from herz.schemas.track import TrackSearchQuery
from herz.services.embedding_index import EmbeddingIndex
from herz.services.track_search import search_tracks


@dataclass(frozen=True)
class Case:
    text: str
    # 期待するジャンル名の一部（ストアの国によって表記が違うので複数の言語で書く）
    genres: tuple[str, ...]


CASES = (
    Case("落ち着いたジャズ、サックス", ("jazz", "ジャズ")),
    Case("ゴリゴリのメタル", ("metal", "メタル", "hard rock", "ハードロック")),
    Case("壮大なオーケストラ", ("classical", "クラシック", "soundtrack", "サウンドトラック", "score")),
    Case("レゲエ", ("reggae", "レゲエ")),
    Case("ヒップホップ、ラップ", ("hip-hop", "hip hop", "ヒップホップ", "rap")),
    Case("カントリー", ("country", "カントリー")),
    Case("踊れるEDM", ("dance", "ダンス", "electronic", "エレクトロニック", "house")),
    Case("ラテン", ("latin", "ラテン", "latino", "salsa", "reggaeton")),
    Case("ブルース", ("blues", "ブルース")),
    Case(
        "癒しのアンビエント", ("new age", "ニューエイジ", "ambient", "easy listening", "イージーリスニング")
    ),
    Case("アニソンっぽい盛り上がる曲", ("anime", "アニメ")),
    Case("昭和の歌謡曲", ("kayokyoku", "歌謡曲", "enka", "演歌")),
    Case("smooth jazz saxophone", ("jazz", "ジャズ")),
    Case("heavy distorted rock guitars", ("rock", "ロック", "metal", "メタル")),
)


def _hit(genre: str | None, expected: tuple[str, ...]) -> bool:
    return genre is not None and any(name in genre.casefold() for name in expected)


async def evaluate(limit: int, verbose: bool) -> None:
    settings = get_settings()
    embedder = get_audio_text_embedder(settings)
    if embedder is None:
        raise SystemExit("CLAPが無効です（`uv sync --extra clap` と CLAP_MODEL を確認）")
    translator = get_query_translator(settings)
    engine = create_async_engine(settings.database_url)
    index = EmbeddingIndex(embedder.model_name)

    scores: list[float] = []
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for case in CASES:
                english = await asyncio.to_thread(translator.to_english, case.text)
                results = await search_tracks(
                    session, TrackSearchQuery(text=english, limit=limit), embedder, index
                )
                hits = [result for result in results if _hit(next(iter(result.genres), None), case.genres)]
                score = len(hits) / limit
                scores.append(score)
                print(f"{score:5.0%}  {case.text}  →  {english}")
                if verbose:
                    for result in results[:5]:
                        mark = "o" if result in hits else "x"
                        print(f"        {mark} {result.artist} - {result.title} {result.genres}")
    finally:
        await engine.dispose()

    print(f"平均 precision@{limit}: {sum(scores) / len(scores):.1%}（{len(index)}曲）")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, default=20, help="上位何曲で測るか")
    parser.add_argument("--verbose", action="store_true", help="各検索の上位5曲も表示する")
    args = parser.parse_args()
    asyncio.run(evaluate(args.limit, args.verbose))


if __name__ == "__main__":
    main()
