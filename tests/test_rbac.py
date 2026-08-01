"""
Integration Tests for Role-Based Access Control (RBAC) Enforcements
"""

from datetime import date, timedelta
import pytest
from fastapi import status
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_employee_cannot_create_task(
    client: AsyncClient,
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee attempting to create a task returns HTTP 403 Forbidden.
    """
    payload = {
        "title": "Unauthorized Task",
        "description": "Employee trying to create task.",
        "priority": "HIGH",
        "due_date": str(date.today() + timedelta(days=5)),
        "assigned_to": employee_user.id,
    }
    response = await client.post("/tasks/", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "action requires admin role" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_employee_cannot_delete_task(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee attempting to delete a task returns HTTP 403 Forbidden.
    """
    task_res = await client.post(
        "/tasks/",
        json={
            "title": "Task for Deletion Test",
            "description": "Description",
            "priority": "LOW",
            "due_date": str(date.today() + timedelta(days=2)),
            "assigned_to": employee_user.id,
        },
        headers=admin_headers,
    )
    task_id = task_res.json()["id"]

    del_res = await client.delete(f"/tasks/{task_id}", headers=employee_headers)
    assert del_res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_employee_cannot_list_all_employees(
    client: AsyncClient, employee_headers: dict[str, str]
) -> None:
    """
    Test Employee attempting to list all employees (`GET /users/`) returns HTTP 403 Forbidden.
    """
    response = await client.get("/users/", headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_employee_cannot_review_leave(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test Employee attempting to approve/reject a leave request returns HTTP 403 Forbidden.
    """
    sub_res = await client.post(
        "/leaves/",
        json={
            "reason": "Test Leave",
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
        },
        headers=employee_headers,
    )
    leave_id = sub_res.json()["id"]

    rev_res = await client.patch(
        f"/leaves/{leave_id}",
        json={"status": "APPROVED"},
        headers=employee_headers,
    )
    assert rev_res.status_code == status.HTTP_403_FORBIDDEN
