"""
Integration & Unit Tests for Authentication Endpoints (/auth/)
"""

from datetime import timedelta

import pytest
from fastapi import Request, Response, status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token
from app.models.user import User
from app.routes.auth import login, refresh, swagger_login
from app.schemas.user import UserLogin


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test valid user login with employee_code returns access JWT token, must_change_password=False,
    and a fully populated user object in JSON body, and refresh token in httpOnly cookie.
    """
    payload = {
        "employee_code": employee_user.employee_code,
        "password": "employeepassword123",
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
async def test_login_pending_password_change_user_returns_true_flag(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """
    Test logging in as a user with must_change_password=True using employee_code
    returns must_change_password=True and a fully populated user object in the login response body.
    """
    from unittest.mock import patch

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
        json={"employee_code": emp_code, "password": temp_pwd},
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
async def test_swagger_login_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test form-data login endpoint (/auth/swagger-login) with employee_code username returns access token.
    """
    data = {
        "username": employee_user.employee_code,
        "password": "employeepassword123",
    }
    response = await client.post("/auth/swagger-login", data=data)
    assert response.status_code == status.HTTP_200_OK

    res_data = response.json()
    assert "access_token" in res_data
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, employee_user: User
) -> None:
    """
    Test login with valid employee_code but incorrect password returns HTTP 401 with generic error message.
    """
    payload = {
        "employee_code": employee_user.employee_code,
        "password": "wrongpassword!",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect employee ID or password."


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    """
    Test login with a non-existent employee_code returns HTTP 401 with generic error message.
    """
    payload = {
        "employee_code": "EMP-9999",
        "password": "somepassword123",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect employee ID or password."


@pytest.mark.asyncio
async def test_login_with_email_in_employee_code_field_fails_cleanly(
    client: AsyncClient, employee_user: User
) -> None:
    """
    Test passing an email address in the employee_code field fails cleanly with HTTP 401 generic error.
    """
    payload = {
        "employee_code": employee_user.email,
        "password": "employeepassword123",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect employee ID or password."


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test exchanging a valid refresh token cookie for a new access token and rotated refresh token cookie.
    """
    login_res = await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
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
    await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
    )
    assert "refresh_token" in client.cookies

    response = await client.post("/auth/logout")
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
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    stolen_token = client.cookies.get("refresh_token")
    assert stolen_token is not None

    # Perform logout
    logout_res = await client.post("/auth/logout")
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
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    stolen_token = client.cookies.get("refresh_token")
    assert stolen_token is not None

    # User logs out
    await client.post("/auth/logout")

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
    login_in = UserLogin(employee_code=employee_user.employee_code, password="employeepassword123")
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
async def test_cleanup_job_removes_only_expired_tokens(
    db_session: AsyncSession,
) -> None:
    """
    Test that cleanup_expired_revocations prunes only tokens whose exp_timestamp is in the past,
    leaving unexpired/active tokens untouched in the revoked_tokens table.
    Also verifies start_scheduler and shutdown_scheduler execute cleanly.
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from app.models.revoked_token import RevokedToken
    from app.services.auth_service import cleanup_expired_revocations
    from app.core.scheduler import start_scheduler, shutdown_scheduler

    now = datetime.now(timezone.utc)
    expired_token = RevokedToken(
        token_jti="test-expired-jti-12345",
        exp_timestamp=now - timedelta(hours=2),
    )
    valid_token = RevokedToken(
        token_jti="test-valid-jti-67890",
        exp_timestamp=now + timedelta(days=7),
    )
    db_session.add_all([expired_token, valid_token])
    await db_session.commit()

    # Verify both exist before cleanup
    res_before = await db_session.execute(
        select(RevokedToken).where(
            RevokedToken.token_jti.in_(["test-expired-jti-12345", "test-valid-jti-67890"])
        )
    )
    assert len(res_before.scalars().all()) == 2

    # Execute cleanup
    deleted_count = await cleanup_expired_revocations(db_session)
    assert deleted_count >= 1

    # Verify only the valid token remains
    res_after = await db_session.execute(
        select(RevokedToken).where(
            RevokedToken.token_jti.in_(["test-expired-jti-12345", "test-valid-jti-67890"])
        )
    )
    remaining = res_after.scalars().all()
    assert len(remaining) == 1
    assert remaining[0].token_jti == "test-valid-jti-67890"

    # Verify scheduler start and clean shutdown lifecycle
    start_scheduler()
    shutdown_scheduler()


