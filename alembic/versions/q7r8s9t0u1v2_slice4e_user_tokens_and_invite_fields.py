"""slice4e_user_tokens_and_invite_fields

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-11-18 18:44:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Create user_tokens table ---
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "token_type IN ('INVITE', 'PASSWORD_RESET')",
            name="check_user_token_type",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_tokens_id"), "user_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_user_tokens_user_id"), "user_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_tokens_token_hash"), "user_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_user_tokens_token_type"), "user_tokens", ["token_type"], unique=False)
    op.create_index(
        "ix_user_tokens_user_type_used",
        "user_tokens",
        ["user_id", "token_type", "used_at"],
        unique=False,
    )

    # --- Add columns to users ---
    op.add_column(
        "users",
        sa.Column(
            "invitation_status",
            sa.String(length=20),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column(
        "users",
        sa.Column("invitation_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("tokens_valid_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "check_user_invitation_status",
        "users",
        "invitation_status IN ('PENDING', 'ACTIVE', 'REVOKED')",
    )
    op.create_index(
        "ix_users_invitation_status",
        "users",
        ["invitation_status"],
        unique=False,
    )


def downgrade() -> None:
    # --- Remove from users ---
    op.drop_index("ix_users_invitation_status", table_name="users")
    op.drop_constraint("check_user_invitation_status", "users", type_="check")
    op.drop_column("users", "tokens_valid_after")
    op.drop_column("users", "invitation_accepted_at")
    op.drop_column("users", "invitation_status")

    # --- Drop user_tokens table ---
    op.drop_index("ix_user_tokens_user_type_used", table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_token_type"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_token_hash"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_user_id"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_id"), table_name="user_tokens")
    op.drop_table("user_tokens")
