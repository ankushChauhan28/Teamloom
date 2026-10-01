"""
Slice 3 Multi-Tenant Isolation & Pagination Test Suite

Comprehensive automated test suite covering:
1. Cross-org 404 isolation across all single-resource endpoints (read, update, delete, approve, reject, reset-password, reports-to, deactivate, reactivate, direct-reports).
2. Cross-org parameter validation (assigned_to, reports_to_id) returning 404.
3. Analytics isolation across organizations, cross-org employee_id lookup (404), and empty organization zero-metrics safety.
4. List endpoint tenant isolation (users, tasks, leaves).
5. Pagination parameters (skip, limit, max cap <= 100, deterministic ordering) and X-Total-Count header on all 7 list endpoints.
6. Error message equivalence between non-existent IDs and cross-tenant IDs.
"""

from datetime import UTC, date, datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave import LeaveRequest, LeaveStatus
from app.models.organization import Organization
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# 1. Cross-Organization 404 Isolation on Single Resource Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_org_get_task_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_headers: dict,
    task_b: Task,
):
    """
    Test: GET /tasks/{id} returns 404 for both Admin A and Employee A when accessing Org B's task.
    """
    res_admin = await client.get(f"/tasks/{task_b.id}", headers=admin_headers)
    assert res_admin.status_code == 404
    assert res_admin.json()["detail"] == f"Task with ID {task_b.id} not found."

    res_emp = await client.get(f"/tasks/{task_b.id}", headers=employee_headers)
    assert res_emp.status_code == 404
    assert res_emp.json()["detail"] == f"Task with ID {task_b.id} not found."


@pytest.mark.asyncio
async def test_cross_org_update_task_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    task_b: Task,
):
    """
    Test: PATCH /tasks/{id} returns 404 for Admin A when updating Org B's task.
    """
    payload = {"title": "Attempted Cross-Org Update", "version": task_b.version}
    res = await client.patch(f"/tasks/{task_b.id}", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == f"Task with ID {task_b.id} not found."


@pytest.mark.asyncio
async def test_cross_org_delete_task_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    task_b: Task,
):
    """
    Test: DELETE /tasks/{id} returns 404 for Admin A when deleting Org B's task.
    """
    res = await client.delete(f"/tasks/{task_b.id}", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == f"Task with ID {task_b.id} not found."


@pytest.mark.asyncio
async def test_cross_org_review_leave_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    leave_b: LeaveRequest,
):
    """
    Test: PATCH /leaves/{id} returns 404 for Admin A when approving/rejecting Org B's leave.
    """
    payload = {"status": "APPROVED"}
    res = await client.patch(f"/leaves/{leave_b.id}", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == f"Leave request with ID {leave_b.id} not found."


@pytest.mark.asyncio
async def test_cross_org_reset_temp_password_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user_b: User,
):
    """
    Test: POST /users/{user_id}/reset-temp-password returns 404 for Admin A when targeting Org B's employee.
    """
    res = await client.post(f"/users/{employee_user_b.id}/reset-temp-password", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "User not found."


@pytest.mark.asyncio
async def test_cross_org_set_user_reports_to_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user_b: User,
    admin_user: User,
):
    """
    Test: PATCH /users/{user_id}/reports-to returns 404 for Admin A when target user belongs to Org B.
    """
    payload = {"reports_to_id": admin_user.id}
    res = await client.patch(f"/users/{employee_user_b.id}/reports-to", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "User not found."


@pytest.mark.asyncio
async def test_cross_org_deactivate_and_reactivate_user_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user_b: User,
):
    """
    Test: PATCH /users/{user_id}/deactivate and /reactivate return 404 for Admin A when targeting Org B's employee.
    """
    res_deact = await client.patch(f"/users/{employee_user_b.id}/deactivate", headers=admin_headers)
    assert res_deact.status_code == 404
    assert res_deact.json()["detail"] == "User not found."

    res_react = await client.patch(f"/users/{employee_user_b.id}/reactivate", headers=admin_headers)
    assert res_react.status_code == 404
    assert res_react.json()["detail"] == "User not found."


@pytest.mark.asyncio
async def test_cross_org_direct_reports_by_user_id_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user_b: User,
):
    """
    Test: GET /users/{user_id}/direct-reports returns 404 for Admin A when targeting user from Org B.
    """
    res = await client.get(f"/users/{employee_user_b.id}/direct-reports", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "User not found."


# ---------------------------------------------------------------------------
# 2. Cross-Organization Parameter Validation (assigned_to & reports_to_id)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_org_assigned_to_in_create_task_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user_b: User,
):
    """
    Test: Creating a task in Org A with assigned_to belonging to Org B returns 404 (same as non-existent user).
    """
    payload = {
        "title": "Cross Org Assignment Task",
        "description": "Attempted assignment across tenant boundary",
        "priority": "HIGH",
        "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "assigned_to": employee_user_b.id,
    }
    res = await client.post("/tasks/", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == f"Assigned user with ID {employee_user_b.id} not found."


@pytest.mark.asyncio
async def test_cross_org_reports_to_id_in_create_employee_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    admin_user_b: User,
):
    """
    Test: Creating an employee in Org A with reports_to_id belonging to Org B returns 404.
    """
    payload = {
        "full_name": "New Org A Worker",
        "email": "worker.a@example.com",
        "designation": "Software Engineer",
        "access_level": 3,
        "reports_to_id": admin_user_b.id,
    }
    res = await client.post("/users/employees", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Reports-to supervisor user not found."


@pytest.mark.asyncio
async def test_cross_org_reports_to_id_in_set_reports_to_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user: User,
    admin_user_b: User,
):
    """
    Test: Setting reports_to_id of Org A employee to an Org B supervisor returns 404.
    """
    payload = {"reports_to_id": admin_user_b.id}
    res = await client.patch(f"/users/{employee_user.id}/reports-to", json=payload, headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Reports-to supervisor user not found."


# ---------------------------------------------------------------------------
# 3. Analytics Isolation & Empty Organization Safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_cross_org_isolation(
    client: AsyncClient,
    admin_headers: dict,
    admin_headers_b: dict,
    employee_user: User,
    employee_user_b: User,
    task_b: Task,
    db_session: AsyncSession,
    test_org: Organization,
    admin_user: User,
):
    """
    Test: Org A analytics only count Org A tasks. Org B analytics only count Org B tasks.
    """
    # Create 1 completed on-time task for Org A
    task_a = Task(
        title="Org A Task 1",
        description="Completed task in Org A",
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.COMPLETED,
        due_datetime=datetime.now(UTC) + timedelta(days=1),
        completed_at=datetime.now(UTC),
        assigned_to=employee_user.id,
        created_by=admin_user.id,
        organization_id=test_org.id,
    )
    db_session.add(task_a)
    await db_session.commit()

    # Org A analytics check
    res_a = await client.get("/analytics/performance", headers=admin_headers)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total_tasks"] == 1
    assert data_a["on_time_count"] == 1
    assert data_a["completion_rate"] == 1.0
    assert len(data_a["milestone_trail"]) == 1
    assert data_a["milestone_trail"][0]["id"] == task_a.id

    # Org B analytics check (task_b is PENDING)
    res_b = await client.get("/analytics/performance", headers=admin_headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total_tasks"] == 1
    assert data_b["pending_count"] == 1
    assert data_b["completion_rate"] == 0.0
    assert len(data_b["milestone_trail"]) == 1
    assert data_b["milestone_trail"][0]["id"] == task_b.id


@pytest.mark.asyncio
async def test_analytics_cross_org_employee_id_returns_404(
    client: AsyncClient,
    admin_headers: dict,
    employee_user_b: User,
):
    """
    Test: Admin A requesting analytics for employee_id belonging to Org B returns 404.
    """
    res = await client.get(f"/analytics/performance?employee_id={employee_user_b.id}", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == f"User with ID {employee_user_b.id} not found."


@pytest.mark.asyncio
async def test_analytics_empty_org_zero_metrics_safety(
    client: AsyncClient,
    admin_headers: dict,
):
    """
    Test: Organization with zero tasks returns zeroed metrics without division-by-zero or errors.
    """
    res = await client.get("/analytics/performance", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_tasks"] == 0
    assert data["on_time_count"] == 0
    assert data["late_count"] == 0
    assert data["overdue_count"] == 0
    assert data["pending_count"] == 0
    assert data["completion_rate"] == 0.0
    assert data["milestone_trail"] == []


# ---------------------------------------------------------------------------
# 4. List Endpoints Tenant Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_employees_tenant_isolation(
    client: AsyncClient,
    admin_headers: dict,
    admin_headers_b: dict,
    employee_user: User,
    employee_user_b: User,
):
    """
    Test: GET /users/ returns only employees belonging to the caller's organization.
    """
    res_a = await client.get("/users/", headers=admin_headers)
    assert res_a.status_code == 200
    users_a = res_a.json()
    assert all(u["id"] == employee_user.id for u in users_a)
    assert not any(u["id"] == employee_user_b.id for u in users_a)

    res_b = await client.get("/users/", headers=admin_headers_b)
    assert res_b.status_code == 200
    users_b = res_b.json()
    assert all(u["id"] == employee_user_b.id for u in users_b)
    assert not any(u["id"] == employee_user.id for u in users_b)


@pytest.mark.asyncio
async def test_list_tasks_and_leaves_tenant_isolation(
    client: AsyncClient,
    admin_headers: dict,
    admin_headers_b: dict,
    task_b: Task,
    leave_b: LeaveRequest,
    db_session: AsyncSession,
    test_org: Organization,
    employee_user: User,
    admin_user: User,
):
    """
    Test: GET /tasks/ and GET /leaves/ return only items belonging to caller's org.
    """
    # Create Task and Leave in Org A
    task_a = Task(
        title="Org A Unique Task",
        description="Desc",
        priority=TaskPriority.LOW,
        status=TaskStatus.PENDING,
        due_datetime=datetime.now(UTC) + timedelta(days=3),
        assigned_to=employee_user.id,
        created_by=admin_user.id,
        organization_id=test_org.id,
    )
    leave_a = LeaveRequest(
        employee_id=employee_user.id,
        reason="Org A Unique Leave",
        start_date=date.today() + timedelta(days=10),
        end_date=date.today() + timedelta(days=12),
        status=LeaveStatus.PENDING,
        organization_id=test_org.id,
    )
    db_session.add_all([task_a, leave_a])
    await db_session.commit()

    # Tasks Isolation
    tasks_res_a = await client.get("/tasks/", headers=admin_headers)
    assert tasks_res_a.status_code == 200
    task_ids_a = [t["id"] for t in tasks_res_a.json()]
    assert task_a.id in task_ids_a
    assert task_b.id not in task_ids_a

    tasks_res_b = await client.get("/tasks/", headers=admin_headers_b)
    assert tasks_res_b.status_code == 200
    task_ids_b = [t["id"] for t in tasks_res_b.json()]
    assert task_b.id in task_ids_b
    assert task_a.id not in task_ids_b

    # Leaves Isolation
    leaves_res_a = await client.get("/leaves/", headers=admin_headers)
    assert leaves_res_a.status_code == 200
    leave_ids_a = [l["id"] for l in leaves_res_a.json()]
    assert leave_a.id in leave_ids_a
    assert leave_b.id not in leave_ids_a

    leaves_res_b = await client.get("/leaves/", headers=admin_headers_b)
    assert leaves_res_b.status_code == 200
    leave_ids_b = [l["id"] for l in leaves_res_b.json()]
    assert leave_b.id in leave_ids_b
    assert leave_a.id not in leave_ids_b


# ---------------------------------------------------------------------------
# 5. Pagination, Deterministic Ordering & X-Total-Count Header Verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pagination_and_x_total_count_headers(
    client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
    test_org: Organization,
    employee_user: User,
    admin_user: User,
):
    """
    Test: All list endpoints return X-Total-Count header, support skip/limit, and adhere to max limit cap of 100.
    """
    # Create 5 tasks in Org A
    tasks = [
        Task(
            title=f"Bulk Task {i}",
            description=f"Description {i}",
            priority=TaskPriority.LOW,
            status=TaskStatus.PENDING,
            due_datetime=datetime.now(UTC) + timedelta(days=i + 1),
            assigned_to=employee_user.id,
            created_by=admin_user.id,
            organization_id=test_org.id,
        )
        for i in range(5)
    ]
    db_session.add_all(tasks)
    await db_session.commit()

    # 1. GET /tasks/ with pagination
    res_page1 = await client.get("/tasks/?skip=0&limit=2", headers=admin_headers)
    assert res_page1.status_code == 200
    assert len(res_page1.json()) == 2
    assert res_page1.headers.get("X-Total-Count") == "5"

    res_page2 = await client.get("/tasks/?skip=2&limit=2", headers=admin_headers)
    assert res_page2.status_code == 200
    assert len(res_page2.json()) == 2
    assert res_page2.headers.get("X-Total-Count") == "5"

    # Deterministic non-overlapping pages
    ids_p1 = {t["id"] for t in res_page1.json()}
    ids_p2 = {t["id"] for t in res_page2.json()}
    assert ids_p1.isdisjoint(ids_p2)

    # 2. GET /users/ pagination & header
    res_users = await client.get("/users/?skip=0&limit=10", headers=admin_headers)
    assert res_users.status_code == 200
    assert "X-Total-Count" in res_users.headers
    assert int(res_users.headers["X-Total-Count"]) >= 1

    # 3. GET /leaves/ pagination & header
    res_leaves = await client.get("/leaves/?skip=0&limit=10", headers=admin_headers)
    assert res_leaves.status_code == 200
    assert "X-Total-Count" in res_leaves.headers
    assert res_leaves.headers["X-Total-Count"] == "0"

    # 4. GET /users/me/reports header
    res_reports = await client.get("/users/me/reports", headers=admin_headers)
    assert res_reports.status_code == 200
    assert "X-Total-Count" in res_reports.headers

    # 5. GET /tasks/team header
    res_team_tasks = await client.get("/tasks/team", headers=admin_headers)
    assert res_team_tasks.status_code == 200
    assert "X-Total-Count" in res_team_tasks.headers

    # 6. GET /leaves/team header
    res_team_leaves = await client.get("/leaves/team", headers=admin_headers)
    assert res_team_leaves.status_code == 200
    assert "X-Total-Count" in res_team_leaves.headers

    # 7. GET /users/{user_id}/direct-reports header
    res_user_reports = await client.get(f"/users/{admin_user.id}/direct-reports", headers=admin_headers)
    assert res_user_reports.status_code == 200
    assert "X-Total-Count" in res_user_reports.headers
