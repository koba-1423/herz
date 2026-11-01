"""store embeddings as pgvector on postgresql

Revision ID: c11d3af91e59
Revises: 2ac5b3236e56
Create Date: 2026-11-01 11:25:04.873130

"""

from collections.abc import Sequence

from alembic import op

from herz.models.types import EMBEDDING_DIM

# revision identifiers, used by Alembic.
revision: str = "c11d3af91e59"
down_revision: str | Sequence[str] | None = "2ac5b3236e56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """PostgreSQLでは埋め込みを pgvector の vector 型にして、コサイン距離のHNSW索引を張る。

    bytea から vector への変換はしないので、既存の埋め込みは消える（空のDBに対して実行し、
    データは `python -m herz.transfer` で移す想定）。SQLiteでは何もしない。
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE tracks ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM}) USING NULL")
    op.execute("CREATE INDEX ix_tracks_embedding_hnsw ON tracks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX ix_tracks_embedding_hnsw")
    op.execute("ALTER TABLE tracks ALTER COLUMN embedding TYPE bytea USING NULL")
