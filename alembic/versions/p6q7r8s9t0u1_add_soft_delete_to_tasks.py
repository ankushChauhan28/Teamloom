"""add soft delete to tasks

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-11-17 14:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p6q7r8s9t0u1"
down_revision: str | Sequence[str] | None = "o5p6q7r8s9t0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("deleted_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tasks_deleted_by_users",
        "tasks",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_deleted_by_users", "tasks", type_="foreignkey")
    op.drop_column("tasks", "deleted_by")
    op.drop_column("tasks", "deleted_at")
    op.drop_column("tasks", "is_deleted")
