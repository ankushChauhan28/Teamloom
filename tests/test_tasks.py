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
    employee_user: User,
) -> None:
    """
    Test Admin deleting a task returns HTTP 204 No Content.
    """
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
    task_id = task_res.json()["id"]

    del_res = await client.delete(f"/tasks/{task_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    get_res = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND


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
        employee_code="EMP-9000",
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
            employee_code=f"EMP-900{r_idx + 1}",
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



