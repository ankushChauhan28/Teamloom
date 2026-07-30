"""
Integration Tests for Role-Based Access Control (RBAC) Enforcements

EDUCATIONAL EXPLANATION - RBAC TESTING:
----------------------------------------
RBAC tests ensure that permission rules are strictly enforced across all API endpoints.
We specifically verify that requests using an EMPLOYEE role access token are blocked with
HTTP 403 Forbidden when attempting Admin-only operations.
"""

from datetime import date, timedelta

from fastapi import status
from fastapi.testclient import TestClient

from app.models.user import User


def test_employee_cannot_create_task(
    client: TestClient,
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
    response = client.post("/tasks/", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "action requires admin role" in response.json()["detail"].lower()


def test_employee_cannot_delete_task(
    client: TestClient,
    admin_headers: dict[str, str],
    employee_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Employee attempting to delete a task returns HTTP 403 Forbidden.
    """
    # Admin creates task
    task_res = client.post(
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

    # Employee attempts deletion -> 403
    del_res = client.delete(f"/tasks/{task_id}", headers=employee_headers)
    assert del_res.status_code == status.HTTP_403_FORBIDDEN


def test_employee_cannot_list_all_employees(
    client: TestClient, employee_headers: dict[str, str]
) -> None:
    """
    Test Employee attempting to list all employees (`GET /users/`) returns HTTP 403 Forbidden.
    """
    response = client.get("/users/", headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_employee_cannot_review_leave(
    client: TestClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test Employee attempting to approve/reject a leave request returns HTTP 403 Forbidden.
    """
    # Employee submits leave
    sub_res = client.post(
        "/leaves/",
        json={
            "reason": "Test Leave",
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
        },
        headers=employee_headers,
    )
    leave_id = sub_res.json()["id"]

    # Employee attempts to approve leave -> 403
    rev_res = client.patch(
        f"/leaves/{leave_id}",
        json={"status": "APPROVED"},
        headers=employee_headers,
    )
    assert rev_res.status_code == status.HTTP_403_FORBIDDEN
