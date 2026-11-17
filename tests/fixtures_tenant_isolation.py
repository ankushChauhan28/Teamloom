"""
Tenant Isolation Test Fixtures (Slice 5, Depth A)

Dedicated, reusable fixture module providing two fully isolated organizations
(Org A: Alpha, Org B: Bravo), each provisioned with:
- Tier 1 Admin (access_level=1)
- Tier 2 Supervisor (access_level=2, reports to Admin)
- Tier 3 Employee (access_level=3, reports to Supervisor)
- Active Task (assigned to Employee, created by Supervisor)
- Soft-Deleted Task (assigned to Employee, deleted by Admin)
- Leave Request (assigned to Employee, status PENDING)
- Pre-generated JWT Bearer Authorization headers for all 6 roles
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.organization import Organization, OrgStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole

# Pre-compute password hash once to ensure fast, deterministic fixture setup
_COMMON_TEST_HASH = hash_password("TenantPass123!")


@dataclass
class TenantOrgContext:
    org: Organization
    admin: User
    supervisor: User
    employee: User
    task: Task
    soft_deleted_task: Task
    leave: LeaveRequest
    admin_headers: dict[str, str]
    supervisor_headers: dict[str, str]
    employee_headers: dict[str, str]


@dataclass
class TenantIsolationSetup:
    org_a: TenantOrgContext
    org_b: TenantOrgContext


async def _build_org_context(
    db_session: AsyncSession,
    name: str,
    domain: str,
    code_prefix: str,
) -> TenantOrgContext:
    org = Organization(
        name=name,
        status=OrgStatus.ACTIVE.value,
        is_internal=False,
    )
    db_session.add(org)
    await db_session.flush()

    admin = User(
        full_name=f"{name} Admin",
        email=f"admin@{domain}",
        hashed_password=_COMMON_TEST_HASH,
        role=UserRole.ADMIN,
        access_level=1,
        employee_code=f"{code_prefix}0000001",
        is_email_verified=True,
        must_change_password=False,
        organization_id=org.id,
    )
    db_session.add(admin)
    await db_session.flush()

    supervisor = User(
        full_name=f"{name} Supervisor",
        email=f"supervisor@{domain}",
        hashed_password=_COMMON_TEST_HASH,
        role=UserRole.EMPLOYEE,
        access_level=2,
        employee_code=f"{code_prefix}0000002",
        is_email_verified=True,
        must_change_password=False,
        reports_to_id=admin.id,
        organization_id=org.id,
    )
    db_session.add(supervisor)
    await db_session.flush()

    employee = User(
        full_name=f"{name} Employee",
        email=f"employee@{domain}",
        hashed_password=_COMMON_TEST_HASH,
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code=f"{code_prefix}0000003",
        is_email_verified=True,
        must_change_password=False,
        reports_to_id=supervisor.id,
        organization_id=org.id,
    )
    db_session.add(employee)
    await db_session.flush()

    active_task = Task(
        title=f"{name} Active Task",
        description=f"Standard active task for {name}",
        priority=TaskPriority.HIGH,
        status=TaskStatus.PENDING,
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        assigned_to=employee.id,
        created_by=supervisor.id,
        organization_id=org.id,
    )
    db_session.add(active_task)

    deleted_task = Task(
        title=f"{name} Soft-Deleted Task",
        description=f"Soft-deleted task for {name}",
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.PENDING,
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        assigned_to=employee.id,
        created_by=admin.id,
        organization_id=org.id,
        is_deleted=True,
        deleted_at=datetime.now(UTC),
        deleted_by=admin.id,
    )
    db_session.add(deleted_task)

    leave = LeaveRequest(
        employee_id=employee.id,
        reason=f"{name} Annual Leave",
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=8),
        status=LeaveStatus.PENDING,
        organization_id=org.id,
    )
    db_session.add(leave)

    await db_session.commit()
    await db_session.refresh(org)
    await db_session.refresh(admin)
    await db_session.refresh(supervisor)
    await db_session.refresh(employee)
    await db_session.refresh(active_task)
    await db_session.refresh(deleted_task)
    await db_session.refresh(leave)

    admin_token = create_access_token(email=admin.email, role=admin.role.value)
    supervisor_token = create_access_token(email=supervisor.email, role=supervisor.role.value)
    employee_token = create_access_token(email=employee.email, role=employee.role.value)

    return TenantOrgContext(
        org=org,
        admin=admin,
        supervisor=supervisor,
        employee=employee,
        task=active_task,
        soft_deleted_task=deleted_task,
        leave=leave,
        admin_headers={"Authorization": f"Bearer {admin_token}"},
        supervisor_headers={"Authorization": f"Bearer {supervisor_token}"},
        employee_headers={"Authorization": f"Bearer {employee_token}"},
    )


@pytest.fixture
async def isolation_setup(db_session: AsyncSession) -> TenantIsolationSetup:
    """
    Dedicated fixture provisioning two isolated tenants with full 3-tier hierarchies,
    active/deleted tasks, and leave requests.
    """
    org_a = await _build_org_context(
        db_session=db_session,
        name="Org Alpha",
        domain="alpha.example.com",
        code_prefix="200",
    )
    org_b = await _build_org_context(
        db_session=db_session,
        name="Org Bravo",
        domain="bravo.example.com",
        code_prefix="300",
    )
    return TenantIsolationSetup(org_a=org_a, org_b=org_b)
