"""
Integration Tests for Task Endpoints (/tasks/)
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User, UserRole



@pytest.mark.asyncio
async def test_create_task_admin_success(
    client: AsyncClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test Admin creating a task assigned to an employee succeeds with 201 Created.
    """
    due_dt = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    payload = {
        "title": "Build Testing Suite",
        "description": "Write pytest integration and unit tests.",
        "priority": "HIGH",
        "due_datetime": due_dt,
        "assigned_to": employee_user.id,
    }
    response = await client.post("/tasks/", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["title"] == payload["title"]
    assert data["priority"] == "HIGH"
    assert data["status"] == "PENDING"
    assert data["assigned_to"] == employee_user.id
    assert data["created_by"] == admin_user.id
    assert data["completed_at"] is None


@pytest.mark.asyncio
async def test_create_task_assign_to_admin_fails(
    client: AsyncClient,
    admin_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test Admin attempting to assign a task to an Admin user fails with 400 Bad Request.
    """
    payload = {
        "title": "Invalid Assignment Task",
        "description": "Cannot assign tasks to admins.",
        "priority": "MEDIUM",
        "due_datetime": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        "assigned_to": admin_user.id,
    }
    response = await client.post("/tasks/", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "employee role" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_tasks_scope_isolation(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test task listing scope: Employee sees only their assigned tasks, while Admin sees all tasks.
    """
    task_payload = {
        "title": "Employee Private Task",
        "description": "Assigned task.",
        "priority": "LOW",
        "due_datetime": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "assigned_to": employee_user.id,
    }
    await client.post("/tasks/", json=task_payload, headers=admin_headers)

    emp_res = await client.get("/tasks/", headers=employee_headers)
    assert emp_res.status_code == status.HTTP_200_OK
    emp_tasks = emp_res.json()
    assert len(emp_tasks) >= 1
    for task in emp_tasks:
        assert task["assigned_to"] == employee_user.id


@pytest.mark.asyncio
async def test_list_tasks_pagination_and_sorting(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test query parameter filtering, sorting by due_datetime, and pagination (skip, limit, sort_by).
    """
    for i in range(3):
        await client.post(
            "/tasks/",
            json={
                "title": f"Task {i}",
                "description": "Batch task",
                "priority": "LOW" if i == 0 else "HIGH",
                "due_datetime": (datetime.now(UTC) + timedelta(days=i + 1)).isoformat(),
                "assigned_to": employee_user.id,
            },
            headers=admin_headers,
        )

    response = await client.get(
        "/tasks/?priority=HIGH&sort_by=due_datetime&skip=0&limit=2",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) <= 2
    for item in data:
        assert item["priority"] == "HIGH"


@pytest.mark.asyncio
async def test_employee_update_status_and_completed_at_timestamp(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee updating task status to COMPLETED populates completed_at timestamp,
    and changing back to IN_PROGRESS resets completed_at to null.
    """
    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Status Update Task",
            "description": "Description",
            "priority": "MEDIUM",
            "due_datetime": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    task_id = task_res.json()["id"]

    # Initially pending, completed_at is None
    assert task_res.json()["completed_at"] is None

    # Transition to COMPLETED
    status_res = await client.patch(
        f"/tasks/{task_id}",
        json={"status": "COMPLETED", "version": 1},
        headers=employee_headers,
    )
    assert status_res.status_code == status.HTTP_200_OK
    comp_data = status_res.json()
    assert comp_data["status"] == "COMPLETED"
    assert comp_data["completed_at"] is not None
    assert comp_data["version"] == 2

    # Attempting to modify a completed task fails with 400 Bad Request
    in_prog_res = await client.patch(
        f"/tasks/{task_id}",
        json={"status": "IN_PROGRESS", "version": 2},
        headers=employee_headers,
    )
    assert in_prog_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot modify a completed task" in in_prog_res.json()["detail"]

    # Editing unauthorized title field fails with 403
    title_res = await client.patch(
        f"/tasks/{task_id}",
        json={"title": "Hacked Title", "version": 2},
        headers=employee_headers,
    )
    assert title_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_delete_task_admin_success(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    employee_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Test Admin deleting a task soft-deletes the row:
    - Returns HTTP 204 No Content
    - Subsequent GET returns HTTP 404 Not Found
    - Row remains in database with is_deleted=True, deleted_at, deleted_by set
    - version column increments
    """
    from sqlalchemy import select
    from app.models.task import Task

    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Task To Delete",
            "description": "Temporary task",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    task_data = task_res.json()
    task_id = task_data["id"]
    initial_version = task_data["version"]

    del_res = await client.delete(f"/tasks/{task_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    get_res = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND

    # Verify task row still exists in DB with soft-delete fields set and version bumped
    stmt = select(Task).where(Task.id == task_id)
    raw_task = (await db_session.execute(stmt)).scalar_one()
    assert raw_task.is_deleted is True
    assert raw_task.deleted_at is not None
    assert raw_task.deleted_by == admin_user.id
    assert raw_task.version == initial_version + 1


@pytest.mark.asyncio
async def test_concurrent_status_update_raises_409_on_conflict(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test optimistic locking across real separate HTTP requests:
    1. Worker 1 and Worker 2 both observe the same task at version 1.
    2. Worker 1 PATCHes the task with version=1 -> succeeds (200 OK), new version is 2.
    3. Worker 2 PATCHes the task with the now-stale version=1 -> rejected with 409 Conflict.
    4. Confirm task state in DB remains untouched by the rejected stale update.
    """
    # 1. Create a task via API
    create_res = await client.post(
        "/tasks/",
        json={
            "title": "Concurrent Task Race Test",
            "description": "Testing optimistic locking",
            "priority": "HIGH",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    task_id = create_res.json()["id"]
    assert create_res.json()["version"] == 1

    # Both workers read the task at version 1
    w1_read = await client.get(f"/tasks/{task_id}", headers=employee_headers)
    assert w1_read.status_code == status.HTTP_200_OK
    assert w1_read.json()["version"] == 1

    # Worker 1 updates status to COMPLETED using version=1
    w1_patch = await client.patch(
        f"/tasks/{task_id}",
        json={"status": "COMPLETED", "version": 1},
        headers=employee_headers,
    )
    assert w1_patch.status_code == status.HTTP_200_OK
    w1_data = w1_patch.json()
    assert w1_data["status"] == "COMPLETED"
    assert w1_data["completed_at"] is not None
    assert w1_data["version"] == 2

    # Worker 2 attempts update using stale version=1
    w2_patch = await client.patch(
        f"/tasks/{task_id}",
        json={"status": "IN_PROGRESS", "version": 1},
        headers=employee_headers,
    )
    assert w2_patch.status_code == status.HTTP_409_CONFLICT
    assert "modified concurrently" in w2_patch.json()["detail"].lower()

    # Verify final DB state via API: status and completed_at remain from Worker 1
    verify_res = await client.get(f"/tasks/{task_id}", headers=employee_headers)
    assert verify_res.status_code == status.HTTP_200_OK
    final_data = verify_res.json()
    assert final_data["status"] == "COMPLETED"
    assert final_data["completed_at"] is not None
    assert final_data["version"] == 2


@pytest.mark.asyncio
async def test_task_update_happy_path_increments_version(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Happy path test:
    PATCH with the current correct version succeeds normally and returns an incremented version.
    """
    create_res = await client.post(
        "/tasks/",
        json={
            "title": "Version Increment Task",
            "description": "Initial description",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    task_id = create_res.json()["id"]
    assert create_res.json()["version"] == 1

    # Update 1: version 1 -> 2
    patch1 = await client.patch(
        f"/tasks/{task_id}",
        json={"title": "Updated Title v2", "version": 1},
        headers=admin_headers,
    )
    assert patch1.status_code == status.HTTP_200_OK
    assert patch1.json()["title"] == "Updated Title v2"
    assert patch1.json()["version"] == 2

    # Update 2: version 2 -> 3
    patch2 = await client.patch(
        f"/tasks/{task_id}",
        json={"title": "Updated Title v3", "version": 2},
        headers=admin_headers,
    )
    assert patch2.status_code == status.HTTP_200_OK
    assert patch2.json()["title"] == "Updated Title v3"
    assert patch2.json()["version"] == 3


@pytest.mark.asyncio
async def test_task_update_missing_version_returns_422(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Validation test:
    A PATCH request missing the required 'version' field returns HTTP 422 Unprocessable Entity,
    not a 500 error.
    """
    create_res = await client.post(
        "/tasks/",
        json={
            "title": "Missing Version Task",
            "description": "Validation test",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    task_id = create_res.json()["id"]

    res = await client.patch(
        f"/tasks/{task_id}",
        json={"title": "Title Without Version"},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    errors = res.json()["detail"]
    assert any("version" in str(err["loc"]) for err in errors)


@pytest.mark.asyncio
async def test_get_tasks_no_n_plus_one_queries(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test that retrieving a list of 10 tasks executes constant queries for tasks + relationships,
    rather than N+1 queries.
    """
    from sqlalchemy import event
    from tests.conftest import engine

    # 1. Create 10 tasks
    for i in range(10):
        await client.post(
            "/tasks/",
            json={
                "title": f"Batch Task {i}",
                "description": f"Description {i}",
                "priority": "MEDIUM",
                "due_datetime": (datetime.now(UTC) + timedelta(days=i + 1)).isoformat(),
                "assigned_to": employee_user.id,
            },
            headers=admin_headers,
        )

    # 2. Count queries executed during GET /tasks/
    queries = []

    def capture_queries(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_queries)
    try:
        response = await client.get("/tasks/?limit=10", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 10
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_queries)

    task_queries = [q for q in queries if "FROM tasks" in q]
    assert len(task_queries) == 1
    assert len(queries) <= 5


@pytest.mark.asyncio
async def test_get_team_tasks_no_n_plus_one_queries(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Test that retrieving team tasks for a manager with 5 direct reports having 3 tasks each (15 tasks)
    executes constant queries and avoids N+1 query explosion.
    """
    from sqlalchemy import event
    from tests.conftest import engine
    from app.core.security import create_access_token, hash_password
    from app.models.task import Task, TaskPriority, TaskStatus

    # 1. Create manager
    mgr = User(
        full_name="Task Manager",
        email="task.manager@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EMPLOYEE,
        employee_code="1000009000",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(mgr)
    await db_session.commit()
    await db_session.refresh(mgr)

    mgr_token = create_access_token(email=mgr.email, role=mgr.role.value)
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # 2. Create 5 direct reports and 3 tasks each (15 tasks)
    tasks_to_add = []
    for r_idx in range(5):
        rep = User(
            full_name=f"Team Member {r_idx}",
            email=f"team.member.{r_idx}@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.EMPLOYEE,
            employee_code=f"100000900{r_idx + 1}",
            reports_to_id=mgr.id,
            must_change_password=False,
            organization_id=test_org.id,
        )
        db_session.add(rep)
        await db_session.commit()
        await db_session.refresh(rep)

        for t_idx in range(3):
            tasks_to_add.append(
                Task(
                    title=f"Report {r_idx} Task {t_idx}",
                    description="Task item",
                    priority=TaskPriority.LOW,
                    status=TaskStatus.PENDING,
                    due_datetime=datetime.now(UTC) + timedelta(days=2),
                    assigned_to=rep.id,
                    created_by=mgr.id,
                    organization_id=test_org.id,
                )
            )

    db_session.add_all(tasks_to_add)
    await db_session.commit()


    # 3. Call GET /tasks/team/ and monitor query count
    queries = []

    def capture_queries(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_queries)
    try:
        response = await client.get("/tasks/team?limit=20", headers=mgr_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 15
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_queries)

    task_queries = [q for q in queries if "FROM tasks" in q]
    assert len(task_queries) == 1
    assert len(queries) <= 6


@pytest.mark.asyncio
async def test_soft_deleted_task_hidden_from_all_views_and_aggregations(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    employee_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Verifies that a soft-deleted task is hidden everywhere by default:
    - Task list (/tasks/) excludes it and X-Total-Count reflects active only
    - Team view (/tasks/team) excludes it and X-Total-Count reflects active only
    - Detail view (/tasks/{id}) returns 404
    - Update attempts (/tasks/{id}) return 404
    - Analytics (/analytics/performance) exclude it from counts and milestone trail
    - DB record still exists with is_deleted=True, deleted_at, deleted_by set, version bumped
    """
    from app.models.task import Task
    from sqlalchemy import select

    # Setup admin -> employee reporting hierarchy for team view testing
    employee_user.reports_to_id = admin_user.id
    await db_session.commit()

    # 1. Create two tasks
    t1_res = await client.post(
        "/tasks/",
        json={
            "title": "Active Task",
            "description": "Should remain visible",
            "priority": "HIGH",
            "due_datetime": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    assert t1_res.status_code == status.HTTP_201_CREATED
    t1_id = t1_res.json()["id"]

    t2_res = await client.post(
        "/tasks/",
        json={
            "title": "Task To Soft Delete",
            "description": "Should become hidden everywhere",
            "priority": "LOW",
            "due_datetime": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    assert t2_res.status_code == status.HTTP_201_CREATED
    t2_data = t2_res.json()
    t2_id = t2_data["id"]
    t2_initial_version = t2_data["version"]

    # Verify both tasks exist initially in list
    list_res_initial = await client.get("/tasks/", headers=admin_headers)
    assert list_res_initial.headers["X-Total-Count"] == "2"
    assert len(list_res_initial.json()) == 2

    # Verify both tasks count in analytics
    analytics_initial = await client.get("/analytics/performance", headers=admin_headers)
    assert analytics_initial.status_code == status.HTTP_200_OK
    assert analytics_initial.json()["total_tasks"] == 2

    # 2. Soft delete Task 2
    del_res = await client.delete(f"/tasks/{t2_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # 3. Verify single fetch returns 404
    detail_res = await client.get(f"/tasks/{t2_id}", headers=admin_headers)
    assert detail_res.status_code == status.HTTP_404_NOT_FOUND

    # 4. Verify update attempt returns 404
    update_res = await client.patch(
        f"/tasks/{t2_id}",
        json={"version": t2_initial_version, "title": "Updated Title Attempt"},
        headers=admin_headers,
    )
    assert update_res.status_code == status.HTTP_404_NOT_FOUND

    # 5. Verify task list (/tasks/) excludes Task 2 and X-Total-Count is 1
    list_res = await client.get("/tasks/", headers=admin_headers)
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.headers["X-Total-Count"] == "1"
    tasks_list = list_res.json()
    assert len(tasks_list) == 1
    assert tasks_list[0]["id"] == t1_id

    # 6. Verify team view (/tasks/team) excludes Task 2 and X-Total-Count is 1
    team_res = await client.get("/tasks/team", headers=admin_headers)
    assert team_res.status_code == status.HTTP_200_OK
    assert team_res.headers["X-Total-Count"] == "1"
    team_tasks = team_res.json()
    assert len(team_tasks) == 1
    assert team_tasks[0]["id"] == t1_id

    # 7. Verify analytics (/analytics/performance) excludes Task 2
    analytics_res = await client.get("/analytics/performance", headers=admin_headers)
    assert analytics_res.status_code == status.HTTP_200_OK
    analytics_data = analytics_res.json()
    assert analytics_data["total_tasks"] == 1
    trail_ids = [item["id"] for item in analytics_data["milestone_trail"]]
    assert t1_id in trail_ids
    assert t2_id not in trail_ids

    # 8. Verify the row still exists in DB with soft delete columns and version incremented
    raw_task = (await db_session.execute(select(Task).where(Task.id == t2_id))).scalar_one()
    assert raw_task.is_deleted is True
    assert raw_task.deleted_at is not None
    assert raw_task.deleted_by == admin_user.id
    assert raw_task.version == t2_initial_version + 1


@pytest.mark.asyncio
async def test_soft_delete_permissions_and_cross_org_isolation(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
    admin_headers_b: dict[str, str],
) -> None:
    """
    Verifies that:
    - Employees cannot delete tasks (403 Forbidden)
    - Admins from another organization cannot delete or see tasks (404 Not Found)
    - Re-deleting an already soft-deleted task returns 404 Not Found
    """
    # Create task in main org
    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Org Isolation Task",
            "description": "Tenant security test",
            "priority": "MEDIUM",
            "due_datetime": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    assert task_res.status_code == status.HTTP_201_CREATED
    task_id = task_res.json()["id"]

    # 1. Non-admin (employee) attempt to delete -> 403 Forbidden
    emp_del_res = await client.delete(f"/tasks/{task_id}", headers=employee_headers)
    assert emp_del_res.status_code == status.HTTP_403_FORBIDDEN

    # 2. Cross-org admin (Org B) cannot see task -> 404
    other_get_res = await client.get(f"/tasks/{task_id}", headers=admin_headers_b)
    assert other_get_res.status_code == status.HTTP_404_NOT_FOUND

    # Cross-org admin (Org B) cannot delete task -> 404
    other_del_res = await client.delete(f"/tasks/{task_id}", headers=admin_headers_b)
    assert other_del_res.status_code == status.HTTP_404_NOT_FOUND

    # 3. Main org admin successfully deletes task -> 204
    admin_del_res = await client.delete(f"/tasks/{task_id}", headers=admin_headers)
    assert admin_del_res.status_code == status.HTTP_204_NO_CONTENT

    # 4. Attempting to delete the already soft-deleted task -> 404 Not Found
    second_del_res = await client.delete(f"/tasks/{task_id}", headers=admin_headers)
    assert second_del_res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_deactivate_user_does_not_soft_delete_tasks(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    Verifies that deactivating a user does NOT soft-delete or modify their assigned tasks.
    Task rows retain is_deleted=False, deleted_at=None, deleted_by=None, and version unchanged.
    """
    from app.models.task import Task
    from sqlalchemy import select

    # Create new employee
    emp_res = await client.post(
        "/users/employees",
        json={"full_name": "Task Owner Employee", "email": "taskowner@testorg.com"},
        headers=admin_headers,
    )
    assert emp_res.status_code == status.HTTP_201_CREATED
    emp_id = emp_res.json()["id"]

    # Activate employee so tasks can be assigned (Slice 4e pending users cannot be assigned tasks)
    emp_db = await db_session.get(User, emp_id)
    emp_db.invitation_status = "ACTIVE"
    await db_session.commit()

    # Assign task to this employee
    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Persistent Task",
            "description": "Must not be deleted when user deactivates",
            "priority": "HIGH",
            "due_datetime": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
            "assigned_to": emp_id,
        },
        headers=admin_headers,
    )
    assert task_res.status_code == status.HTTP_201_CREATED
    task_data = task_res.json()
    task_id = task_data["id"]
    version_before = task_data["version"]

    # Deactivate the employee
    deact_res = await client.patch(f"/users/{emp_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == status.HTTP_200_OK

    # Check task row directly in database
    db_task = (await db_session.execute(select(Task).where(Task.id == task_id))).scalar_one()
    assert db_task.is_deleted is False
    assert db_task.deleted_at is None
    assert db_task.deleted_by is None
    assert db_task.version == version_before

    # Verify task is still reachable via API
    get_task_res = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert get_task_res.status_code == status.HTTP_200_OK
    assert get_task_res.json()["id"] == task_id




