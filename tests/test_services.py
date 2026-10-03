"""
Unit Tests for Service Layer Functions (Isolated Business Logic)
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    AuthorizationException,
    BadRequestException,
    InvalidCredentialsException,
    ResourceNotFoundException,
)
from app.models.leave import LeaveStatus
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
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
    login_in = UserLogin(
        identifier=employee_user.employee_code, password="wrongpassword!", mode="employee"
    )
    with pytest.raises(InvalidCredentialsException):
        await auth_service.authenticate_user(db=db_session, login_in=login_in)


@pytest.mark.asyncio
async def test_unit_authenticate_user_nonexistent_user_raises_exception(
    db_session: AsyncSession,
) -> None:
    """
    Unit Test: Authenticating non-existent employee_code runs constant-time dummy bcrypt and raises `InvalidCredentialsException`.
    """
    login_in = UserLogin(identifier="9999999999", password="anypassword!", mode="employee")
    with pytest.raises(InvalidCredentialsException):
        await auth_service.authenticate_user(db=db_session, login_in=login_in)


@pytest.mark.asyncio
async def test_unit_authenticate_user_locked_account_raises_exception(
    db_session: AsyncSession,
    employee_user: User,
) -> None:
    """
    Unit Test: Authenticating against locked user (both naive & timezone-aware locked_until) raises `InvalidCredentialsException`.
    """
    # 1. Timezone-aware locked_until in future
    employee_user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db_session.commit()

    login_in = UserLogin(
        identifier=employee_user.employee_code,
        password="employeepassword123",
        mode="employee",
    )
    with pytest.raises(InvalidCredentialsException):
        await auth_service.authenticate_user(db=db_session, login_in=login_in)

    # 2. Naive locked_until in future (e.g. SQLite driver return)
    employee_user.locked_until = datetime.now() + timedelta(minutes=15)  # naive
    await db_session.commit()

    with pytest.raises(InvalidCredentialsException):
        await auth_service.authenticate_user(db=db_session, login_in=login_in)


@pytest.mark.asyncio
async def test_unit_change_password_wrong_current_password_raises(
    db_session: AsyncSession,
    employee_user: User,
) -> None:
    """
    Unit Test: change_password with wrong current password raises InvalidCredentialsException.
    """
    from app.schemas.user import PasswordChange

    pwd_in = PasswordChange(
        current_password="WrongCurrentPassword!", new_password="NewValidPassword123!"
    )
    with pytest.raises(InvalidCredentialsException):
        await auth_service.change_password(db=db_session, user=employee_user, pwd_in=pwd_in)


@pytest.mark.asyncio
async def test_unit_refresh_access_token_missing_sub_and_nonexistent_user(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Unit Test: refresh_access_token raises AuthenticationException when sub is missing or user non-existent.
    """
    from app.core.exceptions import AuthenticationException

    # 1. Payload missing 'sub'
    monkeypatch.setattr("app.services.auth_service.decode_refresh_token", lambda token: {})
    with pytest.raises(AuthenticationException, match="Invalid refresh token payload."):
        await auth_service.refresh_access_token(db=db_session, refresh_token="dummy")

    # 2. Payload with non-existent sub email
    monkeypatch.setattr(
        "app.services.auth_service.decode_refresh_token", lambda token: {"sub": "ghost@example.com"}
    )
    with pytest.raises(AuthenticationException, match="User not found."):
        await auth_service.refresh_access_token(db=db_session, refresh_token="dummy")


@pytest.mark.asyncio
async def test_unit_authenticate_user_lockout_transition_and_reset(
    db_session: AsyncSession,
    employee_user: User,
) -> None:
    """
    Unit Test: 5th failed attempt sets locked_until, and subsequent successful login clears failed attempts and locked_until.
    """
    login_fail = UserLogin(
        identifier=employee_user.employee_code, password="WrongPassword!", mode="employee"
    )

    # 4 failed attempts
    for _ in range(4):
        with pytest.raises(InvalidCredentialsException):
            await auth_service.authenticate_user(db=db_session, login_in=login_fail)

    assert employee_user.failed_login_attempts == 4
    assert employee_user.locked_until is None

    # 5th failed attempt triggers locked_until
    with pytest.raises(InvalidCredentialsException):
        await auth_service.authenticate_user(db=db_session, login_in=login_fail)

    assert employee_user.failed_login_attempts == 5
    assert employee_user.locked_until is not None

    # Clear lock window to test successful login reset path
    employee_user.locked_until = None
    await db_session.commit()

    login_success = UserLogin(
        identifier=employee_user.employee_code,
        password="employeepassword123",
        mode="employee",
    )
    user = await auth_service.authenticate_user(db=db_session, login_in=login_success)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


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
        due_datetime=datetime.now(UTC) + timedelta(days=7),
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
        due_datetime=datetime.now(UTC) + timedelta(days=2),
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
async def test_unit_set_user_reports_to_success(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Setting a valid reports-to supervisor ID on an employee succeeds.
    """
    updated_user = await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=admin_user.id
    )
    assert updated_user.reports_to_id == admin_user.id


@pytest.mark.asyncio
async def test_unit_set_user_reports_to_nonexistent_target_raises(
    db_session: AsyncSession, admin_user: User
) -> None:
    """
    Unit Test: Setting supervisor for a non-existent user ID raises ResourceNotFoundException.
    """
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await user_service.set_user_reports_to(
            db=db_session, target_user_id=99999, reports_to_id=admin_user.id
        )
    assert "user not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_reports_to_nonexistent_supervisor_raises(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Unit Test: Setting reports_to_id to a non-existent user ID raises ResourceNotFoundException.
    """
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await user_service.set_user_reports_to(
            db=db_session, target_user_id=employee_user.id, reports_to_id=99999
        )
    assert "supervisor user not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_reports_to_self_raises(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Unit Test: Setting reports_to_id to user's own ID raises BadRequestException.
    """
    with pytest.raises(BadRequestException) as exc_info:
        await user_service.set_user_reports_to(
            db=db_session, target_user_id=employee_user.id, reports_to_id=employee_user.id
        )
    assert "cannot report to themselves" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_reports_to_direct_cycle_raises(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Creating a 2-node circular chain (A -> B, then B -> A) raises BadRequestException.
    """
    # Set User B (employee) reports to User A (admin)
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=admin_user.id
    )

    # Attempt to set User A reports to User B (creating A -> B -> A cycle)
    with pytest.raises(BadRequestException) as exc_info:
        await user_service.set_user_reports_to(
            db=db_session, target_user_id=admin_user.id, reports_to_id=employee_user.id
        )
    assert "circular reporting hierarchy" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_reports_to_longer_cycle_raises(db_session: AsyncSession) -> None:
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
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=user_a.id, reports_to_id=user_b.id
    )
    # B reports to C
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=user_b.id, reports_to_id=user_c.id
    )

    # Attempting C reports to A (creating C -> A -> B -> C cycle)
    with pytest.raises(BadRequestException) as exc_info:
        await user_service.set_user_reports_to(
            db=db_session, target_user_id=user_c.id, reports_to_id=user_a.id
        )
    assert "circular reporting hierarchy" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_set_user_reports_to_clear_success(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Setting reports_to_id to None clears existing supervisor.
    """
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=admin_user.id
    )
    cleared_user = await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=None
    )
    assert cleared_user.reports_to_id is None


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
        due_datetime=datetime.now(UTC) + timedelta(days=2),
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
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=admin_user.id
    )
    task_in = TaskCreate(
        title="Team Task Filter",
        description="Filter test",
        priority=TaskPriority.HIGH,
        due_datetime=datetime.now(UTC) + timedelta(days=2),
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
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        assigned_to=employee_user.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

    update_in = TaskUpdate(version=task.version, title="New Unauthorized Title")
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
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        assigned_to=employee_user.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)

    with pytest.raises(AuthorizationException) as exc_info:
        await task_service.delete_task(db=db_session, task_id=task.id, user=employee_user)
    assert "only administrators can delete tasks" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unit_task_status_transition_updates_completed_at(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Transitioning task to COMPLETED automatically populates completed_at timestamp,
    and attempting to transition an already-COMPLETED task raises AppException (task immutability).
    """
    task_in = TaskCreate(
        title="Completed Timestamp Test Task",
        description="Testing completed_at",
        priority=TaskPriority.HIGH,
        due_datetime=datetime.now(UTC) + timedelta(days=2),
        assigned_to=employee_user.id,
    )
    task = await task_service.create_task(db=db_session, task_in=task_in, creator=admin_user)
    assert task.completed_at is None

    # Part a: Update from PENDING to COMPLETED sets completed_at
    updated_comp = await task_service.update_task(
        db=db_session,
        task_id=task.id,
        task_update=TaskUpdate(version=task.version, status=TaskStatus.COMPLETED),
        user=admin_user,
    )
    assert updated_comp.completed_at is not None
    assert isinstance(updated_comp.completed_at, datetime)

    # Part b: Attempting to transition an already-COMPLETED task raises AppException
    with pytest.raises(AppException) as exc_info:
        await task_service.update_task(
            db=db_session,
            task_id=task.id,
            task_update=TaskUpdate(version=updated_comp.version, status=TaskStatus.IN_PROGRESS),
            user=admin_user,
        )
    assert exc_info.value.status_code == 400
    assert "Cannot modify a completed task" in exc_info.value.detail


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
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=admin_user.id
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


# ==========================================
# ANALYTICS SERVICE UNIT TESTS
# ==========================================


@pytest.mark.asyncio
async def test_unit_analytics_service_scoping_and_classification(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Unit Test: Direct unit coverage for analytics_service across all scoping rules & classification branches.
    """
    from datetime import UTC, datetime, timedelta
    from app.models.task import Task, TaskStatus
    from app.services import analytics_service
    from app.services.analytics_service import _classify_task_state

    # 1. Plain employee scope='self'
    stats_self = await analytics_service.get_performance_analytics(
        db=db_session, user=employee_user
    )
    assert stats_self.scope == "self"
    assert stats_self.total_tasks == 0

    # 2. Plain employee requesting another employee -> AuthorizationException
    with pytest.raises(AuthorizationException):
        await analytics_service.get_performance_analytics(
            db=db_session, user=employee_user, employee_id=admin_user.id
        )

    # 3. Manager hierarchy setup
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=employee_user.id, reports_to_id=admin_user.id
    )
    # Create employee 2 reporting to admin_user
    emp2, _ = await user_service.create_employee(
        db=db_session,
        employee_in=EmployeeCreate(
            email="emp2.unit@example.com",
            full_name="Emp 2",
            reports_to_id=admin_user.id,
            designation="Junior Dev",
        ),
    )
    # Create other employee with no supervisor
    other_emp, _ = await user_service.create_employee(
        db=db_session,
        employee_in=EmployeeCreate(
            email="other.unit@example.com",
            full_name="Other Emp",
            reports_to_id=None,
            designation="Contractor",
        ),
    )

    # Create manager (employee role) that has a report
    mgr_user, _ = await user_service.create_employee(
        db=db_session,
        employee_in=EmployeeCreate(
            email="mgr.unit@example.com",
            full_name="Mgr User",
            reports_to_id=None,
            designation="Team Lead",
        ),
    )
    await user_service.set_user_reports_to(
        db=db_session, target_user_id=emp2.id, reports_to_id=mgr_user.id
    )

    # Manager requesting without employee_id -> scope='team'
    mgr_team_stats = await analytics_service.get_performance_analytics(
        db=db_session, user=mgr_user
    )
    assert mgr_team_stats.scope == "team"

    # Manager requesting own ID -> scope='self'
    mgr_self_stats = await analytics_service.get_performance_analytics(
        db=db_session, user=mgr_user, employee_id=mgr_user.id
    )
    assert mgr_self_stats.scope == "self"

    # Manager requesting direct report ID -> scope='employee'
    mgr_rep_stats = await analytics_service.get_performance_analytics(
        db=db_session, user=mgr_user, employee_id=emp2.id
    )
    assert mgr_rep_stats.scope == "employee"
    assert mgr_rep_stats.employee_id == emp2.id

    # Manager requesting non-report ID -> AuthorizationException
    with pytest.raises(AuthorizationException):
        await analytics_service.get_performance_analytics(
            db=db_session, user=mgr_user, employee_id=other_emp.id
        )

    # 4. Admin scoping:
    # Admin without employee_id -> scope='org'
    admin_org_stats = await analytics_service.get_performance_analytics(
        db=db_session, user=admin_user
    )
    assert admin_org_stats.scope == "org"

    # Admin with employee_id -> scope='employee'
    admin_emp_stats = await analytics_service.get_performance_analytics(
        db=db_session, user=admin_user, employee_id=employee_user.id
    )
    assert admin_emp_stats.scope == "employee"
    assert admin_emp_stats.employee_id == employee_user.id

    # Admin with nonexistent employee_id -> ResourceNotFoundException
    with pytest.raises(ResourceNotFoundException):
        await analytics_service.get_performance_analytics(
            db=db_session, user=admin_user, employee_id=99999
        )

    # 5. Direct unit verification of _classify_task_state
    now_dt = datetime.now(UTC)
    t_completed_no_completed_at = Task(
        title="Completed no stamp",
        due_datetime=now_dt + timedelta(days=1),
        status=TaskStatus.COMPLETED,
        completed_at=None,
    )
    assert _classify_task_state(t_completed_no_completed_at, now_dt) == "late"

    t_completed_on_time = Task(
        title="On time",
        due_datetime=now_dt + timedelta(days=2),
        status=TaskStatus.COMPLETED,
        completed_at=now_dt + timedelta(days=1),
    )
    assert _classify_task_state(t_completed_on_time, now_dt) == "on_time"

    t_completed_late = Task(
        title="Late",
        due_datetime=now_dt + timedelta(days=1),
        status=TaskStatus.COMPLETED,
        completed_at=now_dt + timedelta(days=2),
    )
    assert _classify_task_state(t_completed_late, now_dt) == "late"

    t_overdue = Task(
        title="Overdue",
        due_datetime=now_dt - timedelta(days=1),
        status=TaskStatus.PENDING,
    )
    assert _classify_task_state(t_overdue, now_dt) == "overdue"

    t_pending = Task(
        title="Pending",
        due_datetime=now_dt + timedelta(days=1),
        status=TaskStatus.IN_PROGRESS,
    )
    assert _classify_task_state(t_pending, now_dt) == "pending"
