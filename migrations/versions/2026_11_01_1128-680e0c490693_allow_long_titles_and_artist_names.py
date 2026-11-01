"""allow long titles and artist names

Revision ID: 680e0c490693
Revises: c11d3af91e59
Create Date: 2026-11-01 11:28:55.521571

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "680e0c490693"
down_revision: str | Sequence[str] | None = "c11d3af91e59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """曲名・アーティスト名の長さの上限をなくす。SQLiteは長さを強制しないので何もしない。"""
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column("tracks", "title", type_=sa.Text(), existing_type=sa.String(512), existing_nullable=False)
    op.alter_column(
        "tracks", "artist", type_=sa.Text(), existing_type=sa.String(512), existing_nullable=False
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column("tracks", "title", type_=sa.String(512), existing_type=sa.Text(), existing_nullable=False)
    op.alter_column(
        "tracks", "artist", type_=sa.String(512), existing_type=sa.Text(), existing_nullable=False
    )
