"""
Integration & Unit Tests for Authentication Endpoints (/auth/)
Covers Slice 4b: Dual login modes (Admin email / Employee User ID), server-side enforcement,
timing safety, rate limiting, and session lifecycle.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import Request, Response, status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token, hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.routes.auth import login, refresh, swagger_login
from app.schemas.user import UserLogin


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test valid employee login with User ID in employee mode returns access JWT token,
    must_change_password=False, a fully populated user object in JSON body, and refresh token in httpOnly cookie.
    """
    payload = {
        "identifier": employee_user.employee_code,
        "password": "employeepassword123",
        "mode": "employee",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in response.cookies

    # Assert must_change_password flag and populated user object shape
    assert data["must_change_password"] is False
    assert "user" in data and data["user"] is not None
    user_data = data["user"]
    assert user_data["id"] == employee_user.id
    assert user_data["email"] == employee_user.email
    assert user_data["full_name"] == employee_user.full_name
    assert user_data["role"] == employee_user.role.value
    assert user_data["employee_code"] == employee_user.employee_code
    assert user_data["must_change_password"] is False
    assert "created_at" in user_data


@pytest.mark.asyncio
async def test_login_admin_success(client: AsyncClient, admin_user: User) -> None:
    """
    Test valid admin login with email in admin mode returns access JWT token,
    populated user object, and refresh token in cookie.
    """
    payload = {
        "identifier": admin_user.email,
        "password": "adminpassword123",
        "mode": "admin",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == admin_user.email
    assert data["user"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_login_pending_password_change_user_returns_true_flag(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Test logging in as a user with must_change_password=True using User ID in employee mode
    returns must_change_password=True and a fully populated user object in the login response body (B6).
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
            json={"full_name": "Pending Pwd User", "email": "pending.pwd@example.com"},
            headers=admin_headers,
        )
        assert create_res.status_code == status.HTTP_201_CREATED
        temp_pwd = captured_passwords[0]
        emp_code = create_res.json()["employee_code"]

    login_res = await client.post(
        "/auth/login",
        json={"identifier": emp_code, "password": temp_pwd, "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    data = login_res.json()

    assert data["must_change_password"] is True
    assert "user" in data and data["user"] is not None

    user_data = data["user"]
    assert user_data["email"] == "pending.pwd@example.com"
    assert user_data["full_name"] == "Pending Pwd User"
    assert user_data["role"] == "EMPLOYEE"
    assert user_data["employee_code"] == emp_code
    assert user_data["must_change_password"] is True
    assert "created_at" in user_data


@pytest.mark.asyncio
async def test_swagger_login_success(
    client: AsyncClient, employee_user: User, admin_user: User
) -> None:
    """
    Test form-data login endpoint (/auth/swagger-login):
    - Digits username -> automatically treated as employee mode.
    - '@' username -> automatically treated as admin mode.
    """
    # 1. Employee login via Swagger
    data_emp = {
        "username": employee_user.employee_code,
        "password": "employeepassword123",
    }
    response_emp = await client.post("/auth/swagger-login", data=data_emp)
    assert response_emp.status_code == status.HTTP_200_OK
    assert "access_token" in response_emp.json()

    # 2. Admin login via Swagger
    data_admin = {
        "username": admin_user.email,
        "password": "adminpassword123",
    }
    response_admin = await client.post("/auth/swagger-login", data=data_admin)
    assert response_admin.status_code == status.HTTP_200_OK
    assert "access_token" in response_admin.json()


@pytest.mark.asyncio
async def test_swagger_login_wrong_mode_fails_identically(
    client: AsyncClient, employee_user: User, admin_user: User
) -> None:
    """
    Test /auth/swagger-login fails with 401 Incorrect credentials when username format doesn't match account mode:
    - Admin's User ID (digits -> routed to employee mode where access_level > 1 is required) fails with 401.
    - Employee's email ('@' -> routed to admin mode where access_level == 1 is required) fails with 401.
    """
    # Admin User ID -> treated as employee mode
    res1 = await client.post(
        "/auth/swagger-login",
        data={"username": admin_user.employee_code, "password": "adminpassword123"},
    )
    assert res1.status_code == status.HTTP_401_UNAUTHORIZED
    assert res1.json()["detail"] == "Incorrect credentials."

    # Employee email -> treated as admin mode
    res2 = await client.post(
        "/auth/swagger-login",
        data={"username": employee_user.email, "password": "employeepassword123"},
    )
    assert res2.status_code == status.HTTP_401_UNAUTHORIZED
    assert res2.json()["detail"] == "Incorrect credentials."


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, employee_user: User
) -> None:
    """
    Test login with valid User ID but incorrect password returns HTTP 401 with generic error message.
    """
    payload = {
        "identifier": employee_user.employee_code,
        "password": "wrongpassword!",
        "mode": "employee",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect credentials."


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    """
    Test login with a non-existent employee_code returns HTTP 401 with generic error message.
    """
    payload = {
        "identifier": "9999999999",
        "password": "somepassword123",
        "mode": "employee",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect credentials."


# =====================================================================
# B4, B5, B6 ACCEPTANCE SCENARIO TESTS
# =====================================================================


@pytest.mark.asyncio
async def test_scenario_b4_admin_login_lockout_and_recovery(
    client: AsyncClient, admin_user: User, db_session: AsyncSession
) -> None:
    """
    Scenario B4: Admin logs in with email + password in admin mode.
    5 wrong passwords in admin mode lock the account for 15 minutes.
    A correct password during the lock window is rejected with 401 Incorrect credentials.
    """
    email = admin_user.email
    correct_pwd = "adminpassword123"
    wrong_pwd = "WrongAdminPassword!"

    # 1. 5 wrong attempts in admin mode
    for _ in range(5):
        res = await client.post(
            "/auth/login",
            json={"identifier": email, "password": wrong_pwd, "mode": "admin"},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.json()["detail"] == "Incorrect credentials."

    await db_session.refresh(admin_user)
    assert admin_user.failed_login_attempts == 5
    assert admin_user.locked_until is not None

    # 2. 6th attempt with CORRECT password during lock window is rejected
    res_6th = await client.post(
        "/auth/login",
        json={"identifier": email, "password": correct_pwd, "mode": "admin"},
    )
    assert res_6th.status_code == status.HTTP_401_UNAUTHORIZED
    assert res_6th.json()["detail"] == "Incorrect credentials."

    # 3. Simulate lock window expiration -> correct password succeeds and resets lockout
    admin_user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    res_success = await client.post(
        "/auth/login",
        json={"identifier": email, "password": correct_pwd, "mode": "admin"},
    )
    assert res_success.status_code == status.HTTP_200_OK

    await db_session.refresh(admin_user)
    assert admin_user.failed_login_attempts == 0
    assert admin_user.locked_until is None


@pytest.mark.asyncio
async def test_scenario_b5_cross_mode_credentials_rejected_identically(
    client: AsyncClient, admin_user: User, employee_user: User
) -> None:
    """
    Scenario B5: Cross-mode logins fail with exact identical status code (401) and detail ("Incorrect credentials."):
    1. Admin email in employee mode.
    2. Admin User ID in employee mode.
    3. Employee email in admin mode.
    4. Employee User ID in admin mode.
    """
    # 1. Admin email in employee mode
    r1 = await client.post(
        "/auth/login",
        json={"identifier": admin_user.email, "password": "adminpassword123", "mode": "employee"},
    )
    # 2. Admin User ID in employee mode
    r2 = await client.post(
        "/auth/login",
        json={"identifier": admin_user.employee_code, "password": "adminpassword123", "mode": "employee"},
    )
    # 3. Employee email in admin mode
    r3 = await client.post(
        "/auth/login",
        json={"identifier": employee_user.email, "password": "employeepassword123", "mode": "admin"},
    )
    # 4. Employee User ID in admin mode
    r4 = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "admin"},
    )

    for resp in [r1, r2, r3, r4]:
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp.json() == {"detail": "Incorrect credentials."}


@pytest.mark.asyncio
async def test_wrong_mode_attempts_do_not_increment_failed_attempts_or_lock(
    client: AsyncClient, admin_user: User, employee_user: User, db_session: AsyncSession
) -> None:
    """
    Wrong-mode login attempts are filtered out at the DB query level and behave as 'user not found'.
    Submitting 10 wrong-mode attempts in a row against an account does NOT increment failed_login_attempts
    and never locks the real account.
    """
    # 10 wrong-mode attempts for admin (trying employee mode)
    for _ in range(10):
        await client.post(
            "/auth/login",
            json={"identifier": admin_user.employee_code, "password": "adminpassword123", "mode": "employee"},
        )

    await db_session.refresh(admin_user)
    assert admin_user.failed_login_attempts == 0
    assert admin_user.locked_until is None

    # 10 wrong-mode attempts for employee (trying admin mode)
    for _ in range(10):
        await client.post(
            "/auth/login",
            json={"identifier": employee_user.email, "password": "employeepassword123", "mode": "admin"},
        )

    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 0
    assert employee_user.locked_until is None


@pytest.mark.asyncio
async def test_timing_safety_dummy_bcrypt_execution(
    db_session: AsyncSession, admin_user: User, employee_user: User
) -> None:
    """
    Timing Safety: Verifies that verify_password runs exactly once across all failure and success paths:
    1. Unknown user (runs with DUMMY_HASH)
    2. Wrong mode (runs with DUMMY_HASH)
    3. Inactive user (runs with user's hash)
    4. Locked user (runs with user's hash)
    5. Wrong password path (runs with user's hash)
    6. Correct password path (runs with user's hash)
    """
    from app.services import auth_service

    # Setup inactive user
    employee_user.is_active = False
    await db_session.commit()

    # 1. Unknown user path
    with patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_v:
        with pytest.raises(Exception):
            await auth_service.authenticate_user(
                db=db_session,
                login_in=UserLogin(identifier="9999999999", password="pwd", mode="employee"),
            )
        assert mock_v.call_count == 1

    # 2. Wrong mode path (admin User ID in employee mode -> not found)
    with patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_v:
        with pytest.raises(Exception):
            await auth_service.authenticate_user(
                db=db_session,
                login_in=UserLogin(identifier=admin_user.employee_code, password="pwd", mode="employee"),
            )
        assert mock_v.call_count == 1

    # 3. Inactive user path
    with patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_v:
        with pytest.raises(Exception):
            await auth_service.authenticate_user(
                db=db_session,
                login_in=UserLogin(identifier=employee_user.employee_code, password="pwd", mode="employee"),
            )
        assert mock_v.call_count == 1

    # Restore active state and lock user
    employee_user.is_active = True
    employee_user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db_session.commit()

    # 4. Locked user path
    with patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_v:
        with pytest.raises(Exception):
            await auth_service.authenticate_user(
                db=db_session,
                login_in=UserLogin(identifier=employee_user.employee_code, password="pwd", mode="employee"),
            )
        assert mock_v.call_count == 1

    # Unlock user
    employee_user.locked_until = None
    await db_session.commit()

    # 5. Wrong password path
    with patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_v:
        with pytest.raises(Exception):
            await auth_service.authenticate_user(
                db=db_session,
                login_in=UserLogin(identifier=employee_user.employee_code, password="wrong", mode="employee"),
            )
        assert mock_v.call_count == 1

    # 6. Correct password path
    with patch("app.services.auth_service.verify_password", wraps=auth_service.verify_password) as mock_v:
        user = await auth_service.authenticate_user(
            db=db_session,
            login_in=UserLogin(identifier=employee_user.employee_code, password="employeepassword123", mode="employee"),
        )
        assert user.id == employee_user.id
        assert mock_v.call_count == 1


@pytest.mark.asyncio
async def test_scenario_x8_second_tier1_admin_login(
    client: AsyncClient, db_session: AsyncSession, test_org: Organization
) -> None:
    """
    Scenario X8: A second Tier-1 Admin (access_level=1) in an organization
    logs in with their own email in admin mode.
    """
    second_admin = User(
        full_name="Second Tier1 Admin",
        email="second.admin@company.com",
        hashed_password=hash_password("secondadmin123"),
        role=UserRole.ADMIN,
        access_level=1,
        employee_code="1000000099",
        is_email_verified=True,
        must_change_password=False,
        organization_id=test_org.id,
    )
    db_session.add(second_admin)
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"identifier": "second.admin@company.com", "password": "secondadmin123", "mode": "admin"},
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["user"]["email"] == "second.admin@company.com"
    assert res.json()["user"]["access_level"] == 1


@pytest.mark.asyncio
async def test_admin_email_login_case_insensitivity_and_whitespace_trimming(
    client: AsyncClient, admin_user: User
) -> None:
    """
    Admin email login is case-insensitive and whitespace-trimmed.
    """
    email_variants = [
        f"  {admin_user.email}  ",
        admin_user.email.upper(),
        f"  {admin_user.email.title()} ",
    ]
    for variant in email_variants:
        res = await client.post(
            "/auth/login",
            json={"identifier": variant, "password": "adminpassword123", "mode": "admin"},
        )
        assert res.status_code == status.HTTP_200_OK, f"Failed for email variant: {variant}"
        assert res.json()["user"]["email"] == admin_user.email


@pytest.mark.asyncio
async def test_missing_or_invalid_mode_returns_422(
    client: AsyncClient, employee_user: User
) -> None:
    """
    POST /auth/login returns 422 if mode is missing or not 'admin' / 'employee'.
    """
    # 1. Missing mode
    r_missing = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123"},
    )
    assert r_missing.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Invalid mode
    r_invalid = await client.post(
        "/auth/login",
        json={
            "identifier": employee_user.employee_code,
            "password": "employeepassword123",
            "mode": "superadmin",
        },
    )
    assert r_invalid.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Legacy payload format {"employee_code": ..., "password": ...}
    r_legacy = await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
    )
    assert r_legacy.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =====================================================================
# SESSION & TOKEN LIFECYCLE TESTS
# =====================================================================


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test exchanging a valid refresh token cookie for a new access token and rotated refresh token cookie.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    assert "refresh_token" in client.cookies

    response = await client.post("/auth/refresh")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_refresh_missing_cookie_returns_401(client: AsyncClient) -> None:
    """
    Test calling refresh without a refresh_token cookie returns HTTP 401 Unauthorized.
    """
    response = await client.post("/auth/refresh")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "refresh token cookie missing" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_invalid_jwt_returns_401(client: AsyncClient) -> None:
    """
    Test calling refresh with an invalid refresh_token cookie returns HTTP 401 Unauthorized.
    """
    client.cookies.set("refresh_token", "invalid.token.str", path="/auth")
    response = await client.post("/auth/refresh")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid refresh token" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_expired_jwt_returns_401(client: AsyncClient, employee_user: User) -> None:
    """
    Test calling refresh with an expired refresh_token cookie returns HTTP 401 Unauthorized.
    """
    expired_token = create_refresh_token(
        email=employee_user.email,
        role=employee_user.role.value,
        expires_delta=timedelta(seconds=-10),
    )
    client.cookies.set("refresh_token", expired_token, path="/auth")
    response = await client.post("/auth/refresh")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "refresh token has expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout_user_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test logging out clears the refresh_token cookie and revokes the token server-side.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert "refresh_token" in client.cookies
    access_token = login_res.json()["access_token"]

    response = await client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Logged out successfully"
    assert "refresh_token" not in client.cookies


@pytest.mark.asyncio
async def test_logout_revokes_token_immediately(client: AsyncClient, employee_user: User) -> None:
    """
    Test that after logout, attempting to call /auth/refresh with the revoked token returns HTTP 401.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    stolen_token = client.cookies.get("refresh_token")
    assert stolen_token is not None
    access_token = login_res.json()["access_token"]

    # Perform logout
    logout_res = await client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_res.status_code == status.HTTP_200_OK

    # Attempt to reuse the token after logout
    client.cookies.set("refresh_token", stolen_token, path="/auth")
    refresh_res = await client.post("/auth/refresh")
    assert refresh_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in refresh_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stolen_token_after_logout_rejected(
    client: AsyncClient, employee_user: User
) -> None:
    """
    Test that an attacker using a stolen refresh token after the victim logged out is rejected.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    stolen_token = client.cookies.get("refresh_token")
    assert stolen_token is not None
    access_token = login_res.json()["access_token"]

    # User logs out
    await client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})

    # Attacker uses stolen token
    client.cookies.set("refresh_token", stolen_token, path="/auth")
    attack_res = await client.post("/auth/refresh")
    assert attack_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in attack_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_revocation_idempotency_and_cleanup(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Test that calling revoke_token multiple times is idempotent and cleanup_expired_revocations works cleanly.
    """
    from app.services.auth_service import cleanup_expired_revocations, revoke_token

    token = create_refresh_token(email=employee_user.email, role=employee_user.role.value)

    # First revocation
    await revoke_token(db=db_session, token=token)
    # Second revocation (idempotent duplicate call)
    await revoke_token(db=db_session, token=token)

    # Cleanup job call
    cleaned = await cleanup_expired_revocations(db=db_session)
    assert isinstance(cleaned, int)


@pytest.mark.asyncio
async def test_unit_direct_auth_routes_execution(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Direct unit test calling route handlers asynchronously for complete coverage tracing.
    """
    req = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 12345)})
    response = Response()
    login_in = UserLogin(
        identifier=employee_user.employee_code,
        password="employeepassword123",
        mode="employee",
    )
    res_login = await login(login_in=login_in, request=req, response=response, db=db_session)
    assert res_login.access_token is not None

    class FormStub:
        username = employee_user.employee_code
        password = "employeepassword123"

    res_swagger = await swagger_login(
        request=req, response=response, form_data=FormStub(), db=db_session
    )
    assert res_swagger.access_token is not None

    cookie_token = create_refresh_token(email=employee_user.email, role=employee_user.role.value)
    req = Request(
        {"type": "http", "headers": [(b"cookie", f"refresh_token={cookie_token}".encode())]}
    )
    res_refresh = await refresh(request=req, response=response, db=db_session)
    assert res_refresh.access_token is not None


@pytest.mark.asyncio
async def test_access_token_revoked_after_logout_employee(
    client: AsyncClient, employee_user: User
) -> None:
    """
    QA Regression (a):
    Capture an access token, log out, replay the same access token against protected endpoint
    (/users/me) -> must be rejected (401), not 200.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    access_token = login_res.json()["access_token"]

    # Verify protected endpoint works before logout
    pre_res = await client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert pre_res.status_code == status.HTTP_200_OK

    # Log out
    logout_res = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_res.status_code == status.HTTP_200_OK

    # Replay same access token against protected endpoint -> must return 401
    post_res = await client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert post_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in post_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_token_revoked_after_logout_employee(
    client: AsyncClient, employee_user: User
) -> None:
    """
    QA Regression (b):
    Capture a refresh_token cookie, log out, replay it against /auth/refresh
    -> must be rejected (401), not issue new tokens.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    access_token = login_res.json()["access_token"]
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token is not None

    # Log out
    logout_res = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_res.status_code == status.HTTP_200_OK

    # Replay refresh token against /auth/refresh -> must return 401
    client.cookies.set("refresh_token", refresh_token, path="/auth")
    refresh_res = await client.post("/auth/refresh")
    assert refresh_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in refresh_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout_revocation_admin_tier(
    client: AsyncClient, admin_user: User
) -> None:
    """
    QA Regression (c):
    Repeat access token and refresh token revocation verification for an Admin-tier user
    to confirm the fix is not tier-specific.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": admin_user.email, "password": "adminpassword123", "mode": "admin"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    access_token = login_res.json()["access_token"]
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token is not None

    # Verify protected endpoint works before logout
    pre_res = await client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert pre_res.status_code == status.HTTP_200_OK

    # Log out admin
    logout_res = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_res.status_code == status.HTTP_200_OK

    # 1. Admin access token replayed -> 401
    post_res = await client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert post_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in post_res.json()["detail"].lower()

    # 2. Admin refresh token replayed -> 401
    client.cookies.set("refresh_token", refresh_token, path="/auth")
    refresh_res = await client.post("/auth/refresh")
    assert refresh_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in refresh_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_old_refresh_token_rejected_post_rotation(
    client: AsyncClient, employee_user: User
) -> None:
    """
    QA Regression (d):
    After a successful token refresh, replay the OLD (pre-rotation) refresh token
    against /auth/refresh -> must be rejected (401), while the NEW refresh token succeeds.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    old_refresh_token = client.cookies.get("refresh_token")
    assert old_refresh_token is not None

    # Rotate refresh token
    refresh_res_1 = await client.post("/auth/refresh")
    assert refresh_res_1.status_code == status.HTTP_200_OK
    new_refresh_token = client.cookies.get("refresh_token")
    assert new_refresh_token is not None
    assert new_refresh_token != old_refresh_token

    # Replay OLD (pre-rotation) refresh token -> must be rejected with 401
    client.cookies.set("refresh_token", old_refresh_token, path="/auth")
    replay_old_res = await client.post("/auth/refresh")
    assert replay_old_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in replay_old_res.json()["detail"].lower()

    # The NEW refresh token should still be valid
    client.cookies.set("refresh_token", new_refresh_token, path="/auth")
    valid_res = await client.post("/auth/refresh")
    assert valid_res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_logout_without_access_token_returns_401(client: AsyncClient) -> None:
    """
    Verify that calling /auth/logout without a valid access token returns HTTP 401.
    """
    response = await client.post("/auth/logout")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_without_refresh_cookie_still_revokes_access_token(
    client: AsyncClient, employee_user: User
) -> None:
    """
    Verify that if an API client logs out with only Bearer access token (no cookie present),
    the access token is still revoked server-side.
    """
    login_res = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    access_token = login_res.json()["access_token"]

    # Clear cookie before logout
    client.cookies.clear()

    # Logout with Bearer token only
    logout_res = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_res.status_code == status.HTTP_200_OK

    # Verify access token is revoked
    post_res = await client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert post_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in post_res.json()["detail"].lower()
