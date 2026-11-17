"""
Unit and Integration Tests for Level 1 Rate Limiting Architecture.

Covers:
1. Compound key limit triggers per identifier.
2. Two different identifiers behind the same IP do not block each other (NAT defense).
3. Per-IP ceiling triggers when spraying across many identifiers (spray defense).
4. Window expiry resets counters with controllable clock (no real sleeps).
5. Retry-After calculation matches elapsed window state.
6. Stale-key cleanup removes expired entries from in-memory storage.
7. HTTP 429 response body is identical for existing and non-existing identifiers.
8. RateLimiter interface can be swapped with a fake implementation via FastAPI dependency override.
9. extract_client_ip respects TRUSTED_PROXY_IPS and rejects spoofed headers.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.config import settings
from app.core.rate_limit import (
    InMemoryRateLimiter,
    RateLimiter,
    RateLimitResult,
    extract_client_ip,
    get_rate_limiter,
)
from app.main import app
from app.models.user import User


class ControllableClock:
    """Deterministic controllable clock for testing sliding windows without sleeps."""

    def __init__(self, start_time: float = 1000.0):
        self.current_time = start_time

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


class FakeRateLimiter(RateLimiter):
    """Fake RateLimiter implementation to prove the interface is swappable."""

    def __init__(self, allow_all: bool = True):
        self.allow_all = allow_all
        self.calls: list[dict] = []

    async def check_and_increment(
        self,
        key: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        self.calls.append({"key": key, "max_requests": max_requests, "window_seconds": window_seconds})
        if self.allow_all:
            return RateLimitResult(allowed=True, retry_after_seconds=0)
        return RateLimitResult(allowed=False, retry_after_seconds=42)

    def reset(self) -> None:
        self.calls.clear()

    def cleanup(self) -> int:
        return 0


# ===========================================================================
# 1. Unit Tests for InMemoryRateLimiter with Controllable Clock
# ===========================================================================


@pytest.mark.asyncio
async def test_compound_key_limit_triggers_per_identifier() -> None:
    """Compound key {client IP, identifier} triggers 429 after 10 attempts."""
    clock = ControllableClock(start_time=1000.0)
    limiter = InMemoryRateLimiter(clock=clock)

    # 10 attempts for user1 are allowed
    for i in range(10):
        res = await limiter.check_auth_rate_limit(
            client_ip="192.168.1.1",
            identifier="user1@example.com",
            endpoint_prefix="login",
            compound_limit=10,
            compound_window=900,
            ip_limit=100,
            ip_window=900,
        )
        assert res.allowed is True
        assert res.retry_after == 0

    # 11th attempt for user1 is rejected
    res_11th = await limiter.check_auth_rate_limit(
        client_ip="192.168.1.1",
        identifier="user1@example.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert res_11th.allowed is False
    assert res_11th.retry_after == 900


@pytest.mark.asyncio
async def test_two_different_identifiers_behind_same_ip_do_not_block_each_other() -> None:
    """
    Office NAT Defense:
    Two distinct users behind the same public IP address maintain separate compound counters.
    User A being locked out does not prevent User B from logging in.
    """
    clock = ControllableClock(start_time=1000.0)
    limiter = InMemoryRateLimiter(clock=clock)
    shared_ip = "198.51.100.50"

    # User A exhausts their 10 attempts
    for _ in range(10):
        res = await limiter.check_auth_rate_limit(
            client_ip=shared_ip,
            identifier="alice@company.com",
            endpoint_prefix="login",
            compound_limit=10,
            compound_window=900,
            ip_limit=100,
            ip_window=900,
        )
        assert res.allowed is True

    # 11th attempt for Alice is blocked
    alice_blocked = await limiter.check_auth_rate_limit(
        client_ip=shared_ip,
        identifier="alice@company.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert alice_blocked.allowed is False

    # User B on the same IP is completely unaffected (attempt 1 of 10)
    bob_allowed = await limiter.check_auth_rate_limit(
        client_ip=shared_ip,
        identifier="bob@company.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert bob_allowed.allowed is True
    assert bob_allowed.retry_after == 0


@pytest.mark.asyncio
async def test_per_ip_ceiling_triggers_when_spraying_across_many_identifiers() -> None:
    """
    Password Spraying Defense:
    An attacker spraying credentials across 100 different user accounts from the same IP
    triggers the looser IP ceiling limit (100 attempts / 15 min), blocking further attempts.
    """
    clock = ControllableClock(start_time=1000.0)
    limiter = InMemoryRateLimiter(clock=clock)
    attacker_ip = "203.0.113.88"

    # Spray 100 requests across 100 different identifiers
    for i in range(100):
        res = await limiter.check_auth_rate_limit(
            client_ip=attacker_ip,
            identifier=f"target_user_{i}@victim.com",
            endpoint_prefix="login",
            compound_limit=10,
            compound_window=900,
            ip_limit=100,
            ip_window=900,
        )
        assert res.allowed is True

    # 101st request with a brand-new identifier is rejected by the IP ceiling
    sprayed_101st = await limiter.check_auth_rate_limit(
        client_ip=attacker_ip,
        identifier="brand_new_target@victim.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert sprayed_101st.allowed is False
    assert sprayed_101st.retry_after > 0


@pytest.mark.asyncio
async def test_window_expiry_resets_and_retry_after_calculation() -> None:
    """Sliding window resets once window duration passes, and retry_after reflects elapsed time."""
    clock = ControllableClock(start_time=1000.0)
    limiter = InMemoryRateLimiter(clock=clock)

    # 10 requests at t=1000.0
    for _ in range(10):
        await limiter.check_auth_rate_limit(
            client_ip="10.0.0.1",
            identifier="test@example.com",
            endpoint_prefix="login",
            compound_limit=10,
            compound_window=900,
            ip_limit=100,
            ip_window=900,
        )

    # At t=1000.0, retry-after is full 900 seconds
    res_blocked = await limiter.check_auth_rate_limit(
        client_ip="10.0.0.1",
        identifier="test@example.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert res_blocked.allowed is False
    assert res_blocked.retry_after == 900

    # Advance clock by 300 seconds (t=1300.0)
    clock.advance(300.0)
    res_partial = await limiter.check_auth_rate_limit(
        client_ip="10.0.0.1",
        identifier="test@example.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert res_partial.allowed is False
    # Oldest timestamp is t=1000.0, window is 900 -> expires at 1900.0 -> remaining = 1900 - 1300 = 600
    assert res_partial.retry_after == 600

    # Advance clock past full window (+601 seconds -> t=1901.0)
    clock.advance(601.0)
    res_after_expiry = await limiter.check_auth_rate_limit(
        client_ip="10.0.0.1",
        identifier="test@example.com",
        endpoint_prefix="login",
        compound_limit=10,
        compound_window=900,
        ip_limit=100,
        ip_window=900,
    )
    assert res_after_expiry.allowed is True
    assert res_after_expiry.retry_after == 0


def test_in_memory_cleanup_removes_stale_keys() -> None:
    """Stale keys older than default window are evicted by cleanup()."""
    clock = ControllableClock(start_time=1000.0)
    limiter = InMemoryRateLimiter(default_window_seconds=900, clock=clock)

    limiter.requests["key_active"] = [950.0, 990.0]
    limiter.requests["key_stale"] = [50.0, 80.0]

    # Advance clock to 1100.0
    clock.advance(100.0)
    evicted = limiter.cleanup()

    assert evicted == 1
    assert "key_stale" not in limiter.requests
    assert "key_active" in limiter.requests


# ===========================================================================
# 2. Integration Tests: HTTP Anti-Enumeration & Dependency Swapping
# ===========================================================================


@pytest.mark.asyncio
async def test_429_body_identical_for_existing_and_non_existing_identifiers(
    client: AsyncClient,
    employee_user: User,
) -> None:
    """
    Anti-Enumeration Guard:
    HTTP 429 response structure and detail must be identical whether the identifier
    corresponds to an existing registered user or a non-existent account.
    """
    from app.core.rate_limit import _limiter_instance

    # 1. Rate-limit existing user
    _limiter_instance.reset()
    for _ in range(10):
        await client.post(
            "/auth/login",
            json={"identifier": employee_user.employee_code, "password": "WrongPassword!", "mode": "employee"},
        )
    res_existing = await client.post(
        "/auth/login",
        json={"identifier": employee_user.employee_code, "password": "WrongPassword!", "mode": "employee"},
    )
    assert res_existing.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # 2. Rate-limit non-existing user
    _limiter_instance.reset()
    fake_code = "9999999999"
    for _ in range(10):
        await client.post(
            "/auth/login",
            json={"identifier": fake_code, "password": "WrongPassword!", "mode": "employee"},
        )
    res_non_existing = await client.post(
        "/auth/login",
        json={"identifier": fake_code, "password": "WrongPassword!", "mode": "employee"},
    )
    assert res_non_existing.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # 3. Assert exact payload equality
    assert res_existing.json() == res_non_existing.json()
    assert "retry-after" in res_existing.headers
    assert "retry-after" in res_non_existing.headers


@pytest.mark.asyncio
async def test_rate_limiter_swappable_via_dependency_override(client: AsyncClient) -> None:
    """
    Interface Isolation:
    The FastAPI endpoints consume RateLimiter via dependency injection (get_rate_limiter),
    allowing seamless substitution with a fake/mock implementation or future RedisRateLimiter.
    """
    fake_limiter = FakeRateLimiter(allow_all=False)
    app.dependency_overrides[get_rate_limiter] = lambda: fake_limiter

    try:
        res = await client.post(
            "/auth/login",
            json={"identifier": "test@example.com", "password": "Password123!", "mode": "employee"},
        )
        assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert res.headers["retry-after"] == "42"
        assert len(fake_limiter.calls) > 0
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


# ===========================================================================
# 3. Client IP Extraction Tests (Trusted Proxies & Spoofing Defense)
# ===========================================================================


def test_extract_client_ip_variants() -> None:
    """Tests extract_client_ip logic under various proxy and header configurations."""
    # 1. Direct connection, no proxy
    req_direct = MagicMock()
    req_direct.client.host = "192.0.2.1"
    req_direct.headers = {}
    assert extract_client_ip(req_direct, trusted_proxies=[]) == "192.0.2.1"

    # 2. Untrusted proxy: spoofed X-Forwarded-For is ignored
    req_spoof = MagicMock()
    req_spoof.client.host = "192.0.2.1"
    req_spoof.headers = {"x-forwarded-for": "10.0.0.1, 10.0.0.2"}
    assert extract_client_ip(req_spoof, trusted_proxies=[]) == "192.0.2.1"

    # 3. Trusted proxy: extracts true client IP from X-Forwarded-For
    req_trusted = MagicMock()
    req_trusted.client.host = "127.0.0.1"
    req_trusted.headers = {"x-forwarded-for": "203.0.113.195, 127.0.0.1"}
    assert extract_client_ip(req_trusted, trusted_proxies=["127.0.0.1"]) == "203.0.113.195"

    # 4. Multi-hop trusted proxies
    req_multihop = MagicMock()
    req_multihop.client.host = "10.0.0.1"
    req_multihop.headers = {"x-forwarded-for": "198.51.100.4, 10.0.0.2, 10.0.0.1"}
    assert extract_client_ip(req_multihop, trusted_proxies=["10.0.0.1", "10.0.0.2"]) == "198.51.100.4"
