"""rename manager_id to reports_to_id and add designation

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-09-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | Sequence[str] | None = "d4e5f6g7h8i9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Drop old foreign key constraint
    op.drop_constraint("fk_users_manager_id_users", "users", type_="foreignkey")

    # 2. Rename manager_id to reports_to_id (preserves existing data)
    op.alter_column("users", "manager_id", new_column_name="reports_to_id")

    # 3. Create new foreign key constraint with ondelete='SET NULL'
    op.create_foreign_key(
        "fk_users_reports_to_id_users",
        "users",
        "users",
        ["reports_to_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Add nullable designation column (varchar(100))
    op.add_column("users", sa.Column("designation", sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop designation column
    op.drop_column("users", "designation")

    # 2. Drop new foreign key constraint
    op.drop_constraint("fk_users_reports_to_id_users", "users", type_="foreignkey")

    # 3. Rename reports_to_id back to manager_id
    op.alter_column("users", "reports_to_id", new_column_name="manager_id")

    # 4. Recreate old foreign key constraint
    op.create_foreign_key(
        "fk_users_manager_id_users",
        "users",
        "users",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )
