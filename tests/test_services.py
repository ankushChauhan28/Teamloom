"""
Unit Tests for Service Layer Functions (Isolated Business Logic)
"""

from datetime import date, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationException,
    BadRequestException,
    InvalidCredentialsException,
    ResourceNotFoundException,
    UserAlreadyExistsException,
)
from app.models.leave import LeaveStatus
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveCreate, LeaveUpdateStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.schemas.user import EmployeeCreate, UserLogin
from app.services import auth_service, leave_service, task_service, user_service

# ==========================================
# AUTH SERVICE UNIT TESTS
# ==========================================


@pytest.mark.asyncio
async def test_unit_authenticate_user_wrong_password_raises_exception(
    db_session: AsyncSession,
    employee_user: User,
) -> None:
    """
    Unit Test: Authenticating with incorrect password raises `InvalidCredentialsException`.
    """
    login_in = UserLogin(employee_code=employee_user.employee_code, password="wrongpassword!")
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
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

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
        await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

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
        reviewer=admin_user,
    )

    assert reviewed_leave.status == LeaveStatus.APPROVED
    assert reviewed_leave.reviewed_by == admin_user.id


# ==========================================
# USER SERVICE UNIT TESTS
# ==========================================


@pytest.mark.asyncio
async def test_unit_set_user_manager_success(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Setting a valid manager ID on an employee succeeds.
    """
    updated_user = await user_service.set_user_manager(
        db=db_session, target_user_id=employee_user.id, manager_id=admin_user.id
    )
    assert updated_user.manager_id == admin_user.id


@pytest.mark.asyncio
async def test_unit_set_user_manager_nonexistent_target_raises(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Setting manager for a non-existent user ID raises ResourceNotFoundException.
    """
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await user_service.set_user_manager(
            db=db_session, target_user_id=99999, manager_id=admin_user.id
        )
    assert "user not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_manager_nonexistent_manager_raises(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Unit Test: Setting manager_id to a non-existent user ID raises ResourceNotFoundException.
    """
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await user_service.set_user_manager(
            db=db_session, target_user_id=employee_user.id, manager_id=99999
        )
    assert "manager user not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_manager_self_raises(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Unit Test: Setting manager_id to user's own ID raises BadRequestException.
    """
    with pytest.raises(BadRequestException) as exc_info:
        await user_service.set_user_manager(
            db=db_session, target_user_id=employee_user.id, manager_id=employee_user.id
        )
    assert "cannot be their own manager" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_manager_direct_cycle_raises(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Creating a 2-node circular chain (A -> B, then B -> A) raises BadRequestException.
    """
    # Set User B (employee) manager to User A (admin)
    await user_service.set_user_manager(
        db=db_session, target_user_id=employee_user.id, manager_id=admin_user.id
    )

    # Attempt to set User A's manager to User B (creating A -> B -> A cycle)
    with pytest.raises(BadRequestException) as exc_info:
        await user_service.set_user_manager(
            db=db_session, target_user_id=admin_user.id, manager_id=employee_user.id
        )
    assert "circular manager hierarchy" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_manager_longer_cycle_raises(
    db_session: AsyncSession
) -> None:
    """
    Unit Test: Creating a 3-node circular chain (A -> B -> C, then C -> A) raises BadRequestException.
    """
    # Create 3 users
    emp_a, _ = await user_service.create_employee(
        db=db_session,
        employee_in=EmployeeCreate(email="a@example.com", full_name="User A"),
    )
    emp_b, _ = await user_service.create_employee(
        db=db_session,
        employee_in=EmployeeCreate(email="b@example.com", full_name="User B"),
    )
    emp_c, _ = await user_service.create_employee(
        db=db_session,
        employee_in=EmployeeCreate(email="c@example.com", full_name="User C"),
    )
    user_a, user_b, user_c = emp_a, emp_b, emp_c

    # A reports to B
    await user_service.set_user_manager(
        db=db_session, target_user_id=user_a.id, manager_id=user_b.id
    )
    # B reports to C
    await user_service.set_user_manager(
        db=db_session, target_user_id=user_b.id, manager_id=user_c.id
    )

    # Attempting C reports to A (creating C -> A -> B -> C cycle)
    with pytest.raises(BadRequestException) as exc_info:
        await user_service.set_user_manager(
            db=db_session, target_user_id=user_c.id, manager_id=user_a.id
        )
    assert "circular manager hierarchy" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_manager_clear_success(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Setting manager_id to None clears existing manager.
    """
    await user_service.set_user_manager(
        db=db_session, target_user_id=employee_user.id, manager_id=admin_user.id
    )
    cleared_user = await user_service.set_user_manager(
        db=db_session, target_user_id=employee_user.id, manager_id=None
    )
    assert cleared_user.manager_id is None


@pytest.mark.asyncio
async def test_unit_create_task_non_employee_assignee_raises_exception(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Assigning task to ADMIN (non-EMPLOYEE) raises BadRequestException.
    """
    task_in = TaskCreate(
        title="Admin Assignee Task",
        description="Should fail",
        priority=TaskPriority.HIGH,
        due_date=date.today() + timedelta(days=2),
        assigned_to=admin_user.id,
    )
    with pytest.raises(BadRequestException) as exc_info:
        await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)
    assert "only be assigned to users with the employee role" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_get_tasks_invalid_sort_column_raises_exception(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Passing invalid sort_by column to get_tasks raises BadRequestException.
    """
    with pytest.raises(BadRequestException) as exc_info:
        await task_service.get_tasks(db=db_session, user=admin_user, sort_by="non_existent_column")
    assert "invalid sort column" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_get_team_tasks_filtering_and_sorting(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: get_team_tasks with status, priority, and sort_by filters.
    """
    await user_service.set_user_manager(
        db=db_session, target_user_id=employee_user.id, manager_id=admin_user.id
    )
    task_in = TaskCreate(
        title="Team Task Filter",
        description="Filter test",
        priority=TaskPriority.HIGH,
        due_date=date.today() + timedelta(days=2),
        assigned_to=employee_user.id,
    )
    await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

    tasks = await task_service.get_team_tasks(
        db=db_session,
        user=admin_user,
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        sort_by="title",
    )
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_unit_update_task_employee_disallowed_field_raises_exception(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Employee attempting to update title field on task raises AuthorizationException.
    """
    task_in = TaskCreate(
        title="Original Title",
        description="Desc",
        priority=TaskPriority.LOW,
        due_date=date.today() + timedelta(days=2),
        assigned_to=employee_user.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

    update_in = TaskUpdate(title="New Unauthorized Title")
    with pytest.raises(AuthorizationException) as exc_info:
        await task_service.update_task(
            db=db_session, task_id=task.id, task_update=update_in, user=employee_user
        )
    assert "employees are only permitted to update the task status" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_delete_task_non_admin_raises_exception(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Non-admin attempting to delete task raises AuthorizationException.
    """
    task_in = TaskCreate(
        title="Delete Test Task",
        description="Desc",
        priority=TaskPriority.LOW,
        due_date=date.today() + timedelta(days=2),
        assigned_to=employee_user.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

    with pytest.raises(AuthorizationException) as exc_info:
        await task_service.delete_task(db=db_session, task_id=task.id, user=employee_user)
    assert "only administrators can delete tasks" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_delete_task_nonexistent_raises_exception(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Deleting nonexistent task ID raises ResourceNotFoundException.
    """
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await task_service.delete_task(db=db_session, task_id=99999, user=admin_user)
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_review_leave_nonexistent_raises_exception(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Reviewing nonexistent leave request raises ResourceNotFoundException.
    """
    review_in = LeaveUpdateStatus(status=LeaveStatus.APPROVED)
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await leave_service.review_leave_request(
            db=db_session, leave_id=99999, review_in=review_in, reviewer=admin_user
        )
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_review_leave_already_reviewed_raises_exception(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Reviewing an already reviewed leave request raises BadRequestException.
    """
    leave_in = LeaveCreate(
        reason="Vacation",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=4),
    )
    leave = await leave_service.create_leave_request(
        db=db_session, leave_in=leave_in, employee_id=employee_user.id
    )
    review_in = LeaveUpdateStatus(status=LeaveStatus.APPROVED)
    await leave_service.review_leave_request(
        db=db_session, leave_id=leave.id, review_in=review_in, reviewer=admin_user
    )

    # Review second time -> raises BadRequestException
    with pytest.raises(BadRequestException) as exc_info:
        await leave_service.review_leave_request(
            db=db_session, leave_id=leave.id, review_in=review_in, reviewer=admin_user
        )
    assert "already been reviewed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_review_leave_invalid_status_raises_exception(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Reviewing leave with status other than APPROVED or REJECTED raises BadRequestException.
    """
    leave_in = LeaveCreate(
        reason="Vacation",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=4),
    )
    leave = await leave_service.create_leave_request(
        db=db_session, leave_in=leave_in, employee_id=employee_user.id
    )
    review_in = LeaveUpdateStatus(status=LeaveStatus.PENDING)
    with pytest.raises(BadRequestException) as exc_info:
        await leave_service.review_leave_request(
            db=db_session, leave_id=leave.id, review_in=review_in, reviewer=admin_user
        )
    assert "must be either approved or rejected" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_get_leaves_invalid_sort_column_raises_exception(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Passing invalid sort_by to get_leaves raises BadRequestException.
    """
@pytest.mark.asyncio
async def test_unit_user_service_additional_coverage(
    db_session: AsyncSession, employee_user: User, admin_user: User
) -> None:
    """
    Unit Test: Additional coverage for user_service functions.
    """
    # 1. reset_employee_temp_password success & nonexistent
    updated_emp, email_sent = await user_service.reset_employee_temp_password(
        db=db_session, target_user_id=employee_user.id
    )
    assert updated_emp.must_change_password is True
    assert updated_emp.id == employee_user.id

    with pytest.raises(ResourceNotFoundException) as exc_info:
        await user_service.reset_employee_temp_password(db=db_session, target_user_id=99999)
    assert "not found" in str(exc_info.value).lower()

    # 2. update_user_profile
    from app.schemas.user import UserUpdate
    updated_profile = await user_service.update_user_profile(
        db=db_session, user=employee_user, user_update=UserUpdate(full_name="New Updated Name")
    )
    assert updated_profile.full_name == "New Updated Name"

    # 3. get_employees
    employees = await user_service.get_employees(db=db_session)
    assert len(employees) >= 1

    # 4. get_user_direct_reports
    await user_service.set_user_manager(
        db=db_session, target_user_id=employee_user.id, manager_id=admin_user.id
    )
    reports = await user_service.get_user_direct_reports(db=db_session, user_id=admin_user.id)
    assert len(reports) == 1
    assert reports[0].id == employee_user.id

    # 5. get_team_leave_requests
    leave_in = LeaveCreate(
        reason="Direct Team Leave Test",
        start_date=date.today() + timedelta(days=1),
        end_date=date.today() + timedelta(days=3),
    )
    await leave_service.create_leave_request(
        db=db_session, leave_in=leave_in, employee_id=employee_user.id
    )
    team_leaves = await leave_service.get_team_leave_requests(
        db=db_session, user=admin_user, status=LeaveStatus.PENDING, sort_by="start_date"
    )
    assert len(team_leaves) == 1
    assert team_leaves[0].employee_id == employee_user.id

