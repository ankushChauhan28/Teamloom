"""Slice 4c: Backfill is_email_verified for all existing users

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-10-04 00:00:00.000000

Note on Downgrade:
Downgrade is a safe no-op. We intentionally do not un-verify pre-existing users upon migration rollback.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: str | Sequence[str] | None = "m3n4o5p6q7r8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill is_email_verified=true and email_verified_at=now for all existing users
    # so legacy admins and employees are never locked out once email verification enforcement is active.
    op.execute(
        sa.text(
            "UPDATE users "
            "SET is_email_verified = true, email_verified_at = COALESCE(email_verified_at, NOW()) "
            "WHERE is_email_verified = false;"
        )
    )


def downgrade() -> None:
    # Safe no-op on downgrade to prevent locking out existing accounts
    pass
