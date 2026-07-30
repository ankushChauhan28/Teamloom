"""
Integration Tests for Authentication Endpoints (/auth/)

EDUCATIONAL EXPLANATION - INTEGRATION TESTING & ASSERTIONS:
------------------------------------------------------------
1. What is an Integration Test?
   Integration tests verify how multiple layers (HTTP routing, Pydantic validation,
   security dependencies, and database sessions) work together seamlessly.

2. Why use Python `assert` statements?
   Unlike manual print scripts that output string messages, Pytest uses standard Python
   `assert` statements. If an assertion fails, Pytest inspects the AST and provides a detailed
   diff of expected vs actual values.
"""

from fastapi import status
from fastapi.testclient import TestClient

from app.models.user import User


def test_register_user_success(client: TestClient) -> None:
    """
    Test registering a new user succeeds with HTTP 201 Created and default EMPLOYEE role.
    """
    payload = {
        "email": "new.employee@example.com",
        "full_name": "New Employee",
        "password": "securepassword123",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["role"] == "EMPLOYEE"
    assert "id" in data
    assert "password" not in data  # Ensure raw password is never leaked in response


def test_register_user_duplicate_email_fails(client: TestClient, employee_user: User) -> None:
    """
    Test registering with an already existing email returns HTTP 400 Bad Request.
    """
    payload = {
        "email": employee_user.email,  # Already created by employee_user fixture
        "full_name": "Duplicate User",
        "password": "somepassword123",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"].lower()


def test_login_user_success(client: TestClient, employee_user: User) -> None:
    """
    Test valid user login returns access and refresh JWT tokens.
    """
    payload = {
        "email": employee_user.email,
        "password": "employeepassword123",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_wrong_password_returns_401(client: TestClient, employee_user: User) -> None:
    """
    Test login with incorrect password returns HTTP 401 Unauthorized.
    """
    payload = {
        "email": employee_user.email,
        "password": "wrongpassword!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "incorrect email or password" in response.json()["detail"].lower()


def test_login_nonexistent_user_returns_401(client: TestClient) -> None:
    """
    Test login with an unregistered email returns HTTP 401 Unauthorized.
    """
    payload = {
        "email": "nonexistent@example.com",
        "password": "somepassword123",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_token_success(client: TestClient, employee_user: User) -> None:
    """
    Test exchanging a valid refresh token for a new access token.
    """
    # 1. Login to retrieve refresh token
    login_res = client.post(
        "/auth/login",
        json={"email": employee_user.email, "password": "employeepassword123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # 2. Exchange refresh token
    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert data["refresh_token"] == refresh_token


def test_refresh_invalid_token_returns_401(client: TestClient) -> None:
    """
    Test sending an invalid refresh token returns HTTP 401 Unauthorized.
    """
    response = client.post("/auth/refresh", json={"refresh_token": "invalid.jwt.token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
