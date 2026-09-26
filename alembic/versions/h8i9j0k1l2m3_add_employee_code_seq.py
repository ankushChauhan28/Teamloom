"""add employee_code_seq sequence

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: str | Sequence[str] | None = "g7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create PostgreSQL sequence for atomic employee code generation."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE SEQUENCE IF NOT EXISTS employee_code_seq START WITH 1001;"
            )
        )


def downgrade() -> None:
    """Drop employee_code_seq sequence."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP SEQUENCE IF EXISTS employee_code_seq;"))
