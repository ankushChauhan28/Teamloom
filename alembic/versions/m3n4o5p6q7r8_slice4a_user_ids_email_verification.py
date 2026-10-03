"""Slice 4a: 10-digit numeric user IDs, email verification fields, email_verification_tokens table, lower(email) unique index, drop employee_code_seq

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-10-03 12:00:00.000000

Note on Downgrade:
Recreates the `employee_code_seq` sequence, but old legacy `EMP-` formatted employee codes
cannot be restored because user IDs were regenerated as random 10-digit numeric codes.
"""

from collections.abc import Sequence
import secrets

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: str | Sequence[str] | None = "l2m3n4o5p6q7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Detect email collisions after lowercasing
    collision_query = sa.text(
        """
        SELECT LOWER(TRIM(email)) AS normalized_email, COUNT(*) AS cnt, array_agg(email) AS original_emails
        FROM users
        GROUP BY LOWER(TRIM(email))
        HAVING COUNT(*) > 1;
        """
    )
    collisions = conn.execute(collision_query).fetchall()
    if collisions:
        collision_details = [
            f"'{row.normalized_email}' (conflicting rows: {row.original_emails})" for row in collisions
        ]
        raise RuntimeError(
            f"Cannot proceed with Slice 4a migration: duplicate emails detected after lowercasing: {', '.join(collision_details)}"
        )

    # 2. Lowercase and strip all users.email values, add unique index on lower(email)
    op.execute(sa.text("UPDATE users SET email = LOWER(TRIM(email));"))
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.text("LOWER(email)")],
        unique=True,
    )

    # 3. Regenerate employee_code for EVERY existing user as a unique random 10-digit string
    users = conn.execute(sa.text("SELECT id, employee_code FROM users ORDER BY id ASC;")).fetchall()
    allocated_codes: set[str] = set()

    for user_row in users:
        user_id = user_row.id
        old_code = user_row.employee_code

        # Generate unique 10-digit zero-padded string
        while True:
            code = f"{secrets.randbelow(10**10):010d}"
            if code not in allocated_codes:
                allocated_codes.add(code)
                break

        conn.execute(
            sa.text("UPDATE users SET employee_code = :code WHERE id = :user_id"),
            {"code": code, "user_id": user_id},
        )
        print(f"[Slice 4a Migration] User ID {user_id}: employee_code {old_code} -> {code}")

    # 4. Add check constraint for employee_code format (NULL or exactly 10 digits)
    op.create_check_constraint(
        "check_user_employee_code_format",
        "users",
        "employee_code IS NULL OR employee_code ~ '^[0-9]{10}$'",
    )

    # 5. Add users.is_email_verified and users.email_verified_at, backfilling existing users
    op.add_column(
        "users",
        sa.Column("is_email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE users SET is_email_verified = true, email_verified_at = NOW();"))

    # 6. Create table email_verification_tokens
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_tokens_id"), "email_verification_tokens", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_email_verification_tokens_user_id"),
        "email_verification_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_verification_tokens_token_hash"),
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )

    # 7. Drop sequence employee_code_seq
    op.execute(sa.text("DROP SEQUENCE IF EXISTS employee_code_seq;"))


def downgrade() -> None:
    # 1. Recreate sequence employee_code_seq
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS employee_code_seq START WITH 1001;"))

    # 2. Drop email_verification_tokens table
    op.drop_index(
        op.f("ix_email_verification_tokens_token_hash"), table_name="email_verification_tokens"
    )
    op.drop_index(
        op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens"
    )
    op.drop_index(
        op.f("ix_email_verification_tokens_id"), table_name="email_verification_tokens"
    )
    op.drop_table("email_verification_tokens")

    # 3. Drop users email verification columns
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "is_email_verified")

    # 4. Drop check constraint on employee_code format
    op.drop_constraint("check_user_employee_code_format", "users", type_="check")

    # 5. Drop lower(email) unique index
    op.drop_index("ix_users_email_lower", table_name="users")
