"""あるDBのライブラリ（楽曲とクローラの処理済み記録）を別のDBにコピーするコマンド。

    uv run python -m herz.transfer --source sqlite+aiosqlite:///./herz.db \\
        --target postgresql+asyncpg://herz:herz@localhost:5432/herz

コピー先は `alembic upgrade head` 済みであること。コピー先に既にある行は飛ばすので、
途中で止めても、コピー元に曲が増えた後でも、再実行すれば差分だけが入る。
"""

import argparse
import asyncio
import time
from typing import Any

from sqlalchemy import Table, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from herz.models import CrawlMark, TrackRecord

_BATCH = 2000


async def _copy_table(source: AsyncEngine, target: AsyncEngine, table: Table) -> int:
    insert = pg_insert if target.dialect.name == "postgresql" else sqlite_insert
    keys = list(table.primary_key.columns)
    before = await _count(target, table)
    checked = 0
    last: tuple[Any, ...] | None = None
    while True:
        # 主キー順に区切って読む（OFFSET より速く、途中で行が増えても読み飛ばさない）
        statement = select(table).order_by(*keys).limit(_BATCH)
        if last is not None:
            statement = statement.where(_after(keys, last))
        async with source.connect() as connection:
            rows = [dict(row._mapping) for row in await connection.execute(statement)]
        if not rows:
            return await _count(target, table) - before
        async with target.begin() as connection:
            await connection.execute(insert(table).on_conflict_do_nothing(), rows)
        checked += len(rows)
        last = tuple(rows[-1][key.name] for key in keys)
        print(f"  {table.name}: {checked}行を確認", flush=True)


async def _count(engine: AsyncEngine, table: Table) -> int:
    # まとめて INSERT したときの rowcount はドライバによって返らない (-1) ので、行数の増分で数える
    async with engine.connect() as connection:
        return int(await connection.scalar(select(func.count()).select_from(table)) or 0)


def _after(keys: list[Any], last: tuple[Any, ...]) -> Any:
    return tuple_(*keys) > tuple_(*last)


async def transfer(source_url: str, target_url: str) -> None:
    source = create_async_engine(source_url)
    target = create_async_engine(target_url)
    started = time.monotonic()
    try:
        for model in (TrackRecord, CrawlMark):
            table = model.__table__
            assert isinstance(table, Table)
            copied = await _copy_table(source, target, table)
            print(f"{table.name}: 新しく {copied}行", flush=True)
    finally:
        await source.dispose()
        await target.dispose()
    print(f"完了 ({(time.monotonic() - started) / 60:.1f}分)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", required=True, help="コピー元のDATABASE_URL")
    parser.add_argument("--target", required=True, help="コピー先のDATABASE_URL")
    args = parser.parse_args()
    asyncio.run(transfer(args.source, args.target))


if __name__ == "__main__":
    main()
