"""add revoked_tokens table

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"
down_revision: str | Sequence[str] | None = "f6g7h8i9j0k1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema by creating revoked_tokens table."""
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_jti", sa.String(length=255), nullable=False),
        sa.Column("exp_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_jti"),
    )
    op.create_index(op.f("ix_revoked_tokens_id"), "revoked_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_revoked_tokens_token_jti"), "revoked_tokens", ["token_jti"], unique=True)
    op.create_index(
        op.f("ix_revoked_tokens_exp_timestamp"), "revoked_tokens", ["exp_timestamp"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema by dropping revoked_tokens table."""
    op.drop_index(op.f("ix_revoked_tokens_exp_timestamp"), table_name="revoked_tokens")
    op.drop_index(op.f("ix_revoked_tokens_token_jti"), table_name="revoked_tokens")
    op.drop_index(op.f("ix_revoked_tokens_id"), table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
