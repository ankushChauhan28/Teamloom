import re
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.user import EmployeeCreate
from app.services.user_service import create_employee



@pytest.mark.asyncio
async def test_admin_create_employee_success(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
) -> None:
    """
    Test Admin can successfully create a new employee with a manager assigned.
    Verifies employee_code 10-digit numeric format, must_change_password flag, and absence of plaintext password in response body.
    """
    payload = {
        "full_name": "Alice Employee",
        "email": "alice.created@example.com",
        "reports_to_id": admin_user.id,
        "designation": "Lead Engineer",
    }
    response = await client.post("/users/employees", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["full_name"] == "Alice Employee"
    assert data["email"] == "alice.created@example.com"
    assert data["reports_to_id"] == admin_user.id
    assert data["designation"] == "Lead Engineer"
    assert data["role"] == "EMPLOYEE"
    assert re.match(r"^[0-9]{10}$", data["employee_code"])
    assert data["must_change_password"] is True
    assert "password" not in data
    assert "temp_password" not in data
    assert "temporary_password" not in data


@pytest.mark.asyncio
async def test_employee_code_10_digit_random_generation(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Test that employee_code values are generated as 10-digit random numeric strings.
    """
    res1 = await client.post(
        "/users/employees",
        json={"full_name": "Random User 1", "email": "random1@example.com"},
        headers=admin_headers,
    )
    res2 = await client.post(
        "/users/employees",
        json={"full_name": "Random User 2", "email": "random2@example.com"},
        headers=admin_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    assert res2.status_code == status.HTTP_201_CREATED

    code1 = res1.json()["employee_code"]
    code2 = res2.json()["employee_code"]

    assert re.match(r"^[0-9]{10}$", code1)
    assert re.match(r"^[0-9]{10}$", code2)
    assert code1 != code2


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
async def test_duplicate_email_case_insensitive_rejected(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_user: User,
) -> None:
    """
    Test creating an employee with an existing email in different casing returns HTTP 400.
    """
    payload = {
        "full_name": "Duplicate Mixed Case User",
        "email": employee_user.email.upper(),
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

    with patch(
        "app.services.user_service.send_employee_welcome_email", side_effect=mock_send_email
    ):
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
        json={"identifier": emp_code, "password": temp_pwd, "mode": "employee"},
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

    with patch(
        "app.services.user_service.send_employee_welcome_email", side_effect=mock_send_email
    ):
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
        json={"identifier": emp_code, "password": temp_pwd, "mode": "employee"},
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


@pytest.mark.asyncio
async def test_concurrent_employee_creation_no_duplicate_codes(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Audit & Security Test: Fires 5 simultaneous POST /users/employees requests via asyncio.gather()
    and asserts all 5 generated employee_code values are unique and returned with HTTP 201.
    """
    import asyncio

    async def create_one(i: int):
        return await client.post(
            "/users/employees",
            json={"full_name": f"Concurrent User {i}", "email": f"concurrent{i}@example.com"},
            headers=admin_headers,
        )

    responses = await asyncio.gather(*[create_one(i) for i in range(5)])
    for res in responses:
        assert res.status_code == status.HTTP_201_CREATED

    codes = [res.json()["employee_code"] for res in responses]
    assert len(codes) == 5
    assert len(set(codes)) == 5


@pytest.mark.asyncio
async def test_employee_creation_happy_path(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """
    Happy-path regression test:
    Confirm an admin can create an employee, receiving HTTP 201 Created and
    a valid 10-digit numeric employee_code.
    """
    response = await client.post(
        "/users/employees",
        json={
            "full_name": "Happy Path Employee",
            "email": "happy.path@example.com",
            "designation": "Software Engineer",
            "access_level": 3,
        },
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "happy.path@example.com"
    assert data["full_name"] == "Happy Path Employee"
    assert re.match(r"^[0-9]{10}$", data["employee_code"])
    assert data["role"] == "EMPLOYEE"


@pytest.mark.asyncio
async def test_employee_creation_collision_retry_succeeds(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Simulate code collision scenario:
    The database already contains a user with employee_code '1234567890'.
    When the generator produces a colliding code on first attempt, create_employee catches IntegrityError,
    retries using savepoint, and successfully allocates '9876543210' on the second attempt.
    """
    user1 = User(
        full_name="Pre-existing 1",
        email="pre1@example.com",
        hashed_password="hash",
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1234567890",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(user1)
    await db_session.commit()

    generated_codes = iter(["1234567890", "9876543210"])

    with patch(
        "app.services.user_service._generate_next_employee_code",
        side_effect=lambda *args, **kwargs: next(generated_codes),
    ):
        response = await client.post(
            "/users/employees",
            json={"full_name": "Collision Survivor", "email": "survivor@example.com"},
            headers=admin_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["employee_code"] == "9876543210"
        assert data["email"] == "survivor@example.com"


@pytest.mark.asyncio
async def test_employee_creation_desync_exhausts_retries_returns_clean_app_exception(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    When all 10 retry attempts collide, create_employee()
    must raise a clean AppException with status_code=500 rather than letting a raw
    IntegrityError propagate unhandled.
    """
    colliding_user = User(
        full_name="Colliding User",
        email="colliding@example.com",
        hashed_password="hash",
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1234567890",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(colliding_user)
    await db_session.commit()

    with patch(
        "app.services.user_service._generate_next_employee_code",
        return_value="1234567890",
    ):
        response = await client.post(
            "/users/employees",
            json={"full_name": "Exhausted Retries", "email": "exhausted@example.com"},
            headers=admin_headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = response.json().get("detail", "")
        assert "Failed to generate a unique employee code" in detail
        assert "please retry" in detail


@pytest.mark.asyncio
async def test_create_employee_service_raises_app_exception_on_exhausted_retries(
    db_session: AsyncSession,
    test_org: Organization,
) -> None:
    """
    Unit test directly on create_employee():
    Verify that an exhausted retry loop raises AppException with status_code=500.
    """
    colliding_user = User(
        full_name="Colliding Service User",
        email="colliding_service@example.com",
        hashed_password="hash",
        role=UserRole.EMPLOYEE,
        access_level=3,
        employee_code="1234567890",
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(colliding_user)
    await db_session.commit()

    emp_in = EmployeeCreate(
        full_name="Service Test Employee",
        email="service.test@example.com",
    )

    with patch(
        "app.services.user_service._generate_next_employee_code",
        return_value="1234567890",
    ):
        with pytest.raises(AppException) as exc_info:
            await create_employee(db_session, emp_in)

        assert exc_info.value.status_code == 500
        assert "Failed to generate a unique employee code" in exc_info.value.message


@pytest.mark.asyncio
async def test_old_emp_code_rejected_at_login(
    client: AsyncClient,
) -> None:
    """
    Test that legacy EMP-1001 formatted User IDs are rejected with generic invalid credentials error (401)
    and legacy schema payload missing mode/identifier is rejected with 422.
    """
    # 1. Sent as identifier in employee mode -> 401 with Incorrect credentials.
    payload = {
        "identifier": "EMP-1001",
        "password": "anypassword123",
        "mode": "employee",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect credentials."

    # 2. Sent as legacy payload {"employee_code": ..., "password": ...} -> 422 Unprocessable Entity
    legacy_payload = {
        "employee_code": "EMP-1001",
        "password": "anypassword123",
    }
    resp_legacy = await client.post("/auth/login", json=legacy_payload)
    assert resp_legacy.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY



