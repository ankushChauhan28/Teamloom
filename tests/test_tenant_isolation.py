"""
API-Level Tenant Isolation Test Suite (Slice 5, Depth A)

Comprehensive black-box HTTP tests proving that an authenticated user of Organization A
can NEVER read, modify, delete, or discover data belonging to Organization B through
any route in the application.

Tested Attack Vectors:
1. By-ID Access: GET, PATCH, DELETE of Org B's task, leave, and user return 404 (same
   response structure as non-existent IDs, preventing resource enumeration).
2. List Scoping: List endpoints (tasks, team tasks, leaves, team leaves, users, direct reports)
   and X-Total-Count strictly reflect Org A data, ignoring Org B data and soft-deleted tasks.
3. Write Attacks: Cross-tenant task assignment, reports_to assignment, deactivation reassignments,
   and leave reviews are rejected with 404, keeping Org B state untouched in the database.
4. Soft-Deleted Isolation: Soft-deleted tasks of Org B are completely inaccessible and invisible
   from Org A across single-fetch, list, update, and delete endpoints.
5. Analytics Scoping: Organization, team, and employee scopes strictly aggregate Org A data.
   Cross-org employee_id queries return 404/403.
6. Parameter & Body Injection: Passing organization_id in query parameters or request body cannot
   override the caller's tenant context.
7. Token & Auth Boundaries: Org A tokens cannot access Org B resources. Deactivated or revoked
   tokens are rejected.
"""

from datetime import UTC, datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave import LeaveRequest, LeaveStatus
from app.models.task import Task
from app.models.user import User
from tests.fixtures_tenant_isolation import TenantIsolationSetup, isolation_setup  # noqa: F401


# ===========================================================================
# 1. By-ID Access Attacks (Tasks, Soft-Deleted Tasks, Leaves, Users)
# ===========================================================================

@pytest.mark.asyncio
async def test_cross_org_get_task_by_id_returns_404_anti_enumeration(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /tasks/{id} returns 404 for Admin A, Supervisor A, and Employee A when targeting Org B's task.
    Response detail must match non-existent task error to prevent enumeration.
    """
    task_b_id = isolation_setup.org_b.task.id
    expected_msg = f"Task with ID {task_b_id} not found."

    for headers, role_name in [
        (isolation_setup.org_a.admin_headers, "Admin A"),
        (isolation_setup.org_a.supervisor_headers, "Supervisor A"),
        (isolation_setup.org_a.employee_headers, "Employee A"),
    ]:
        res = await client.get(f"/tasks/{task_b_id}", headers=headers)
        assert res.status_code == 404, f"{role_name} expected 404, got {res.status_code}"
        assert res.json()["detail"] == expected_msg


@pytest.mark.asyncio
async def test_cross_org_patch_task_by_id_returns_404(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    PATCH /tasks/{id} returns 404 for Admin A, Supervisor A, and Employee A when targeting Org B's task.
    Org B task remains completely unmodified in the database.
    """
    task_b = isolation_setup.org_b.task
    original_title = task_b.title
    original_version = task_b.version

    for headers, role_name in [
        (isolation_setup.org_a.admin_headers, "Admin A"),
        (isolation_setup.org_a.supervisor_headers, "Supervisor A"),
        (isolation_setup.org_a.employee_headers, "Employee A"),
    ]:
        payload = {"title": "Malicious Title Change", "version": original_version}
        res = await client.patch(f"/tasks/{task_b.id}", json=payload, headers=headers)
        assert res.status_code == 404, f"{role_name} expected 404, got {res.status_code}"
        assert res.json()["detail"] == f"Task with ID {task_b.id} not found."

    # Verify DB integrity: Org B task was NOT modified
    await db_session.refresh(task_b)
    assert task_b.title == original_title
    assert task_b.version == original_version


@pytest.mark.asyncio
async def test_cross_org_delete_task_by_id_returns_404_and_preserves_task(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    DELETE /tasks/{id}:
    - Admin A receives 404 when attempting to delete Org B's task.
    - Supervisor A and Employee A receive 403 (Tier 1 authorization guard).
    Org B task remains un-deleted in the database.
    """
    task_b = isolation_setup.org_b.task

    # Admin A attempt -> 404
    res_admin = await client.delete(f"/tasks/{task_b.id}", headers=isolation_setup.org_a.admin_headers)
    assert res_admin.status_code == 404
    assert res_admin.json()["detail"] == f"Task with ID {task_b.id} not found."

    # Supervisor A attempt -> 403
    res_sup = await client.delete(f"/tasks/{task_b.id}", headers=isolation_setup.org_a.supervisor_headers)
    assert res_sup.status_code == 403

    # Employee A attempt -> 403
    res_emp = await client.delete(f"/tasks/{task_b.id}", headers=isolation_setup.org_a.employee_headers)
    assert res_emp.status_code == 403

    # Verify DB: Org B task is not soft-deleted
    await db_session.refresh(task_b)
    assert task_b.is_deleted is False
    assert task_b.deleted_at is None
    assert task_b.deleted_by is None


@pytest.mark.asyncio
async def test_cross_org_soft_deleted_task_inaccessible(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    Soft-deleted tasks of Org B are completely inaccessible and invisible to Org A:
    - GET returns 404.
    - PATCH returns 404.
    - DELETE returns 404.
    """
    deleted_task_b = isolation_setup.org_b.soft_deleted_task

    # GET
    for headers in [
        isolation_setup.org_a.admin_headers,
        isolation_setup.org_a.supervisor_headers,
        isolation_setup.org_a.employee_headers,
    ]:
        res_get = await client.get(f"/tasks/{deleted_task_b.id}", headers=headers)
        assert res_get.status_code == 404
        assert res_get.json()["detail"] == f"Task with ID {deleted_task_b.id} not found."

    # PATCH
    res_patch = await client.patch(
        f"/tasks/{deleted_task_b.id}",
        json={"title": "Trying to edit deleted task", "version": deleted_task_b.version},
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_patch.status_code == 404
    assert res_patch.json()["detail"] == f"Task with ID {deleted_task_b.id} not found."

    # DELETE
    res_delete = await client.delete(
        f"/tasks/{deleted_task_b.id}",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_delete.status_code == 404
    assert res_delete.json()["detail"] == f"Task with ID {deleted_task_b.id} not found."


@pytest.mark.asyncio
async def test_cross_org_leave_review_returns_404_and_preserves_leave(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    PATCH /leaves/{id}:
    - Admin A receives 404 when reviewing Org B's leave request.
    - Supervisor A and Employee A receive 403 (Tier 1 authorization guard).
    Org B leave remains PENDING in the database.
    """
    leave_b = isolation_setup.org_b.leave

    # Admin A attempt
    res_admin = await client.patch(
        f"/leaves/{leave_b.id}",
        json={"status": "APPROVED"},
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_admin.status_code == 404
    assert res_admin.json()["detail"] == f"Leave request with ID {leave_b.id} not found."

    # Supervisor A attempt
    res_sup = await client.patch(
        f"/leaves/{leave_b.id}",
        json={"status": "APPROVED"},
        headers=isolation_setup.org_a.supervisor_headers,
    )
    assert res_sup.status_code == 403

    # Employee A attempt
    res_emp = await client.patch(
        f"/leaves/{leave_b.id}",
        json={"status": "APPROVED"},
        headers=isolation_setup.org_a.employee_headers,
    )
    assert res_emp.status_code == 403

    # Verify DB: leave_b status remains PENDING
    await db_session.refresh(leave_b)
    assert leave_b.status == LeaveStatus.PENDING


@pytest.mark.asyncio
async def test_cross_org_user_by_id_endpoints_return_404(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    By-ID user endpoints return 404 when Admin A targets an Org B user:
    - GET /users/{user_id}/direct-reports
    - POST /users/{user_id}/reset-temp-password
    - PATCH /users/{user_id}/reports-to
    - PATCH /users/{user_id}/deactivate
    - PATCH /users/{user_id}/reactivate
    And return 403 for Supervisor A / Employee A.
    """
    emp_b = isolation_setup.org_b.employee
    admin_a = isolation_setup.org_a.admin

    # 1. GET direct reports by ID
    res = await client.get(
        f"/users/{emp_b.id}/direct-reports",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "User not found."

    res_sup = await client.get(
        f"/users/{emp_b.id}/direct-reports",
        headers=isolation_setup.org_a.supervisor_headers,
    )
    assert res_sup.status_code == 403

    # 2. Reset temp password
    res_pwd = await client.post(
        f"/users/{emp_b.id}/reset-temp-password",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_pwd.status_code == 404
    assert res_pwd.json()["detail"] == "User not found."

    # 3. Reports-to modification
    res_rep = await client.patch(
        f"/users/{emp_b.id}/reports-to",
        json={"reports_to_id": admin_a.id},
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_rep.status_code == 404
    assert res_rep.json()["detail"] == "User not found."

    # 4. Deactivate
    res_deact = await client.patch(
        f"/users/{emp_b.id}/deactivate",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_deact.status_code == 404
    assert res_deact.json()["detail"] == "User not found."

    # 5. Reactivate
    res_react = await client.patch(
        f"/users/{emp_b.id}/reactivate",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_react.status_code == 404
    assert res_react.json()["detail"] == "User not found."

    # Verify DB: Org B employee remains completely untouched and active
    await db_session.refresh(emp_b)
    assert emp_b.is_active is True
    assert emp_b.reports_to_id == isolation_setup.org_b.supervisor.id


# ===========================================================================
# 2. List Endpoints & Pagination Header Scoping
# ===========================================================================

@pytest.mark.asyncio
async def test_list_tasks_isolation_and_x_total_count(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /tasks/:
    - Admin A sees only active tasks of Org A (count = 1). Org B tasks and soft-deleted tasks excluded.
    - X-Total-Count header strictly matches Org A active count (1).
    - Supervisor A / Employee A see only own tasks in Org A (count = 1 for Employee A, 0 for Supervisor A).
    """
    # Admin A
    res_admin = await client.get("/tasks/", headers=isolation_setup.org_a.admin_headers)
    assert res_admin.status_code == 200
    tasks_a = res_admin.json()
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == isolation_setup.org_a.task.id
    assert res_admin.headers["X-Total-Count"] == "1"

    # Employee A
    res_emp = await client.get("/tasks/", headers=isolation_setup.org_a.employee_headers)
    assert res_emp.status_code == 200
    emp_tasks = res_emp.json()
    assert len(emp_tasks) == 1
    assert emp_tasks[0]["id"] == isolation_setup.org_a.task.id

    # Supervisor A (no tasks assigned to self)
    res_sup = await client.get("/tasks/", headers=isolation_setup.org_a.supervisor_headers)
    assert res_sup.status_code == 200
    assert len(res_sup.json()) == 0
    assert res_sup.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_team_tasks_isolation(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /tasks/team:
    - Supervisor A sees tasks assigned to Employee A (Org A direct report).
    - Excludes Org B tasks completely.
    - Supervisor B sees tasks assigned to Employee B (Org B direct report).
    """
    res_sup_a = await client.get("/tasks/team", headers=isolation_setup.org_a.supervisor_headers)
    assert res_sup_a.status_code == 200
    team_tasks_a = res_sup_a.json()
    assert len(team_tasks_a) == 1
    assert team_tasks_a[0]["id"] == isolation_setup.org_a.task.id

    res_sup_b = await client.get("/tasks/team", headers=isolation_setup.org_b.supervisor_headers)
    assert res_sup_b.status_code == 200
    team_tasks_b = res_sup_b.json()
    assert len(team_tasks_b) == 1
    assert team_tasks_b[0]["id"] == isolation_setup.org_b.task.id


@pytest.mark.asyncio
async def test_list_leaves_and_team_leaves_isolation(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /leaves/ and GET /leaves/team:
    - Admin A lists all leaves in Org A (count = 1). Org B leaves excluded. X-Total-Count = 1.
    - Supervisor A team leaves lists only Employee A leave (count = 1).
    - Employee A sees only own leave in Org A.
    """
    # Admin A listing leaves
    res_leaves = await client.get("/leaves/", headers=isolation_setup.org_a.admin_headers)
    assert res_leaves.status_code == 200
    leaves = res_leaves.json()
    assert len(leaves) == 1
    assert leaves[0]["id"] == isolation_setup.org_a.leave.id
    assert res_leaves.headers["X-Total-Count"] == "1"

    # Supervisor A listing team leaves
    res_team = await client.get("/leaves/team", headers=isolation_setup.org_a.supervisor_headers)
    assert res_team.status_code == 200
    team_leaves = res_team.json()
    assert len(team_leaves) == 1
    assert team_leaves[0]["id"] == isolation_setup.org_a.leave.id

    # Employee A listing leaves (scoped to self)
    res_emp = await client.get("/leaves/", headers=isolation_setup.org_a.employee_headers)
    assert res_emp.status_code == 200
    assert len(res_emp.json()) == 1
    assert res_emp.json()[0]["id"] == isolation_setup.org_a.leave.id


@pytest.mark.asyncio
async def test_list_users_and_reports_isolation(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /users/ and GET /users/me/reports:
    - Admin A lists employees in Org A (2 users: Supervisor, Employee; Admin excluded from employees list).
      Org B users excluded. X-Total-Count = 2.
    - Supervisor A reports returns only Employee A (count = 1). Org B reports excluded.
    """
    # List employees as Admin A
    res_users = await client.get("/users/", headers=isolation_setup.org_a.admin_headers)
    assert res_users.status_code == 200
    users_data = res_users.json()
    assert len(users_data) == 2
    user_ids = {u["id"] for u in users_data}
    assert isolation_setup.org_a.supervisor.id in user_ids
    assert isolation_setup.org_a.employee.id in user_ids
    assert isolation_setup.org_b.admin.id not in user_ids
    assert isolation_setup.org_b.supervisor.id not in user_ids
    assert isolation_setup.org_b.employee.id not in user_ids
    assert res_users.headers["X-Total-Count"] == "2"

    # Supervisor A reports
    res_rep = await client.get("/users/me/reports", headers=isolation_setup.org_a.supervisor_headers)
    assert res_rep.status_code == 200
    reports = res_rep.json()
    assert len(reports) == 1
    assert reports[0]["id"] == isolation_setup.org_a.employee.id


# ===========================================================================
# 3. Cross-Tenant Write Attacks & Foreign-Key Spoofing
# ===========================================================================

@pytest.mark.asyncio
async def test_cross_org_write_task_assignment_blocked(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    POST /tasks/ with assigned_to targeting an Org B user returns 404 ("Assigned user with ID ... not found.").
    No task is created in Org A or Org B.
    """
    emp_b_id = isolation_setup.org_b.employee.id
    payload = {
        "title": "Cross-Org Assignment Attack",
        "description": "Attempting to assign task to Org B user",
        "priority": "HIGH",
        "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "assigned_to": emp_b_id,
    }

    # Attempt via Admin A
    res_admin = await client.post("/tasks/", json=payload, headers=isolation_setup.org_a.admin_headers)
    assert res_admin.status_code == 404
    assert res_admin.json()["detail"] == f"Assigned user with ID {emp_b_id} not found."

    # Attempt via Supervisor A
    res_sup = await client.post("/tasks/", json=payload, headers=isolation_setup.org_a.supervisor_headers)
    assert res_sup.status_code == 404
    assert res_sup.json()["detail"] == f"Assigned user with ID {emp_b_id} not found."

    # Verify DB: No task with title 'Cross-Org Assignment Attack' exists
    res = await db_session.execute(select(Task).where(Task.title == "Cross-Org Assignment Attack"))
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cross_org_write_create_employee_with_cross_org_supervisor_blocked(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    POST /users/employees with reports_to_id targeting an Org B supervisor returns 404
    ("Reports-to supervisor user not found.").
    No user is created.
    """
    sup_b_id = isolation_setup.org_b.supervisor.id
    payload = {
        "full_name": "Infiltrator Employee",
        "email": "infiltrator@alpha.example.com",
        "designation": "Security Tester",
        "reports_to_id": sup_b_id,
        "access_level": 3,
    }

    res = await client.post(
        "/users/employees",
        json=payload,
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Reports-to supervisor user not found."

    # Verify DB: User was NOT created
    res_user = await db_session.execute(
        select(User).where(User.email == "infiltrator@alpha.example.com")
    )
    assert res_user.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cross_org_write_set_reports_to_blocked(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    PATCH /users/{user_id}/reports-to targeting Org A employee with reports_to_id of Org B supervisor
    returns 404 ("Reports-to supervisor user not found.").
    Org A employee's supervisor remains unchanged.
    """
    emp_a = isolation_setup.org_a.employee
    sup_b = isolation_setup.org_b.supervisor
    orig_sup_id = emp_a.reports_to_id

    res = await client.patch(
        f"/users/{emp_a.id}/reports-to",
        json={"reports_to_id": sup_b.id},
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Reports-to supervisor user not found."

    # Verify DB: reports_to_id unchanged
    await db_session.refresh(emp_a)
    assert emp_a.reports_to_id == orig_sup_id


@pytest.mark.asyncio
async def test_cross_org_write_deactivation_reassignments_blocked(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    PATCH /users/{user_id}/deactivate:
    - Attempting deactivation of Supervisor A with default_new_manager_id pointing to Supervisor B -> 404.
    - Attempting deactivation of Supervisor A with reassignments pointing to Supervisor B -> 404.
    Supervisor A remains active, Employee A's supervisor remains unchanged.
    """
    sup_a = isolation_setup.org_a.supervisor
    emp_a = isolation_setup.org_a.employee
    sup_b = isolation_setup.org_b.supervisor

    # 1. default_new_manager_id attack
    payload_default = {"default_new_manager_id": sup_b.id}
    res_def = await client.patch(
        f"/users/{sup_a.id}/deactivate",
        json=payload_default,
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_def.status_code == 404
    assert res_def.json()["detail"] == "Reports-to supervisor user not found."

    # 2. explicit reassignments mapping attack
    payload_map = {"reassignments": {emp_a.id: sup_b.id}}
    res_map = await client.patch(
        f"/users/{sup_a.id}/deactivate",
        json=payload_map,
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_map.status_code == 404
    assert res_map.json()["detail"] == "Reports-to supervisor user not found."

    # Verify DB: Supervisor A still active, Employee A reports_to_id untouched
    await db_session.refresh(sup_a)
    await db_session.refresh(emp_a)
    assert sup_a.is_active is True
    assert emp_a.reports_to_id == sup_a.id


# ===========================================================================
# 4. Analytics Scoping Attacks
# ===========================================================================

@pytest.mark.asyncio
async def test_analytics_cross_org_employee_lookup_returns_404(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /analytics/performance?employee_id={id}:
    - Admin A targeting Org B employee receives 404.
    - Supervisor A targeting Org B employee receives 403 (anti-enumeration across non-reports).
    """
    emp_b_id = isolation_setup.org_b.employee.id

    res_admin = await client.get(
        f"/analytics/performance?employee_id={emp_b_id}",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_admin.status_code == 404
    assert res_admin.json()["detail"] == f"User with ID {emp_b_id} not found."

    res_sup = await client.get(
        f"/analytics/performance?employee_id={emp_b_id}",
        headers=isolation_setup.org_a.supervisor_headers,
    )
    assert res_sup.status_code == 403


@pytest.mark.asyncio
async def test_analytics_org_team_self_metrics_scoping(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    GET /analytics/performance:
    - Admin A (org scope) sees total_tasks = 1 (Org A active task). Org B and soft-deleted tasks excluded.
    - Supervisor A (team scope) sees total_tasks = 1 (Employee A task).
    - Employee A (self scope) sees total_tasks = 1.
    """
    # Org scope (Admin A)
    res_admin = await client.get("/analytics/performance", headers=isolation_setup.org_a.admin_headers)
    assert res_admin.status_code == 200
    data_admin = res_admin.json()
    assert data_admin["scope"] == "org"
    assert data_admin["total_tasks"] == 1

    # Team scope (Supervisor A)
    res_sup = await client.get("/analytics/performance", headers=isolation_setup.org_a.supervisor_headers)
    assert res_sup.status_code == 200
    data_sup = res_sup.json()
    assert data_sup["scope"] == "team"
    assert data_sup["total_tasks"] == 1

    # Self scope (Employee A)
    res_emp = await client.get("/analytics/performance", headers=isolation_setup.org_a.employee_headers)
    assert res_emp.status_code == 200
    data_emp = res_emp.json()
    assert data_emp["scope"] == "self"
    assert data_emp["total_tasks"] == 1


# ===========================================================================
# 5. Query Parameter & Request Body Tenant Spoofing / Injection
# ===========================================================================

@pytest.mark.asyncio
async def test_query_param_organization_id_ignored(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    Injecting ?organization_id={org_b.id} into list or analytics endpoints has NO effect.
    Scoping is strictly taken from current_user.organization_id.
    """
    org_b_id = isolation_setup.org_b.org.id

    # Tasks list
    res_tasks = await client.get(
        f"/tasks/?organization_id={org_b_id}",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_tasks.status_code == 200
    tasks = res_tasks.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == isolation_setup.org_a.task.id

    # Leaves list
    res_leaves = await client.get(
        f"/leaves/?organization_id={org_b_id}",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_leaves.status_code == 200
    leaves = res_leaves.json()
    assert len(leaves) == 1
    assert leaves[0]["id"] == isolation_setup.org_a.leave.id

    # Users list (employees in Org A)
    res_users = await client.get(
        f"/users/?organization_id={org_b_id}",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_users.status_code == 200
    users = res_users.json()
    assert len(users) == 2
    assert all(u["id"] != isolation_setup.org_b.admin.id for u in users)

    # Analytics
    res_analytics = await client.get(
        f"/analytics/performance?organization_id={org_b_id}",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_analytics.status_code == 200
    assert res_analytics.json()["total_tasks"] == 1


@pytest.mark.asyncio
async def test_body_organization_id_injection_overridden_by_session(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
    db_session: AsyncSession,
):
    """
    Injecting organization_id of Org B into POST request bodies (/tasks/, /leaves/)
    is completely overridden by current_user.organization_id.
    """
    org_b_id = isolation_setup.org_b.org.id
    org_a_id = isolation_setup.org_a.org.id

    # Create task with injected organization_id
    task_payload = {
        "title": "Injection Test Task",
        "description": "Injection test task description",
        "priority": "LOW",
        "due_datetime": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "assigned_to": isolation_setup.org_a.employee.id,
        "organization_id": org_b_id,
    }
    res_task = await client.post("/tasks/", json=task_payload, headers=isolation_setup.org_a.admin_headers)
    assert res_task.status_code == 201
    created_task_id = res_task.json()["id"]

    # Verify DB: created task's organization_id is Org A, NOT Org B
    res_db = await db_session.execute(select(Task).where(Task.id == created_task_id))
    db_task = res_db.scalar_one()
    assert db_task.organization_id == org_a_id

    # Create leave with injected organization_id
    from datetime import date
    leave_payload = {
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
        "end_date": (date.today() + timedelta(days=12)).isoformat(),
        "reason": "Injection Test Leave",
        "organization_id": org_b_id,
    }
    res_leave = await client.post("/leaves/", json=leave_payload, headers=isolation_setup.org_a.employee_headers)
    assert res_leave.status_code == 201
    created_leave_id = res_leave.json()["id"]

    res_leave_db = await db_session.execute(select(LeaveRequest).where(LeaveRequest.id == created_leave_id))
    db_leave = res_leave_db.scalar_one()
    assert db_leave.organization_id == org_a_id


# ===========================================================================
# 6. Token & Auth Boundaries
# ===========================================================================

@pytest.mark.asyncio
async def test_auth_token_isolation_across_tenants(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    Org A's token cannot read Org B profile or change Org B's state.
    GET /users/me always returns caller's profile.
    Calling /tasks/ with Org A token returns Org A tasks, while Org B token returns Org B tasks.
    """
    res_me_a = await client.get("/users/me", headers=isolation_setup.org_a.admin_headers)
    assert res_me_a.status_code == 200
    assert res_me_a.json()["email"] == isolation_setup.org_a.admin.email

    res_me_b = await client.get("/users/me", headers=isolation_setup.org_b.admin_headers)
    assert res_me_b.status_code == 200
    assert res_me_b.json()["email"] == isolation_setup.org_b.admin.email

    # Tasks list isolation between tokens
    res_tasks_a = await client.get("/tasks/", headers=isolation_setup.org_a.admin_headers)
    assert res_tasks_a.status_code == 200
    assert [t["id"] for t in res_tasks_a.json()] == [isolation_setup.org_a.task.id]

    res_tasks_b = await client.get("/tasks/", headers=isolation_setup.org_b.admin_headers)
    assert res_tasks_b.status_code == 200
    assert [t["id"] for t in res_tasks_b.json()] == [isolation_setup.org_b.task.id]


@pytest.mark.asyncio
async def test_deactivated_user_token_rejected_immediately(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    Once an employee is deactivated by Admin A, their existing JWT token is immediately rejected (401).
    Anti-enumeration guarantees identical 401 "User not found." response.
    """
    emp_a = isolation_setup.org_a.employee

    # Deactivate Employee A via Admin A
    res_deact = await client.patch(
        f"/users/{emp_a.id}/deactivate",
        headers=isolation_setup.org_a.admin_headers,
    )
    assert res_deact.status_code == 200

    # Subsequent request using employee_a_headers is rejected with 401
    res_blocked = await client.get("/users/me", headers=isolation_setup.org_a.employee_headers)
    assert res_blocked.status_code == 401
    assert res_blocked.json()["detail"] == "User not found."


@pytest.mark.asyncio
async def test_revoked_token_via_logout_rejected(
    client: AsyncClient,
    isolation_setup: TenantIsolationSetup,
):
    """
    Once a user logs out (POST /auth/logout), their token is revoked and cannot be used anywhere.
    """
    admin_headers = isolation_setup.org_a.admin_headers

    # Logout
    res_logout = await client.post("/auth/logout", headers=admin_headers)
    assert res_logout.status_code == 200

    # Subsequent request is rejected with 401
    res_me = await client.get("/users/me", headers=admin_headers)
    assert res_me.status_code == 401
    assert "revoked" in res_me.json()["detail"].lower()
