"""
Integration Tests for User Endpoints (/users/)
"""

from fastapi import status
from fastapi.testclient import TestClient

from app.models.user import User


def test_get_me_success(
    client: TestClient, employee_user: User, employee_headers: dict[str, str]
) -> None:
    """
    Test retrieving own user profile (`GET /users/me`) returns 200 and matches user payload.
    """
    response = client.get("/users/me", headers=employee_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == employee_user.id
    assert data["email"] == employee_user.email
    assert data["full_name"] == employee_user.full_name
    assert data["role"] == "EMPLOYEE"


def test_get_me_unauthenticated_fails(client: TestClient) -> None:
    """
    Test accessing `/users/me` without Authorization header returns 401 Unauthorized.
    """
    response = client.get("/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_update_me_success(
    client: TestClient, employee_user: User, employee_headers: dict[str, str]
) -> None:
    """
    Test updating own full name (`PATCH /users/me`) returns updated user model.
    """
    payload = {"full_name": "Updated John Employee"}
    response = client.patch("/users/me", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["full_name"] == payload["full_name"]
    assert data["email"] == employee_user.email


def test_list_employees_by_admin(
    client: TestClient,
    admin_user: User,
    employee_user: User,
    admin_headers: dict[str, str],
) -> None:
    """
    Test listing employees (`GET /users/`) as Admin returns a list of EMPLOYEE role users.
    """
    response = client.get("/users/", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Verify all returned users have role EMPLOYEE
    for item in data:
        assert item["role"] == "EMPLOYEE"
