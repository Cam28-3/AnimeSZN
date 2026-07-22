"""enable pgvector extension

Revision ID: 59d8c41aa8a1
Revises:
Create Date: 2026-07-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '59d8c41aa8a1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Previously a manual `psql` step run before `alembic upgrade head` -- captured here so a
    # fresh database is fully provisioned by migrations alone (needed for first deploy).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Downgrade schema."""
    # Safe to run: this migration's upgrade always runs first (down_revision=None), so by the
    # time its downgrade runs, every later migration -- including the one creating the
    # vector-typed synopsis_embedding column -- has already been downgraded away.
    op.execute("DROP EXTENSION IF EXISTS vector")
