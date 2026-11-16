"""add missing indexes for performance

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-11-16 14:15:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o5p6q7r8s9t0"
down_revision: str | Sequence[str] | None = "n4o5p6q7r8s9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. tasks.assigned_to index
    op.create_index(
        op.f("ix_tasks_assigned_to"),
        "tasks",
        ["assigned_to"],
        unique=False,
    )
    # 2. tasks composite (organization_id, status) index
    op.create_index(
        op.f("ix_tasks_organization_id_status"),
        "tasks",
        ["organization_id", "status"],
        unique=False,
    )
    # 3. leave_requests.employee_id index
    op.create_index(
        op.f("ix_leave_requests_employee_id"),
        "leave_requests",
        ["employee_id"],
        unique=False,
    )
    # 4. leave_requests composite (organization_id, status) index
    op.create_index(
        op.f("ix_leave_requests_organization_id_status"),
        "leave_requests",
        ["organization_id", "status"],
        unique=False,
    )
    # 5. users.reports_to_id index
    op.create_index(
        op.f("ix_users_reports_to_id"),
        "users",
        ["reports_to_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_reports_to_id"), table_name="users")
    op.drop_index(op.f("ix_leave_requests_organization_id_status"), table_name="leave_requests")
    op.drop_index(op.f("ix_leave_requests_employee_id"), table_name="leave_requests")
    op.drop_index(op.f("ix_tasks_organization_id_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_assigned_to"), table_name="tasks")
