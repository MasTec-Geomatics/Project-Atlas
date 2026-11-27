"""load stage and download progress

Revision ID: 38e531be1451
Revises: 817df3fa6e16
Create Date: 2026-11-25 20:55:11.480265

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "38e531be1451"
down_revision: str | Sequence[str] | None = "817df3fa6e16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("load_runs", sa.Column("stage", sa.Text(), nullable=True))
    op.add_column("load_runs", sa.Column("bytes_downloaded", sa.BigInteger(), nullable=True))
    op.add_column("load_runs", sa.Column("bytes_total", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_load_runs_stage"),
        "load_runs",
        "stage IN ('downloading', 'copying', 'swapping')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_load_runs_stage"), "load_runs", type_="check")
    op.drop_column("load_runs", "bytes_total")
    op.drop_column("load_runs", "bytes_downloaded")
    op.drop_column("load_runs", "stage")
