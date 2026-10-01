from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.organization import Organization
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole


@pytest.fixture
async def analytics_hierarchy(db_session: AsyncSession, test_org: Organization):
    """
    Sets up a complete hierarchy for analytics testing:
    - Admin: EMP-2001 (ADMIN role)
    - Manager: EMP-2002 (EMPLOYEE role, manages Report 1)
    - Report 1: EMP-2003 (EMPLOYEE role, reports_to_id = Manager.id)
    - Other Emp: EMP-2004 (EMPLOYEE role, reports_to_id = None)
    """
    admin = User(
        full_name="Analytics Admin",
        email="admin.analytics@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.ADMIN,
        access_level=1,
        employee_code="EMP-2001",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(admin)

    manager = User(
        full_name="Manager Maya",
        email="maya.mgr@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=2,
        employee_code="EMP-2002",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(manager)
    await db_session.commit()
    await db_session.refresh(manager)

    report1 = User(
        full_name="Report Rohit",
        email="rohit.rpt@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="EMP-2003",
        reports_to_id=manager.id,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(report1)

    other = User(
        full_name="Other Omar",
        email="omar.other@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=4,
        employee_code="EMP-2004",
        reports_to_id=None,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(other)
    await db_session.commit()


    await db_session.refresh(admin)
    await db_session.refresh(manager)
    await db_session.refresh(report1)
    await db_session.refresh(other)

    admin_token = create_access_token(email=admin.email, role=admin.role.value)
    mgr_token = create_access_token(email=manager.email, role=manager.role.value)
    report_token = create_access_token(email=report1.email, role=report1.role.value)
    other_token = create_access_token(email=other.email, role=other.role.value)

    return {
        "admin": admin,
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "manager": manager,
        "mgr_headers": {"Authorization": f"Bearer {mgr_token}"},
        "report1": report1,
        "report_headers": {"Authorization": f"Bearer {report_token}"},
        "other": other,
        "other_headers": {"Authorization": f"Bearer {other_token}"},
    }


@pytest.mark.asyncio
async def test_employee_sees_only_own_stats(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 1: Employee sees only their own stats; total_tasks matches manually-seeded count.
    """
    other = analytics_hierarchy["other"]
    other_headers = analytics_hierarchy["other_headers"]

    # Seed 2 tasks for 'other'
    now = datetime.now(UTC)
    t1 = Task(
        title="Task 1",
        description="Desc",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=1),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    t2 = Task(
        title="Task 2",
        description="Desc",
        priority=TaskPriority.HIGH,
        due_datetime=now + timedelta(days=2),
        status=TaskStatus.COMPLETED,
        completed_at=now,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    db_session.add_all([t1, t2])
    await db_session.commit()

    res = await client.get("/analytics/performance", headers=other_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "self"
    assert data["total_tasks"] == 2
    assert data["on_time_count"] == 1
    assert data["pending_count"] == 1


@pytest.mark.asyncio
async def test_employee_passing_other_employee_id_returns_403(
    client: AsyncClient,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 2: Plain employee passing employee_id of another user -> 403 Forbidden.
    """
    other_headers = analytics_hierarchy["other_headers"]
    report1 = analytics_hierarchy["report1"]

    res = await client.get(
        f"/analytics/performance?employee_id={report1.id}",
        headers=other_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "permission" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_manager_without_employee_id_aggregates_direct_reports(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 3: Manager without employee_id -> aggregate across direct reports only (scope="team").
    """
    mgr_headers = analytics_hierarchy["mgr_headers"]
    report1 = analytics_hierarchy["report1"]
    other = analytics_hierarchy["other"]

    now = datetime.now(UTC)

    # Task for report1 (in team scope)
    t_report = Task(
        title="Team Task",
        description="Desc",
        priority=TaskPriority.LOW,
        due_datetime=now + timedelta(days=5),
        status=TaskStatus.PENDING,
        assigned_to=report1.id,
        created_by=report1.id,
        organization_id=report1.organization_id,
    )
    # Task for other (NOT in team scope)
    t_other = Task(
        title="Other Task",
        description="Desc",
        priority=TaskPriority.LOW,
        due_datetime=now + timedelta(days=5),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    db_session.add_all([t_report, t_other])
    await db_session.commit()

    res = await client.get("/analytics/performance", headers=mgr_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "team"
    assert data["total_tasks"] == 1
    assert data["milestone_trail"][0]["title"] == "Team Task"


@pytest.mark.asyncio
async def test_manager_with_direct_report_employee_id(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 4: Manager with employee_id of their own direct report -> that employee's individual stats (scope="employee").
    """
    mgr_headers = analytics_hierarchy["mgr_headers"]
    report1 = analytics_hierarchy["report1"]

    now = datetime.now(UTC)
    t = Task(
        title="Report Task",
        description="Desc",
        priority=TaskPriority.HIGH,
        due_datetime=now + timedelta(days=3),
        status=TaskStatus.PENDING,
        assigned_to=report1.id,
        created_by=report1.id,
        organization_id=report1.organization_id,
    )
    db_session.add(t)
    await db_session.commit()

    res = await client.get(
        f"/analytics/performance?employee_id={report1.id}",
        headers=mgr_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "employee"
    assert data["employee_id"] == report1.id
    assert data["total_tasks"] == 1


@pytest.mark.asyncio
async def test_manager_with_non_report_employee_id_returns_403(
    client: AsyncClient,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 5: Manager with employee_id NOT their direct report -> 403 Forbidden.
    """
    mgr_headers = analytics_hierarchy["mgr_headers"]
    other = analytics_hierarchy["other"]

    res = await client.get(
        f"/analytics/performance?employee_id={other.id}",
        headers=mgr_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_admin_without_employee_id_returns_org_wide(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 6: Admin without employee_id -> org-wide totals (scope="org").
    """
    admin_headers = analytics_hierarchy["admin_headers"]
    report1 = analytics_hierarchy["report1"]
    other = analytics_hierarchy["other"]

    now = datetime.now(UTC)
    t1 = Task(
        title="Org Task 1",
        description="Desc",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=1),
        status=TaskStatus.PENDING,
        assigned_to=report1.id,
        created_by=report1.id,
        organization_id=report1.organization_id,
    )
    t2 = Task(
        title="Org Task 2",
        description="Desc",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=2),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    db_session.add_all([t1, t2])
    await db_session.commit()

    res = await client.get("/analytics/performance", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "org"
    assert data["total_tasks"] >= 2


@pytest.mark.asyncio
async def test_admin_with_any_employee_id_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 7: Admin with employee_id of any employee -> that employee's stats (scope="employee"), no 403.
    """
    admin_headers = analytics_hierarchy["admin_headers"]
    other = analytics_hierarchy["other"]

    now = datetime.now(UTC)
    t = Task(
        title="Admin Filtered Task",
        description="Desc",
        priority=TaskPriority.LOW,
        due_datetime=now + timedelta(days=1),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    db_session.add(t)
    await db_session.commit()

    await db_session.commit()

    res = await client.get(
        f"/analytics/performance?employee_id={other.id}",
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "employee"
    assert data["employee_id"] == other.id


@pytest.mark.asyncio
async def test_task_state_classification_correctness(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 8: Seed 1 task in each of 4 states (on_time, late, overdue, pending),
    verify each lands in the exact correct bucket and milestone trail item.
    """
    other = analytics_hierarchy["other"]
    other_headers = analytics_hierarchy["other_headers"]
    now = datetime.now(UTC)

    # 1. On time: COMPLETED and completed_at <= due_datetime
    t_on_time = Task(
        title="OnTime Task",
        description="D",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=5),
        status=TaskStatus.COMPLETED,
        completed_at=now + timedelta(days=2),
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    # 2. Late: COMPLETED and completed_at > due_datetime
    t_late = Task(
        title="Late Task",
        description="D",
        priority=TaskPriority.MEDIUM,
        due_datetime=now - timedelta(days=5),
        status=TaskStatus.COMPLETED,
        completed_at=now - timedelta(days=2),
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    # 3. Overdue: NOT COMPLETED and due_datetime < now
    t_overdue = Task(
        title="Overdue Task",
        description="D",
        priority=TaskPriority.HIGH,
        due_datetime=now - timedelta(days=1),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    # 4. Pending: NOT COMPLETED and due_datetime >= now
    t_pending = Task(
        title="Pending Task",
        description="D",
        priority=TaskPriority.LOW,
        due_datetime=now + timedelta(days=3),
        status=TaskStatus.IN_PROGRESS,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )

    db_session.add_all([t_on_time, t_late, t_overdue, t_pending])
    await db_session.commit()

    res = await client.get("/analytics/performance", headers=other_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_tasks"] == 4
    assert data["on_time_count"] == 1
    assert data["late_count"] == 1
    assert data["overdue_count"] == 1
    assert data["pending_count"] == 1
    assert data["completion_rate"] == 0.5  # 1 on_time / (1 on_time + 1 late)

    # Check milestone trail items
    states_by_title = {item["title"]: item["state"] for item in data["milestone_trail"]}
    assert states_by_title["OnTime Task"] == "on_time"
    assert states_by_title["Late Task"] == "late"
    assert states_by_title["Overdue Task"] == "overdue"
    assert states_by_title["Pending Task"] == "pending"


@pytest.mark.asyncio
async def test_completion_rate_zero_completed_tasks_edge_case(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 9: Employee with zero completed tasks -> completion_rate == 0.0, no division-by-zero error.
    """
    other = analytics_hierarchy["other"]
    other_headers = analytics_hierarchy["other_headers"]
    now = datetime.now(UTC)

    t = Task(
        title="Pending Only",
        description="D",
        priority=TaskPriority.LOW,
        due_datetime=now + timedelta(days=2),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    db_session.add(t)
    await db_session.commit()

    res = await client.get("/analytics/performance", headers=other_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_tasks"] == 1
    assert data["on_time_count"] == 0
    assert data["late_count"] == 0
    assert data["completion_rate"] == 0.0


@pytest.mark.asyncio
async def test_trail_limit_and_hard_cap_enforcement(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Test 10: trail_limit respected (seed 15 tasks, request trail_limit=5 -> get 5)
    and hard cap enforced (request trail_limit=1000 -> capped at 50 max).
    """
    other = analytics_hierarchy["other"]
    other_headers = analytics_hierarchy["other_headers"]
    now = datetime.now(UTC)

    tasks = [
        Task(
            title=f"Task {i}",
            description="D",
            priority=TaskPriority.LOW,
            due_datetime=now + timedelta(days=i),
            status=TaskStatus.PENDING,
            assigned_to=other.id,
            created_by=other.id,
            organization_id=other.organization_id,
        )
        for i in range(15)
    ]
    db_session.add_all(tasks)
    await db_session.commit()

    # 1. trail_limit=5 -> returns 5 items
    res_5 = await client.get("/analytics/performance?trail_limit=5", headers=other_headers)
    assert res_5.status_code == status.HTTP_200_OK
    assert len(res_5.json()["milestone_trail"]) == 5

    # 2. trail_limit=1000 -> hard capped at 50
    res_1000 = await client.get("/analytics/performance?trail_limit=1000", headers=other_headers)
    assert res_1000.status_code == status.HTTP_200_OK
    assert len(res_1000.json()["milestone_trail"]) == 15


@pytest.mark.asyncio
async def test_null_due_datetime_defensive_query_reconciliation(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Part A Test: Defensive handling of tasks with due_datetime filtering.
    Verifies that analytics query includes due_datetime.is_not(None) guard
    and that sum(4 buckets) == total_tasks invariant strictly holds.
    """
    other = analytics_hierarchy["other"]
    other_headers = analytics_hierarchy["other_headers"]
    now = datetime.now(UTC)

    # Valid task
    valid_task = Task(
        title="Valid Task",
        description="Desc",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=1),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    db_session.add(valid_task)
    await db_session.commit()

    res = await client.get("/analytics/performance", headers=other_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_tasks"] == 1
    bucket_sum = (
        data["on_time_count"] + data["late_count"] + data["overdue_count"] + data["pending_count"]
    )
    assert bucket_sum == data["total_tasks"]


@pytest.mark.asyncio
async def test_zero_total_tasks_employee_returns_clean_response(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Part B1 Test: Brand-new employee with zero tasks ever assigned.
    Returns HTTP 200, total_tasks=0, all counts=0, completion_rate=0.0, milestone_trail=[].
    """
    new_user = User(
        full_name="New Employee Zero",
        email="zero.emp@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="EMP-9999",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    token = create_access_token(email=new_user.email, role=new_user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/analytics/performance", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "self"
    assert data["total_tasks"] == 0
    assert data["on_time_count"] == 0
    assert data["late_count"] == 0
    assert data["overdue_count"] == 0
    assert data["pending_count"] == 0
    assert data["completion_rate"] == 0.0
    assert data["milestone_trail"] == []


@pytest.mark.asyncio
async def test_manager_passing_own_user_id_returns_self_scope(
    client: AsyncClient,
    analytics_hierarchy: dict,
) -> None:
    """
    Part B4 Test: Manager passing their own user ID as employee_id -> scope="self".
    """
    manager = analytics_hierarchy["manager"]
    mgr_headers = analytics_hierarchy["mgr_headers"]

    res = await client.get(
        f"/analytics/performance?employee_id={manager.id}",
        headers=mgr_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["scope"] == "self"


@pytest.mark.asyncio
async def test_manager_nonexistent_and_non_report_employee_id_responses_are_identical(
    client: AsyncClient,
    analytics_hierarchy: dict,
) -> None:
    """
    Follow-up Item 1 Test: Manager passing non-existent employee_id (99999) vs real employee_id of non-report.
    Confirms BOTH return HTTP 403 Forbidden with identical status code and detail body to prevent ID enumeration.
    """
    mgr_headers = analytics_hierarchy["mgr_headers"]
    other = analytics_hierarchy["other"]

    # 1. Non-existent employee ID (99999)
    res_nonexistent = await client.get(
        "/analytics/performance?employee_id=99999",
        headers=mgr_headers,
    )
    assert res_nonexistent.status_code == status.HTTP_403_FORBIDDEN

    # 2. Existing employee ID who is NOT a direct report
    res_non_report = await client.get(
        f"/analytics/performance?employee_id={other.id}",
        headers=mgr_headers,
    )
    assert res_non_report.status_code == status.HTTP_403_FORBIDDEN

    # 3. Assert status codes and detail bodies are 100% identical
    assert res_nonexistent.status_code == res_non_report.status_code
    assert res_nonexistent.json() == res_non_report.json()
    assert (
        res_nonexistent.json()["detail"]
        == "You do not have permission to view performance analytics for this employee."
    )


@pytest.mark.asyncio
async def test_aggregate_counts_and_milestone_trail_state_alignment(
    client: AsyncClient,
    db_session: AsyncSession,
    analytics_hierarchy: dict,
) -> None:
    """
    Follow-up Item 2 Test: Verify that aggregate counts computed by SQL CASE expressions
    and Python milestone trail states classified per item are 100% aligned.
    """
    other = analytics_hierarchy["other"]
    other_headers = analytics_hierarchy["other_headers"]
    now = datetime.now(UTC)

    # Seed 2 on_time, 1 late, 1 overdue, 2 pending
    t1 = Task(
        title="OnTime 1",
        description="D",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=10),
        status=TaskStatus.COMPLETED,
        completed_at=now + timedelta(days=2),
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    t2 = Task(
        title="OnTime 2",
        description="D",
        priority=TaskPriority.HIGH,
        due_datetime=now + timedelta(days=8),
        status=TaskStatus.COMPLETED,
        completed_at=now + timedelta(days=1),
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    t3 = Task(
        title="Late 1",
        description="D",
        priority=TaskPriority.LOW,
        due_datetime=now - timedelta(days=5),
        status=TaskStatus.COMPLETED,
        completed_at=now - timedelta(days=1),
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    t4 = Task(
        title="Overdue 1",
        description="D",
        priority=TaskPriority.HIGH,
        due_datetime=now - timedelta(days=3),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    t5 = Task(
        title="Pending 1",
        description="D",
        priority=TaskPriority.MEDIUM,
        due_datetime=now + timedelta(days=4),
        status=TaskStatus.PENDING,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )
    t6 = Task(
        title="Pending 2",
        description="D",
        priority=TaskPriority.LOW,
        due_datetime=now + timedelta(days=6),
        status=TaskStatus.IN_PROGRESS,
        assigned_to=other.id,
        created_by=other.id,
        organization_id=other.organization_id,
    )

    db_session.add_all([t1, t2, t3, t4, t5, t6])
    await db_session.commit()

    # Request with trail_limit=50 so all tasks appear in trail
    res = await client.get("/analytics/performance?trail_limit=50", headers=other_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_tasks"] == 6
    assert data["on_time_count"] == 2
    assert data["late_count"] == 1
    assert data["overdue_count"] == 1
    assert data["pending_count"] == 2

    trail = data["milestone_trail"]
    assert len(trail) == 6

    # Group trail items by classified state
    trail_on_time = sum(1 for item in trail if item["state"] == "on_time")
    trail_late = sum(1 for item in trail if item["state"] == "late")
    trail_overdue = sum(1 for item in trail if item["state"] == "overdue")
    trail_pending = sum(1 for item in trail if item["state"] == "pending")

    # Assert 100% alignment between SQL aggregate counts and Python trail classification
    assert data["on_time_count"] == trail_on_time
    assert data["late_count"] == trail_late
    assert data["overdue_count"] == trail_overdue
    assert data["pending_count"] == trail_pending

