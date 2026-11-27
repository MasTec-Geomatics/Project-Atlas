"""progress for every load stage

Revision ID: 5c2d9e71a0b4
Revises: 38e531be1451
Create Date: 2026-11-26 22:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c2d9e71a0b4"
down_revision: str | Sequence[str] | None = "38e531be1451"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f("ck_load_runs_stage"), "load_runs", type_="check")
    op.alter_column("load_runs", "bytes_downloaded", new_column_name="progress_done")
    op.alter_column("load_runs", "bytes_total", new_column_name="progress_total")
    op.create_check_constraint(
        op.f("ck_load_runs_stage"),
        "load_runs",
        "stage IN ('downloading', 'unzipping', 'copying', 'swapping')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_load_runs_stage"), "load_runs", type_="check")
    op.execute("UPDATE load_runs SET stage = 'downloading' WHERE stage = 'unzipping'")
    op.alter_column("load_runs", "progress_total", new_column_name="bytes_total")
    op.alter_column("load_runs", "progress_done", new_column_name="bytes_downloaded")
    op.create_check_constraint(
        op.f("ck_load_runs_stage"),
        "load_runs",
        "stage IN ('downloading', 'copying', 'swapping')",
    )
