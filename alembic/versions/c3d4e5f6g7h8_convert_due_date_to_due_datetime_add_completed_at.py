"""convert due_date to due_datetime and add completed_at

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-08-23 23:45:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime, time

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6g7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add completed_at column
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Add due_datetime column as nullable initially
    op.add_column("tasks", sa.Column("due_datetime", sa.DateTime(timezone=True), nullable=True))

    # 3. Data backfill for existing tasks: set time to 23:59:59 UTC
    connection = op.get_bind()
    results = connection.execute(
        sa.text("SELECT id, due_date FROM tasks WHERE due_date IS NOT NULL")
    ).fetchall()

    for row in results:
        task_id, due_d = row[0], row[1]
        if due_d:
            if isinstance(due_d, str):
                parts = [int(p) for p in due_d.split(" ")[0].split("-")]
                dt_val = datetime(parts[0], parts[1], parts[2], 23, 59, 59, tzinfo=UTC)
            elif hasattr(due_d, "year"):
                dt_val = datetime.combine(due_d, time(23, 59, 59), tzinfo=UTC)
            else:
                dt_val = datetime.now(UTC)

            connection.execute(
                sa.text("UPDATE tasks SET due_datetime = :dt WHERE id = :user_id"),
                {"dt": dt_val, "user_id": task_id},
            )

    # 4. Alter due_datetime column to nullable=False
    op.alter_column("tasks", "due_datetime", nullable=False)

    # 5. Drop old due_date column
    op.drop_column("tasks", "due_date")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("tasks", sa.Column("due_date", sa.Date(), nullable=True))

    connection = op.get_bind()
    results = connection.execute(
        sa.text("SELECT id, due_datetime FROM tasks WHERE due_datetime IS NOT NULL")
    ).fetchall()

    for row in results:
        task_id, due_dt = row[0], str(row[1])
        if due_dt:
            date_part = due_dt.split(" ")[0]
            connection.execute(
                sa.text("UPDATE tasks SET due_date = :d WHERE id = :user_id"),
                {"d": date_part, "user_id": task_id},
            )

    op.alter_column("tasks", "due_date", nullable=False)
    op.drop_column("tasks", "due_datetime")
    op.drop_column("tasks", "completed_at")
