"""add employee_code and must_change_password

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-21 17:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add employee_code as nullable initially
    op.add_column("users", sa.Column("employee_code", sa.String(), nullable=True))
    # 2. Add must_change_password as non-nullable with server_default=false
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 3. Data backfill for existing users
    connection = op.get_bind()
    results = connection.execute(
        sa.text("SELECT id FROM users ORDER BY created_at ASC, id ASC")
    ).fetchall()

    code_counter = 1001
    for row in results:
        user_id = row[0]
        code_str = f"EMP-{code_counter}"
        connection.execute(
            sa.text("UPDATE users SET employee_code = :code WHERE id = :user_id"),
            {"code": code_str, "user_id": user_id},
        )
        code_counter += 1

    # 4. Alter employee_code to nullable=False and add unique index
    op.alter_column("users", "employee_code", nullable=False)
    op.create_index(op.f("ix_users_employee_code"), "users", ["employee_code"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_users_employee_code"), table_name="users")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "employee_code")
