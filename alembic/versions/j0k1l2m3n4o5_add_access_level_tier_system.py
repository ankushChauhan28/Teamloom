"""add access level tier system

Revision ID: j0k1l2m3n4o5
Revises: 104551d9fda5
Create Date: 2026-09-22 16:38:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: str | Sequence[str] | None = "104551d9fda5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    1. Add access_level column to users table (INTEGER, default 3, CHECK 1-4).
    2. Expand designation column to VARCHAR(255).
    3. Migrate existing role data to access_level:
       - role == 'ADMIN' -> 1
       - role == 'EMPLOYEE' and has direct reports -> 2
       - role == 'EMPLOYEE' -> 3
    """
    # 1. Add access_level column with server_default='3' and CHECK constraint
    op.add_column(
        "users",
        sa.Column(
            "access_level",
            sa.Integer(),
            sa.CheckConstraint(
                "access_level >= 1 AND access_level <= 4",
                name="check_user_access_level",
            ),
            nullable=False,
            server_default="3",
        ),
    )

    # 2. Expand designation to VARCHAR(255)
    op.alter_column(
        "users",
        "designation",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )

    # 3. Data migration for existing users
    # Tier 1 for Admins
    op.execute("UPDATE users SET access_level = 1 WHERE role = 'ADMIN'")

    # Tier 2 for Employees who are designated as managers or supervise direct reports
    op.execute(
        """
        UPDATE users 
        SET access_level = 2 
        WHERE role = 'EMPLOYEE' 
          AND (
            id IN (SELECT DISTINCT reports_to_id FROM users WHERE reports_to_id IS NOT NULL)
            OR LOWER(designation) LIKE '%manager%'
            OR LOWER(designation) LIKE '%supervisor%'
            OR LOWER(designation) LIKE '%lead%'
          )
        """
    )

    # Tier 3 for remaining standard employees
    op.execute(
        "UPDATE users SET access_level = 3 WHERE role = 'EMPLOYEE' AND access_level = 3"
    )


def downgrade() -> None:
    """
    Reverses the migration:
    1. Shrink designation back to VARCHAR(100).
    2. Drop access_level column and constraint.
    """
    op.alter_column(
        "users",
        "designation",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.drop_column("users", "access_level")
