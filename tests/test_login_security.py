"""
Security Integration Tests for Account Lockout & IP Rate Limiting (/auth/login)
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import _limiter_instance
from app.models.user import User


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Resets the in-memory rate limiter state before every test."""
    _limiter_instance.reset()
    yield
    _limiter_instance.reset()


@pytest.mark.asyncio
async def test_account_lockout_after_five_failed_attempts(
    client: AsyncClient,
    employee_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Test 5 consecutive failed logins lock the account.
    6th attempt with correct password fails with HTTP 401 generic message.
    """
    code = employee_user.employee_code
    correct_pwd = "employeepassword123"
    wrong_pwd = "WrongPassword123!"

    # 1. Submit 5 failed login attempts
    for i in range(5):
        res = await client.post(
            "/auth/login",
            json={"employee_code": code, "password": wrong_pwd},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.json()["detail"] == "Incorrect employee ID or password."

    # Refresh db instance
    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 5
    assert employee_user.locked_until is not None

    # 2. 6th attempt with CORRECT password fails because account is locked
    res_6th = await client.post(
        "/auth/login",
        json={"employee_code": code, "password": correct_pwd},
    )
    assert res_6th.status_code == status.HTTP_401_UNAUTHORIZED
    # Response must be completely indistinguishable from invalid credentials
    assert res_6th.json()["detail"] == "Incorrect employee ID or password."


@pytest.mark.asyncio
async def test_account_unlocks_after_lockout_window_passes(
    client: AsyncClient,
    employee_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Test after lockout window passes, logging in with correct password succeeds
    and resets failed_login_attempts to 0 and locked_until to None.
    """
    code = employee_user.employee_code
    correct_pwd = "employeepassword123"

    # Manually simulate a locked user with locked_until in the past (1 minute ago)
    employee_user.failed_login_attempts = 5
    employee_user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    # Attempt login with correct password
    res = await client.post(
        "/auth/login",
        json={"employee_code": code, "password": correct_pwd},
    )
    assert res.status_code == status.HTTP_200_OK
    assert "access_token" in res.json()

    # Verify lockout counter and timestamp reset
    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 0
    assert employee_user.locked_until is None


@pytest.mark.asyncio
async def test_successful_login_resets_failed_attempt_counter(
    client: AsyncClient,
    employee_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Test successful login clears failed_login_attempts counter back to 0.
    """
    code = employee_user.employee_code
    correct_pwd = "employeepassword123"

    # 3 failed attempts
    for _ in range(3):
        await client.post(
            "/auth/login",
            json={"employee_code": code, "password": "WrongPassword!"},
        )

    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 3

    # Successful login
    res = await client.post(
        "/auth/login",
        json={"employee_code": code, "password": correct_pwd},
    )
    assert res.status_code == status.HTTP_200_OK

    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 0


@pytest.mark.asyncio
async def test_indistinguishable_locked_versus_invalid_credentials_responses(
    client: AsyncClient,
    employee_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Test responses for wrong password, locked account, and non-existent employee ID
    are exact identical (status code 401 and detail string).
    """
    # 1. Non-existent employee ID
    res_nonexistent = await client.post(
        "/auth/login",
        json={"employee_code": "EMP-9999", "password": "AnyPassword!"},
    )

    # 2. Invalid password
    res_wrong_pwd = await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "WrongPassword!"},
    )

    # 3. Lock user
    employee_user.failed_login_attempts = 5
    employee_user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db_session.commit()

    res_locked = await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
    )

    # All 3 responses must be identical
    assert res_nonexistent.status_code == status.HTTP_401_UNAUTHORIZED
    assert res_wrong_pwd.status_code == status.HTTP_401_UNAUTHORIZED
    assert res_locked.status_code == status.HTTP_401_UNAUTHORIZED

    assert res_nonexistent.json() == res_wrong_pwd.json() == res_locked.json()
    assert res_locked.json()["detail"] == "Incorrect employee ID or password."


@pytest.mark.asyncio
async def test_ip_rate_limiting_exceeded_returns_429(
    client: AsyncClient,
    employee_user: User,
) -> None:
    """
    Test 11th request from same IP returns HTTP 429 Too Many Requests
    and sets Retry-After response header.
    """
    headers = {"X-Forwarded-For": "192.168.1.100"}

    # Send 10 login requests from IP 192.168.1.100
    for i in range(10):
        res = await client.post(
            "/auth/login",
            json={"employee_code": f"EMP-100{i}", "password": "InvalidPassword!"},
            headers=headers,
        )
        assert res.status_code != status.HTTP_429_TOO_MANY_REQUESTS

    # 11th request from same IP -> 429 Too Many Requests
    res_11th = await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
        headers=headers,
    )
    assert res_11th.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "retry-after" in res_11th.headers
    assert res_11th.headers["retry-after"].isdigit()
    assert "Too many login attempts" in res_11th.json()["detail"]


@pytest.mark.asyncio
async def test_successful_logins_count_towards_ip_rate_limit(
    client: AsyncClient,
    employee_user: User,
) -> None:
    """
    Test that SUCCESSFUL logins also increment the per-IP rate limit counter.
    10 successful logins from an IP cause the 11th login attempt (even valid) to return HTTP 429.
    """
    headers = {"X-Forwarded-For": "10.10.10.10"}
    code = employee_user.employee_code
    pwd = "employeepassword123"

    # Send 10 SUCCESSFUL login requests from IP 10.10.10.10
    for _ in range(10):
        res = await client.post(
            "/auth/login",
            json={"employee_code": code, "password": pwd},
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK

    # 11th successful login request from same IP is rate limited
    res_11th = await client.post(
        "/auth/login",
        json={"employee_code": code, "password": pwd},
        headers=headers,
    )
    assert res_11th.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "retry-after" in res_11th.headers
    assert "Too many login attempts" in res_11th.json()["detail"]


@pytest.mark.asyncio
async def test_fresh_user_with_correct_credentials_logs_in_successfully(
    client: AsyncClient,
    employee_user: User,
) -> None:
    """
    Step 3 Test: Confirms an un-locked user with zero prior failed attempts
    and valid credentials logs in successfully with HTTP 200 and access_token.
    """
    res = await client.post(
        "/auth/login",
        json={"employee_code": employee_user.employee_code, "password": "employeepassword123"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["employee_code"] == employee_user.employee_code
