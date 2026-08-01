"""
Unit Tests for Service Layer Functions (Isolated Business Logic)
"""

from datetime import date, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    InvalidCredentialsException,
    ResourceNotFoundException,
    UserAlreadyExistsException,
)
from app.models.leave import LeaveStatus
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus
from app.schemas.task import TaskCreate
from app.schemas.user import UserCreate, UserLogin
from app.services import auth_service, leave_service, task_service

# ==========================================
# AUTH SERVICE UNIT TESTS
# ==========================================


@pytest.mark.asyncio
async def test_unit_register_user_success(db_session: AsyncSession) -> None:
    """
    Unit Test: Directly call `auth_service.register_user` asynchronously and assert User is created.
    """
    user_in = UserCreate(
        email="direct.unit@example.com",
        full_name="Direct Unit User",
        password="unitpassword123",
    )
    user = await auth_service.register_user(db=db_session, user_in=user_in)

    assert user.id is not None
    assert user.email == "direct.unit@example.com"
    assert user.role == UserRole.EMPLOYEE
    assert user.hashed_password != "unitpassword123"


@pytest.mark.asyncio
async def test_unit_register_user_duplicate_raises_exception(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Unit Test: Attempting to register an existing email directly raises `UserAlreadyExistsException`.
    """
    user_in = UserCreate(
        email=employee_user.email,
        full_name="Duplicate Name",
        password="password123",
    )
    with pytest.raises(UserAlreadyExistsException) as exc_info:
        await auth_service.register_user(db=db_session, user_in=user_in)

    assert "already exists" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_authenticate_user_wrong_password_raises_exception(
    db_session: AsyncSession,
    employee_user: User,
) -> None:
    """
    Unit Test: Authenticating with incorrect password raises `InvalidCredentialsException`.
    """
    login_in = UserLogin(email=employee_user.email, password="wrongpassword!")
    with pytest.raises(InvalidCredentialsException):
        await auth_service.authenticate_user(db=db_session, login_in=login_in)


# ==========================================
# TASK SERVICE UNIT TESTS
# ==========================================


@pytest.mark.asyncio
async def test_unit_create_task_success(
    db_session: AsyncSession,
    admin_user: User,
    employee_user: User,
) -> None:
    """
    Unit Test: Directly call `task_service.create_task` with TaskCreate domain object.
    """
    task_in = TaskCreate(
        title="Service Unit Task",
        description="Testing task service directly.",
        priority=TaskPriority.HIGH,
        due_date=date.today() + timedelta(days=7),
        assigned_to=employee_user.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator_id=admin_user.id)

    assert task.id is not None
    assert task.title == "Service Unit Task"
    assert task.status == TaskStatus.PENDING
    assert task.created_by == admin_user.id
    assert task.assigned_to == employee_user.id


@pytest.mark.asyncio
async def test_unit_create_task_nonexistent_assignee_raises_exception(
    db_session: AsyncSession,
    admin_user: User,
) -> None:
    """
    Unit Test: Assigning a task to a non-existent user ID raises `ResourceNotFoundException`.
    """
    task_in = TaskCreate(
        title="Invalid Assignee Task",
        description="Nonexistent assignee.",
        priority=TaskPriority.LOW,
        due_date=date.today() + timedelta(days=2),
        assigned_to=99999,
    )
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await task_service.create_task(db=db_session, task_in=task_in, creator_id=admin_user.id)

    assert "not found" in str(exc_info.value).lower()


# ==========================================
# LEAVE SERVICE UNIT TESTS
# ==========================================


@pytest.mark.asyncio
async def test_unit_create_leave_invalid_dates_raises_exception(
    db_session: AsyncSession,
    employee_user: User,
) -> None:
    """
    Unit Test: Submitting a leave request with end_date before start_date raises `BadRequestException`.
    """
    leave_in = LeaveCreate(
        reason="Invalid Date Range",
        start_date=date.today() + timedelta(days=10),
        end_date=date.today() + timedelta(days=5),
    )
    with pytest.raises(BadRequestException) as exc_info:
        await leave_service.create_leave_request(
            db=db_session, leave_in=leave_in, employee_id=employee_user.id
        )

    assert "cannot be prior to start date" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_review_leave_request_success(
    db_session: AsyncSession,
    admin_user: User,
    employee_user: User,
) -> None:
    """
    Unit Test: Reviewing a PENDING leave request updates status and reviewer ID.
    """
    leave_in = LeaveCreate(
        reason="Unit Test Vacation",
        start_date=date.today() + timedelta(days=14),
        end_date=date.today() + timedelta(days=18),
    )
    leave = await leave_service.create_leave_request(
        db=db_session, leave_in=leave_in, employee_id=employee_user.id
    )

    review_in = LeaveUpdateStatus(status=LeaveStatus.APPROVED)
    reviewed_leave = await leave_service.review_leave_request(
        db=db_session,
        leave_id=leave.id,
        review_in=review_in,
        reviewer_id=admin_user.id,
    )

    assert reviewed_leave.status == LeaveStatus.APPROVED
    assert reviewed_leave.reviewed_by == admin_user.id
