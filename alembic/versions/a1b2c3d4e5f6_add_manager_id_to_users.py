"""add manager_id to users

Revision ID: a1b2c3d4e5f6
Revises: f2850ec5859c
Create Date: 2026-08-21 16:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f2850ec5859c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("manager_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_manager_id_users",
        "users",
        "users",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_users_manager_id_users", "users", type_="foreignkey")
    op.drop_column("users", "manager_id")
