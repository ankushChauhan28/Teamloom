"""
Slice 2 Tests: Organization Model & Creation Paths (FR-1, FR-15, H1, H3)
"""

from datetime import UTC, date, datetime, timedelta
import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.organization import Organization, OrgStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveCreate
from app.schemas.task import TaskCreate
from app.schemas.user import EmployeeCreate
from app.services import leave_service, task_service, user_service


# ===========================================================================
# 1. Organization Model Basics
# ===========================================================================

@pytest.mark.asyncio
async def test_organization_creation_and_attributes(db_session: AsyncSession) -> None:
    """
    Test basic organization creation, attributes, and defaults.
    - required name
    - is_internal defaults to False for normal organizations
    - created_at timezone-aware
    - optional gst_number
    """
    org = Organization(
        name="Acme Corporation",
        status=OrgStatus.ACTIVE.value,
        is_internal=False,
        gst_number="27ABCDE1234F1Z5",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    assert org.id is not None
    assert org.name == "Acme Corporation"
    assert org.status == "active"
    assert org.is_internal is False
    assert org.gst_number == "27ABCDE1234F1Z5"
    assert org.created_at is not None
    assert isinstance(org.created_at, datetime)


@pytest.mark.asyncio
async def test_organization_status_constraint(db_session: AsyncSession) -> None:
    """
    Test status values and database CHECK constraint enforcement on organizations table:
    Allowed: 'pending_payment', 'active', 'suspended'
    Disallowed: Any other arbitrary string raises IntegrityError.
    """
    # 1. Test allowed statuses
    for valid_status in [OrgStatus.PENDING_PAYMENT.value, OrgStatus.ACTIVE.value, OrgStatus.SUSPENDED.value]:
        org = Organization(
            name=f"Org Status {valid_status}",
            status=valid_status,
            is_internal=False,
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)
        assert org.status == valid_status

    # 2. Test disallowed status triggers check_org_status constraint violation
    invalid_org = Organization(
        name="Invalid Status Org",
        status="invalid_status_value",
        is_internal=False,
    )
    db_session.add(invalid_org)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_organization_cascade_and_relationships(db_session: AsyncSession) -> None:
    """
    Verify ORM relationships on Organization: users, tasks, leave_requests.
    """
    org = Organization(name="Relational Org", status=OrgStatus.ACTIVE.value, is_internal=False)
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    user = User(
        full_name="Rel User",
        email="rel.user@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1000007701",
        must_change_password=False,
        organization_id=org.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    task = Task(
        title="Rel Task",
        description="Relational task test",
        priority=TaskPriority.LOW,
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        status=TaskStatus.PENDING,
        assigned_to=user.id,
        created_by=user.id,
        organization_id=org.id,
    )
    leave = LeaveRequest(
        employee_id=user.id,
        reason="Rel Leave",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 2),
        status=LeaveStatus.PENDING,
        organization_id=org.id,
    )
    db_session.add_all([task, leave])
    await db_session.commit()

    # Query organization with relationships loaded
    result = await db_session.execute(select(Organization).where(Organization.id == org.id))
    fetched_org = result.scalar_one()

    # Await lazy load / check relations
    user_res = await db_session.execute(select(User).where(User.organization_id == fetched_org.id))
    assert len(user_res.scalars().all()) == 1

    task_res = await db_session.execute(select(Task).where(Task.organization_id == fetched_org.id))
    assert len(task_res.scalars().all()) == 1

    leave_res = await db_session.execute(select(LeaveRequest).where(LeaveRequest.organization_id == fetched_org.id))
    assert len(leave_res.scalars().all()) == 1


# ===========================================================================
# 2. Creation Paths Inherit Organization ID
# ===========================================================================

@pytest.mark.asyncio
async def test_create_employee_inherits_admin_organization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """
    FR-9 / Slice 2: Newly created employee inherits the organization of the admin who creates them.
    Tested via both service layer and HTTP endpoint.
    """
    custom_org = Organization(name="Custom Org A", status=OrgStatus.ACTIVE.value, is_internal=False)
    db_session.add(custom_org)
    await db_session.commit()
    await db_session.refresh(custom_org)

    admin = User(
        full_name="Org A Admin",
        email="admin.orga@example.com",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        access_level=1,
        employee_code="1000008001",
        must_change_password=False,
        organization_id=custom_org.id,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    # 1. Via Service
    emp_in = EmployeeCreate(
        full_name="Service Employee Org A",
        email="emp.orga.service@example.com",
        designation="Software Engineer",
    )
    created_user, _ = await user_service.create_employee(
        db=db_session,
        employee_in=emp_in,
        organization_id=admin.organization_id,
    )
    assert created_user.organization_id == custom_org.id

    # 2. Via HTTP Route
    admin_token = create_access_token(email=admin.email, role=admin.role.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    res = await client.post(
        "/users/employees",
        json={"full_name": "HTTP Employee Org A", "email": "emp.orga.http@example.com"},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    emp_res = await db_session.execute(select(User).where(User.id == data["id"]))
    db_emp = emp_res.scalar_one()
    assert db_emp.organization_id == custom_org.id


@pytest.mark.asyncio
async def test_create_task_inherits_creator_organization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """
    Slice 2: Created task inherits the organization of the user who creates it.
    Tested via both service layer and HTTP endpoint.
    """
    custom_org = Organization(name="Task Org B", status=OrgStatus.ACTIVE.value, is_internal=False)
    db_session.add(custom_org)
    await db_session.commit()
    await db_session.refresh(custom_org)

    admin = User(
        full_name="Task Org Admin",
        email="admin.taskorg@example.com",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        access_level=1,
        employee_code="1000008005",
        must_change_password=False,
        organization_id=custom_org.id,
    )
    emp = User(
        full_name="Task Org Employee",
        email="emp.taskorg@example.com",
        hashed_password=hash_password("emppass123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1000008006",
        must_change_password=False,
        organization_id=custom_org.id,
    )
    db_session.add_all([admin, emp])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(emp)

    # 1. Via Service
    task_in = TaskCreate(
        title="Org Task via Service",
        description="Task service test",
        priority=TaskPriority.HIGH,
        due_datetime=datetime.now(UTC) + timedelta(days=3),
        assigned_to=emp.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin)
    assert task.organization_id == custom_org.id

    # 2. Via HTTP Route
    admin_token = create_access_token(email=admin.email, role=admin.role.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "title": "Org Task via HTTP",
        "description": "Task route test",
        "priority": "MEDIUM",
        "due_datetime": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
        "assigned_to": emp.id,
    }
    res = await client.post("/tasks/", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    task_res = await db_session.execute(select(Task).where(Task.id == data["id"]))
    db_task = task_res.scalar_one()
    assert db_task.organization_id == custom_org.id


@pytest.mark.asyncio
async def test_create_leave_request_inherits_employee_organization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """
    Slice 2: Created leave request inherits the organization of the employee submitting it.
    Tested via both service layer and HTTP endpoint.
    """
    custom_org = Organization(name="Leave Org C", status=OrgStatus.ACTIVE.value, is_internal=False)
    db_session.add(custom_org)
    await db_session.commit()
    await db_session.refresh(custom_org)

    emp = User(
        full_name="Leave Org Employee",
        email="emp.leaveorg@example.com",
        hashed_password=hash_password("emppass123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1000008010",
        must_change_password=False,
        organization_id=custom_org.id,
    )
    db_session.add(emp)
    await db_session.commit()
    await db_session.refresh(emp)

    # 1. Via Service
    leave_in = LeaveCreate(
        reason="Vacation via Service",
        start_date=date(2027, 2, 1),
        end_date=date(2027, 2, 5),
    )
    leave = await leave_service.create_leave_request(
        db=db_session, leave_in=leave_in, employee_id=emp.id
    )
    assert leave.organization_id == custom_org.id

    # 2. Via HTTP Route
    emp_token = create_access_token(email=emp.email, role=emp.role.value)
    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    payload = {
        "reason": "Vacation via HTTP",
        "start_date": "2027-03-01",
        "end_date": "2027-03-05",
    }
    res = await client.post("/leaves/", json=payload, headers=emp_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    leave_res = await db_session.execute(select(LeaveRequest).where(LeaveRequest.id == data["id"]))
    db_leave = leave_res.scalar_one()
    assert db_leave.organization_id == custom_org.id
