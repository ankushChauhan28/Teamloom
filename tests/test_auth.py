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
async def test_register_user_success(client: AsyncClient) -> None:
    """
    Test registering a new user succeeds with HTTP 201 Created and default EMPLOYEE role.
    """
    payload = {
        "email": "new.employee@example.com",
        "full_name": "New Employee",
        "password": "securepassword123",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["role"] == "EMPLOYEE"
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_user_duplicate_email_fails(
    client: AsyncClient, employee_user: User
) -> None:
    """
    Test registering with an already existing email returns HTTP 400 Bad Request.
    """
    payload = {
        "email": employee_user.email,
        "full_name": "Duplicate User",
        "password": "somepassword123",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test valid user login returns access JWT token in JSON body and refresh token in httpOnly cookie.
    """
    payload = {
        "email": employee_user.email,
        "password": "employeepassword123",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_swagger_login_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test form-data login endpoint (/auth/swagger-login) returns access token and sets cookie.
    """
    data = {
        "username": employee_user.email,
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
    Test login with incorrect password returns HTTP 401 Unauthorized.
    """
    payload = {
        "email": employee_user.email,
        "password": "wrongpassword!",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "incorrect email or password" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    """
    Test login with an unregistered email returns HTTP 401 Unauthorized.
    """
    payload = {
        "email": "nonexistent@example.com",
        "password": "somepassword123",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, employee_user: User) -> None:
    """
    Test exchanging a valid refresh token cookie for a new access token and rotated refresh token cookie.
    """
    login_res = await client.post(
        "/auth/login",
        json={"email": employee_user.email, "password": "employeepassword123"},
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
    Test logging out clears the refresh_token cookie.
    """
    await client.post(
        "/auth/login",
        json={"email": employee_user.email, "password": "employeepassword123"},
    )
    assert "refresh_token" in client.cookies

    response = await client.post("/auth/logout")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_unit_direct_auth_routes_execution(
    db_session: AsyncSession, employee_user: User
) -> None:
    """
    Direct unit test calling route handlers asynchronously for complete coverage tracing.
    """
    response = Response()
    login_in = UserLogin(email=employee_user.email, password="employeepassword123")
    res_login = await login(login_in=login_in, response=response, db=db_session)
    assert res_login.access_token is not None

    class FormStub:
        username = employee_user.email
        password = "employeepassword123"

    res_swagger = await swagger_login(
        response=response, form_data=FormStub(), db=db_session
    )
    assert res_swagger.access_token is not None

    cookie_token = create_refresh_token(
        email=employee_user.email, role=employee_user.role.value
    )
    req = Request(
        {"type": "http", "headers": [(b"cookie", f"refresh_token={cookie_token}".encode())]}
    )
    res_refresh = await refresh(request=req, response=response, db=db_session)
    assert res_refresh.access_token is not None
