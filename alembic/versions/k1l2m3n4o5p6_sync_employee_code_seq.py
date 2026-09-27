"""sync employee_code_seq to max existing employee_code

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-09-27 14:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: str | Sequence[str] | None = "j0k1l2m3n4o5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Sync employee_code_seq sequence to current maximum employee_code number."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                SELECT setval(
                    'employee_code_seq',
                    (SELECT COALESCE(MAX(CAST(SUBSTRING(employee_code FROM 5) AS INTEGER)), 1000)
                     FROM users
                     WHERE employee_code ~ '^EMP-[0-9]+$')
                );
                """
            )
        )


def downgrade() -> None:
    """No-op on downgrade as sequence state does not revert."""
    pass
