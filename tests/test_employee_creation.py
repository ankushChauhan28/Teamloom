"""
Integration & Security Tests for Employee Creation, Employee ID System, and Forced Password Change Flow
"""

from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_admin_create_employee_success(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
) -> None:
    """
    Test Admin can successfully create a new employee with a manager assigned.
    Verifies employee_code format, must_change_password flag, and absence of plaintext password in response body.
    """
    payload = {
        "full_name": "Alice Employee",
        "email": "alice.created@example.com",
        "manager_id": admin_user.id,
    }
    response = await client.post("/users/employees", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["full_name"] == "Alice Employee"
    assert data["email"] == "alice.created@example.com"
    assert data["manager_id"] == admin_user.id
    assert data["role"] == "EMPLOYEE"
    assert data["employee_code"].startswith("EMP-")
    assert data["must_change_password"] is True
    assert "password" not in data
    assert "temp_password" not in data
    assert "temporary_password" not in data


@pytest.mark.asyncio
async def test_employee_code_sequential_generation(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Test that employee_code values are generated sequentially (EMP-1001, EMP-1002, etc.).
    """
    res1 = await client.post(
        "/users/employees",
        json={"full_name": "Seq User 1", "email": "seq1@example.com"},
        headers=admin_headers,
    )
    res2 = await client.post(
        "/users/employees",
        json={"full_name": "Seq User 2", "email": "seq2@example.com"},
        headers=admin_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    assert res2.status_code == status.HTTP_201_CREATED

    code1 = res1.json()["employee_code"]
    code2 = res2.json()["employee_code"]

    num1 = int(code1.split("-")[1])
    num2 = int(code2.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.asyncio
async def test_duplicate_email_rejected(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test creating an employee with an existing email returns HTTP 400 Bad Request.
    """
    payload = {
        "full_name": "Duplicate Email User",
        "email": employee_user.email,
    }
    response = await client.post("/users/employees", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_admin_cannot_create_employee(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test regular EMPLOYEE attempting to call `POST /users/employees` returns HTTP 403 Forbidden.
    """
    payload = {
        "full_name": "Unauthorized Employee",
        "email": "unauth@example.com",
    }
    response = await client.post("/users/employees", json=payload, headers=employee_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_must_change_password_enforcement_and_change_flow(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Full security flow test:
    1. Admin creates a new employee. Captured temp_password via mock.
    2. New employee logs in with temp_password.
    3. New employee attempts accessing protected route (`GET /tasks/`) -> blocked with 403 password_change_required.
    4. New employee calls `POST /auth/change-password` -> password updated and flag cleared.
    5. New employee retries `GET /tasks/` -> access granted (200 OK).
    """
    captured_passwords = []

    def mock_send_email(email, full_name, employee_code, temp_password):
        captured_passwords.append(temp_password)
        return True

    with patch("app.services.user_service.send_employee_welcome_email", side_effect=mock_send_email):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Pwd Change User", "email": "pwd.change@example.com"},
            headers=admin_headers,
        )
        assert create_res.status_code == status.HTTP_201_CREATED
        temp_pwd = captured_passwords[0]

    # Step 2: Employee logs in with temp password and assigned employee_code
    emp_code = create_res.json()["employee_code"]
    login_res = await client.post(
        "/auth/login",
        json={"employee_code": emp_code, "password": temp_pwd},
    )
    assert login_res.status_code == status.HTTP_200_OK
    emp_token = login_res.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Step 3: Accessing protected route is blocked with 403 password_change_required
    task_res = await client.get("/tasks/", headers=emp_headers)
    assert task_res.status_code == status.HTTP_403_FORBIDDEN
    assert task_res.json()["detail"] == "password_change_required"

    leave_res = await client.get("/leaves/", headers=emp_headers)
    assert leave_res.status_code == status.HTTP_403_FORBIDDEN
    assert leave_res.json()["detail"] == "password_change_required"

    # Step 4: Employee changes password via POST /auth/change-password
    change_res = await client.post(
        "/auth/change-password",
        json={"current_password": temp_pwd, "new_password": "NewPermanentPassword123!"},
        headers=emp_headers,
    )
    assert change_res.status_code == status.HTTP_200_OK
    assert change_res.json()["must_change_password"] is False

    # Step 5: Employee retries accessing protected route -> 200 OK granted
    unlocked_res = await client.get("/tasks/", headers=emp_headers)
    assert unlocked_res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_admin_reset_temp_password(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test Admin calling `POST /users/{user_id}/reset-temp-password` resets password and enforces change.
    Response does not leak temporary password.
    """
    res = await client.post(
        f"/users/{employee_user.id}/reset-temp-password",
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["id"] == employee_user.id
    assert "password" not in data
    assert "temp_password" not in data


@pytest.mark.asyncio
async def test_existing_users_unaffected(
    client: AsyncClient,
    employee_headers: dict[str, str],
) -> None:
    """
    Test existing users (must_change_password=False) can access protected endpoints normally.
    """
    response = await client.get("/tasks/", headers=employee_headers)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_pending_password_change_blocked_on_users_me(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Comprehensive Audit Test: Confirm a user with must_change_password = True is blocked
    with HTTP 403 on GET /users/me and PATCH /users/me as well.
    """
    captured_passwords = []

    def mock_send_email(email, full_name, employee_code, temp_password):
        captured_passwords.append(temp_password)
        return True

    with patch("app.services.user_service.send_employee_welcome_email", side_effect=mock_send_email):
        create_res = await client.post(
            "/users/employees",
            json={"full_name": "Audit User", "email": "audit.user@example.com"},
            headers=admin_headers,
        )
        assert create_res.status_code == status.HTTP_201_CREATED
        temp_pwd = captured_passwords[0]
        emp_code = create_res.json()["employee_code"]

    login_res = await client.post(
        "/auth/login",
        json={"employee_code": emp_code, "password": temp_pwd},
    )
    emp_token = login_res.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Verify GET /users/me is blocked with 403
    me_res = await client.get("/users/me", headers=emp_headers)
    assert me_res.status_code == status.HTTP_403_FORBIDDEN
    assert me_res.json()["detail"] == "password_change_required"

    # Verify PATCH /users/me is blocked with 403
    patch_me_res = await client.patch(
        "/users/me",
        json={"full_name": "New Name"},
        headers=emp_headers,
    )
    assert patch_me_res.status_code == status.HTTP_403_FORBIDDEN
    assert patch_me_res.json()["detail"] == "password_change_required"

