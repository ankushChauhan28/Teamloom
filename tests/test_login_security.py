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
            json={"identifier": code, "password": wrong_pwd, "mode": "employee"},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.json()["detail"] == "Incorrect credentials."

    # Refresh db instance
    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 5
    assert employee_user.locked_until is not None

    # 2. 6th attempt with CORRECT password fails because account is locked
    res_6th = await client.post(
        "/auth/login",
        json={"identifier": code, "password": correct_pwd, "mode": "employee"},
    )
    assert res_6th.status_code == status.HTTP_401_UNAUTHORIZED
    # Response must be completely indistinguishable from invalid credentials
    assert res_6th.json()["detail"] == "Incorrect credentials."


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
        json={"identifier": code, "password": correct_pwd, "mode": "employee"},
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
            json={"identifier": code, "password": "WrongPassword!", "mode": "employee"},
        )

    await db_session.refresh(employee_user)
    assert employee_user.failed_login_attempts == 3

    # Successful login
    res = await client.post(
        "/auth/login",
        json={"identifier": code, "password": correct_pwd, "mode": "employee"},
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
        json={"identifier": "9999999999", "password": "AnyPassword!", "mode": "employee"},
    )

    # 2. Invalid password
    res_wrong_pwd = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "WrongPassword!", "mode": "employee"},
    )

    # 3. Lock user
    employee_user.failed_login_attempts = 5
    employee_user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db_session.commit()

    res_locked = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )

    # All 3 responses must be identical
    assert res_nonexistent.status_code == status.HTTP_401_UNAUTHORIZED
    assert res_wrong_pwd.status_code == status.HTTP_401_UNAUTHORIZED
    assert res_locked.status_code == status.HTTP_401_UNAUTHORIZED

    assert res_nonexistent.json() == res_wrong_pwd.json() == res_locked.json()
    assert res_locked.json()["detail"] == "Incorrect credentials."


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
            json={"identifier": f"900000000{i}", "password": "InvalidPassword!", "mode": "employee"},
            headers=headers,
        )
        assert res.status_code != status.HTTP_429_TOO_MANY_REQUESTS

    # 11th request from same IP -> 429 Too Many Requests
    res_11th = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
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
            json={"identifier": code, "password": pwd, "mode": "employee"},
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK

    # 11th successful login request from same IP is rate limited
    res_11th = await client.post(
        "/auth/login",
        json={"identifier": code, "password": pwd, "mode": "employee"},
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
        json={"identifier": employee_user.employee_code, "password": "employeepassword123", "mode": "employee"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["employee_code"] == employee_user.employee_code


@pytest.mark.asyncio
async def test_rate_limit_ignores_spoofed_header_without_trusted_proxy(
    client: AsyncClient,
    employee_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    V-02 Test: Ensure attackers cannot bypass rate limiting by rotating X-Forwarded-For
    headers when requests come from an untrusted client IP (TRUSTED_PROXY_IPS is empty).
    All requests are attributed to the direct connection host (127.0.0.1).
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", [])

    for i in range(10):
        res = await client.post(
            "/auth/login",
            json={"identifier": f"900000000{i}", "password": "WrongPassword!", "mode": "employee"},
            headers={"X-Forwarded-For": f"198.51.100.{i}"},
        )
        assert res.status_code != status.HTTP_429_TOO_MANY_REQUESTS

    # 11th request with yet another spoofed IP must still be blocked with 429
    res_11th = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "WrongPassword!", "mode": "employee"},
        headers={"X-Forwarded-For": "198.51.100.254"},
    )
    assert res_11th.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "retry-after" in res_11th.headers


@pytest.mark.asyncio
async def test_rate_limit_uses_forwarded_header_when_proxy_trusted(
    client: AsyncClient,
    employee_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    V-02 Test: When the direct client host is in TRUSTED_PROXY_IPS (e.g. 127.0.0.1),
    extract_client_ip parses X-Forwarded-For and applies rate limiting to the forwarded IP.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["127.0.0.1"])

    client_ip_a = "203.0.113.10"
    client_ip_b = "203.0.113.20"

    # 10 requests from client A behind trusted proxy
    for i in range(10):
        res = await client.post(
            "/auth/login",
            json={"identifier": f"800000000{i}", "password": "WrongPassword!", "mode": "employee"},
            headers={"X-Forwarded-For": f"{client_ip_a}, 127.0.0.1"},
        )
        assert res.status_code != status.HTTP_429_TOO_MANY_REQUESTS

    # 11th request from client A hits 429
    res_a_blocked = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "WrongPassword!", "mode": "employee"},
        headers={"X-Forwarded-For": client_ip_a},
    )
    assert res_a_blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # Request from client B behind same proxy is NOT blocked
    res_b_allowed = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "WrongPassword!", "mode": "employee"},
        headers={"X-Forwarded-For": client_ip_b},
    )
    assert res_b_allowed.status_code != status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_redis_rate_limiter_shares_state_across_instances() -> None:
    """
    V-03 Test: Demonstrates that two separate RedisRateLimiter instances (simulating
    two independent Uvicorn worker processes or cluster nodes) share counter state
    via Redis (tested via fakeredis), preventing horizontal scale rate limiter bypass.
    """
    import fakeredis.aioredis
    from app.core.rate_limit import RedisRateLimiter

    fake_server = fakeredis.FakeServer()
    client_worker1 = fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)
    client_worker2 = fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)

    worker_1 = RedisRateLimiter(max_requests=10, window_seconds=60, redis_client=client_worker1)
    worker_2 = RedisRateLimiter(max_requests=10, window_seconds=60, redis_client=client_worker2)

    # Worker 1 processes 6 requests from IP
    for _ in range(6):
        res = await worker_1.check_and_increment("client-192.168.1.1")
        assert res.allowed is True

    # Worker 2 processes 4 requests from same IP
    for _ in range(4):
        res = await worker_2.check_and_increment("client-192.168.1.1")
        assert res.allowed is True

    # 11th request processed by Worker 1 is BLOCKED because Worker 2 contributed to shared state
    res_11th = await worker_1.check_and_increment("client-192.168.1.1")
    assert res_11th.allowed is False
    assert res_11th.retry_after_seconds > 0

    # Distinct IP processed by Worker 2 is allowed
    res_other = await worker_2.check_and_increment("client-10.0.0.1")
    assert res_other.allowed is True

    # Test reset() functionality
    await worker_1.reset()
    res_after_reset = await worker_2.check_and_increment("client-192.168.1.1")
    assert res_after_reset.allowed is True

    await client_worker1.aclose()
    await client_worker2.aclose()
