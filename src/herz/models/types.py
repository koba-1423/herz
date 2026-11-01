from typing import Any

import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import LargeBinary
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine

# 埋め込みの次元数（laion/larger_clap_general は512次元）。PostgreSQLの vector 列はこの次元で作るので、
# 次元の違うモデルに切り替えるときはマイグレーションも必要になる
EMBEDDING_DIM = 512


class Embedding(TypeDecorator[bytes]):
    """埋め込みベクトル。PostgreSQLでは pgvector の vector 型（近傍検索の索引が使える）、
    それ以外（開発・テスト用のSQLite）では float32 のバイト列で保存する。

    Python側ではどちらでも float32 のバイト列として扱う。
    """

    impl = LargeBinary
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(EMBEDDING_DIM))
        return dialect.type_descriptor(LargeBinary())

    def process_bind_param(self, value: bytes | None, dialect: Dialect) -> Any:
        if value is None or dialect.name != "postgresql":
            return value
        return np.frombuffer(value, dtype=np.float32)

    def process_result_value(self, value: Any, dialect: Dialect) -> bytes | None:
        if value is None or dialect.name != "postgresql":
            return value
        return np.asarray(value, dtype=np.float32).tobytes()
