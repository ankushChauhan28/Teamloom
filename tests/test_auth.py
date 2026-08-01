"""
Integration Tests for Authentication Endpoints (/auth/)
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from app.models.user import User


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
    Test valid user login returns access and refresh JWT tokens.
    """
    payload = {
        "email": employee_user.email,
        "password": "employeepassword123",
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


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
    Test exchanging a valid refresh token for a new access token.
    """
    login_res = await client.post(
        "/auth/login",
        json={"email": employee_user.email, "password": "employeepassword123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert data["refresh_token"] == refresh_token


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client: AsyncClient) -> None:
    """
    Test sending an invalid refresh token returns HTTP 401 Unauthorized.
    """
    response = await client.post("/auth/refresh", json={"refresh_token": "invalid.jwt.token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
