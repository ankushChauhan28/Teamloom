"""
Integration Tests for Task Endpoints (/tasks/)
"""

from datetime import date, timedelta

from fastapi import status
from fastapi.testclient import TestClient

from app.models.user import User


def test_create_task_admin_success(
    client: TestClient,
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
    response = client.post("/tasks/", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["title"] == payload["title"]
    assert data["priority"] == "HIGH"
    assert data["status"] == "PENDING"
    assert data["assigned_to"] == employee_user.id
    assert data["created_by"] == admin_user.id


def test_create_task_assign_to_admin_fails(
    client: TestClient,
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
        "assigned_to": admin_user.id,  # Invalid: admin role
    }
    response = client.post("/tasks/", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "employee role" in response.json()["detail"].lower()


def test_list_tasks_scope_isolation(
    client: TestClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test task listing scope: Employee sees only their assigned tasks, while Admin sees all tasks.
    """
    # Create task for employee
    task_payload = {
        "title": "Employee Private Task",
        "description": "Assigned task.",
        "priority": "LOW",
        "due_date": str(date.today() + timedelta(days=3)),
        "assigned_to": employee_user.id,
    }
    client.post("/tasks/", json=task_payload, headers=admin_headers)

    # Employee lists tasks
    emp_res = client.get("/tasks/", headers=employee_headers)
    assert emp_res.status_code == status.HTTP_200_OK
    emp_tasks = emp_res.json()
    assert len(emp_tasks) >= 1
    for task in emp_tasks:
        assert task["assigned_to"] == employee_user.id


def test_list_tasks_pagination_and_sorting(
    client: TestClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test query parameter filtering, sorting, and pagination (skip, limit, sort_by).
    """
    # Seed 3 tasks
    for i in range(3):
        client.post(
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

    # Query with priority filter, sorting, and limit=2
    response = client.get(
        "/tasks/?priority=HIGH&sort_by=due_date&skip=0&limit=2",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) <= 2
    for item in data:
        assert item["priority"] == "HIGH"


def test_employee_update_status_only(
    client: TestClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee updating task status succeeds, but updating title/description fails with 403.
    """
    # 1. Admin creates task
    task_res = client.post(
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

    # 2. Employee updates status -> Success (200)
    status_res = client.patch(
        f"/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=employee_headers,
    )
    assert status_res.status_code == status.HTTP_200_OK
    assert status_res.json()["status"] == "IN_PROGRESS"

    # 3. Employee attempts to update title -> Forbidden (403)
    title_res = client.patch(
        f"/tasks/{task_id}",
        json={"title": "Hacked Title"},
        headers=employee_headers,
    )
    assert title_res.status_code == status.HTTP_403_FORBIDDEN


def test_delete_task_admin_success(
    client: TestClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Admin deleting a task returns HTTP 204 No Content.
    """
    task_res = client.post(
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

    # Delete task
    del_res = client.delete(f"/tasks/{task_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # Verify task is gone
    get_res = client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND
