"""add organizations table and backfill existing data
Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-10-01 19:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l2m3n4o5p6q7"
down_revision: str | Sequence[str] | None = "k1l2m3n4o5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("gst_number", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending_payment', 'active', 'suspended')",
            name="check_org_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)

    # 2. Insert default internal organization
    op.execute(
        """
        INSERT INTO organizations (name, status, is_internal, created_at)
        VALUES ('Internal / free forever', 'active', true, NOW());
        """
    )

    # 3. Add organization_id as nullable column to company-owned tables
    op.add_column("users", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.add_column("leave_requests", sa.Column("organization_id", sa.Integer(), nullable=True))

    # 4. Backfill all existing rows into the default internal organization
    op.execute(
        """
        UPDATE users 
        SET organization_id = (SELECT id FROM organizations WHERE is_internal = true ORDER BY id ASC LIMIT 1)
        WHERE organization_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE tasks 
        SET organization_id = (SELECT id FROM organizations WHERE is_internal = true ORDER BY id ASC LIMIT 1)
        WHERE organization_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE leave_requests 
        SET organization_id = (SELECT id FROM organizations WHERE is_internal = true ORDER BY id ASC LIMIT 1)
        WHERE organization_id IS NULL;
        """
    )

    # 5. Set NOT NULL, foreign key constraints and indexes
    op.alter_column("users", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)
    op.create_foreign_key(
        "fk_users_organization_id_organizations",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.alter_column("tasks", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.create_index(op.f("ix_tasks_organization_id"), "tasks", ["organization_id"], unique=False)
    op.create_foreign_key(
        "fk_tasks_organization_id_organizations",
        "tasks",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.alter_column("leave_requests", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.create_index(
        op.f("ix_leave_requests_organization_id"), "leave_requests", ["organization_id"], unique=False
    )
    op.create_foreign_key(
        "fk_leave_requests_organization_id_organizations",
        "leave_requests",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 1. Drop foreign keys, indices, and columns from company-owned tables
    op.drop_constraint(
        "fk_leave_requests_organization_id_organizations", "leave_requests", type_="foreignkey"
    )
    op.drop_index(op.f("ix_leave_requests_organization_id"), table_name="leave_requests")
    op.drop_column("leave_requests", "organization_id")

    op.drop_constraint("fk_tasks_organization_id_organizations", "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_organization_id"), table_name="tasks")
    op.drop_column("tasks", "organization_id")

    op.drop_constraint("fk_users_organization_id_organizations", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_column("users", "organization_id")

    # 2. Drop organizations table
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")
