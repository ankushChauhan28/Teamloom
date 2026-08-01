"""
Integration Tests for Task Endpoints (/tasks/)
"""

from datetime import date, timedelta
import pytest
from fastapi import status
from httpx import AsyncClient

from app.models.user import User


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
    payload = {
        "title": "Build Testing Suite",
        "description": "Write pytest integration and unit tests.",
        "priority": "HIGH",
        "due_date": str(date.today() + timedelta(days=7)),
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
        "due_date": str(date.today() + timedelta(days=5)),
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
        "due_date": str(date.today() + timedelta(days=3)),
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
    Test query parameter filtering, sorting, and pagination (skip, limit, sort_by).
    """
    for i in range(3):
        await client.post(
            "/tasks/",
            json={
                "title": f"Task {i}",
                "description": "Batch task",
                "priority": "LOW" if i == 0 else "HIGH",
                "due_date": str(date.today() + timedelta(days=i + 1)),
                "assigned_to": employee_user.id,
            },
            headers=admin_headers,
        )

    response = await client.get(
        "/tasks/?priority=HIGH&sort_by=due_date&skip=0&limit=2",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) <= 2
    for item in data:
        assert item["priority"] == "HIGH"


@pytest.mark.asyncio
async def test_employee_update_status_only(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee updating task status succeeds, but updating title/description fails with 403.
    """
    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Status Update Task",
            "description": "Description",
            "priority": "MEDIUM",
            "due_date": str(date.today() + timedelta(days=5)),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    task_id = task_res.json()["id"]

    status_res = await client.patch(
        f"/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=employee_headers,
    )
    assert status_res.status_code == status.HTTP_200_OK
    assert status_res.json()["status"] == "IN_PROGRESS"

    title_res = await client.patch(
        f"/tasks/{task_id}",
        json={"title": "Hacked Title"},
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
            "due_date": str(date.today() + timedelta(days=1)),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    task_id = task_res.json()["id"]

    del_res = await client.delete(f"/tasks/{task_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    get_res = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND
