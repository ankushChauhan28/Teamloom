"""
Rate Limiter Interface & In-Memory Sliding-Window Implementation (Level 1).

Decided Level 1 Design:
- Dual-key rate limiting for authentication endpoints:
  1. Compound key {client IP, normalized identifier} (default: 10 attempts / 15 minutes).
     Prevents office NAT IP lockout across different users sharing an egress gateway.
  2. Looser per-IP ceiling across all identifiers (default: 100 attempts / 15 minutes).
     Protects against distributed password spraying across many accounts from one IP.
- Sliding-window algorithm:
  Stores request timestamps per key. Calculates exact Retry-After seconds.
- Stale-key cleanup:
  Periodically and on-demand purges expired timestamp lists so in-memory state does not grow unbounded.
- Controllable clock support (clock callable) for deterministic, sleep-free testing.
- Abstract RateLimiter interface allows seamless future Redis implementation behind
  the same contract without altering route dependencies.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import math
import time

from fastapi import Request

from app.core.config import settings


@dataclass
class RateLimitResult:
    """Result of a rate limit evaluation."""

    allowed: bool
    retry_after_seconds: int = 0

    @property
    def retry_after(self) -> int:
        return self.retry_after_seconds


def extract_client_ip(request: Request, trusted_proxies: list[str] | None = None) -> str:
    """
    Safely resolves client IP address:
    - Only trusts X-Forwarded-For if request.client.host is in trusted_proxies (defaults to settings.TRUSTED_PROXY_IPS).
    - If trusted, parses X-Forwarded-For from right to left, returning the rightmost untrusted IP.
    - Otherwise, strictly falls back to direct connection host (request.client.host).
    """
    proxies = trusted_proxies if trusted_proxies is not None else settings.TRUSTED_PROXY_IPS
    client_host = request.client.host if request.client and request.client.host else "127.0.0.1"
    if client_host in proxies:
        x_forwarded_for = request.headers.get("X-Forwarded-For") or request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
            for ip in reversed(ips):
                if ip not in proxies:
                    return ip
            if ips:
                return ips[0]
    return client_host


class RateLimiter(ABC):
    """Abstract interface for rate limiting implementations."""

    @abstractmethod
    async def check_and_increment(
        self,
        key: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        """
        Checks if key is within rate limit and records request timestamp if allowed.
        """
        pass

    async def check_auth_rate_limit(
        self,
        client_ip: str,
        identifier: str,
        endpoint_prefix: str,
        compound_limit: int | None = None,
        compound_window: int | None = None,
        ip_limit: int | None = None,
        ip_window: int | None = None,
    ) -> RateLimitResult:
        """
        Evaluates both the compound {IP, identifier} limit and the per-IP ceiling limit.
        Default implementation delegates to check_and_increment.
        """
        c_limit = compound_limit if compound_limit is not None else settings.RATE_LIMIT_AUTH_ATTEMPTS
        c_window = compound_window if compound_window is not None else settings.RATE_LIMIT_AUTH_WINDOW_SECONDS
        i_limit = ip_limit if ip_limit is not None else settings.RATE_LIMIT_IP_CEILING_ATTEMPTS
        i_window = ip_window if ip_window is not None else settings.RATE_LIMIT_IP_CEILING_WINDOW_SECONDS

        norm_id = identifier.strip().lower() if identifier else "anonymous"
        compound_key = f"{endpoint_prefix}:compound:{client_ip}:{norm_id}"
        ip_key = f"{endpoint_prefix}:ip:{client_ip}"

        # 1. Check IP ceiling first (spray defense across all identifiers)
        ip_res = await self.check_and_increment(ip_key, max_requests=i_limit, window_seconds=i_window)
        if not ip_res.allowed:
            return ip_res

        # 2. Check compound key (per-identifier NAT defense)
        compound_res = await self.check_and_increment(compound_key, max_requests=c_limit, window_seconds=c_window)
        if not compound_res.allowed:
            return compound_res

        return RateLimitResult(allowed=True, retry_after_seconds=0)

    @abstractmethod
    def reset(self) -> None:
        """Clears all stored rate limit states (useful for testing)."""
        pass

    @abstractmethod
    def cleanup(self) -> int:
        """Removes expired keys from storage. Returns number of keys evicted."""
        pass


class InMemoryRateLimiter(RateLimiter):
    """
    In-memory sliding-window rate limiter implementation.
    Tracks timestamps per key in a dictionary with automatic and manual stale-key cleanup.
    Supports injectable clock for deterministic testing without real sleeps.
    """

    def __init__(
        self,
        default_max_requests: int = 10,
        default_window_seconds: int = 900,
        clock: Callable[[], float] = time.time,
        cleanup_interval_calls: int = 100,
    ):
        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        self.clock = clock
        self.cleanup_interval_calls = cleanup_interval_calls
        self._call_counter = 0
        self.requests: dict[str, list[float]] = {}

    def _now(self) -> float:
        return self.clock()

    async def check_and_increment(
        self,
        key: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        now = self._now()
        max_req = max_requests if max_requests is not None else self.default_max_requests
        win_sec = window_seconds if window_seconds is not None else self.default_window_seconds
        window_start = now - win_sec

        # Trigger periodic cleanup
        self._call_counter += 1
        if self._call_counter >= self.cleanup_interval_calls:
            self.cleanup()
            self._call_counter = 0

        # Retrieve and filter timestamps within sliding window
        timestamps = self.requests.get(key, [])
        valid_timestamps = [ts for ts in timestamps if ts > window_start]

        if len(valid_timestamps) >= max_req:
            oldest_ts = valid_timestamps[0]
            remaining_seconds = oldest_ts + win_sec - now
            retry_after = max(1, math.ceil(remaining_seconds))
            self.requests[key] = valid_timestamps
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        valid_timestamps.append(now)
        self.requests[key] = valid_timestamps
        return RateLimitResult(allowed=True, retry_after_seconds=0)

    async def check_auth_rate_limit(
        self,
        client_ip: str,
        identifier: str,
        endpoint_prefix: str,
        compound_limit: int | None = None,
        compound_window: int | None = None,
        ip_limit: int | None = None,
        ip_window: int | None = None,
    ) -> RateLimitResult:
        c_limit = compound_limit if compound_limit is not None else settings.RATE_LIMIT_AUTH_ATTEMPTS
        c_window = compound_window if compound_window is not None else settings.RATE_LIMIT_AUTH_WINDOW_SECONDS
        i_limit = ip_limit if ip_limit is not None else settings.RATE_LIMIT_IP_CEILING_ATTEMPTS
        i_window = ip_window if ip_window is not None else settings.RATE_LIMIT_IP_CEILING_WINDOW_SECONDS

        norm_id = identifier.strip().lower() if identifier else "anonymous"
        compound_key = f"{endpoint_prefix}:compound:{client_ip}:{norm_id}"
        ip_key = f"{endpoint_prefix}:ip:{client_ip}"

        now = self._now()

        # 1. Check IP ceiling first (spray defense)
        ip_window_start = now - i_window
        ip_timestamps = [ts for ts in self.requests.get(ip_key, []) if ts > ip_window_start]
        if len(ip_timestamps) >= i_limit:
            oldest_ts = ip_timestamps[0]
            retry_after = max(1, math.ceil(oldest_ts + i_window - now))
            self.requests[ip_key] = ip_timestamps
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        # 2. Check compound key (per-identifier NAT defense)
        c_window_start = now - c_window
        c_timestamps = [ts for ts in self.requests.get(compound_key, []) if ts > c_window_start]
        if len(c_timestamps) >= c_limit:
            oldest_ts = c_timestamps[0]
            retry_after = max(1, math.ceil(oldest_ts + c_window - now))
            self.requests[compound_key] = c_timestamps
            # Failed request attempt on compound key still counts towards the IP ceiling
            ip_timestamps.append(now)
            self.requests[ip_key] = ip_timestamps
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        # 3. Both allowed: record timestamps on both keys
        ip_timestamps.append(now)
        self.requests[ip_key] = ip_timestamps

        c_timestamps.append(now)
        self.requests[compound_key] = c_timestamps

        return RateLimitResult(allowed=True, retry_after_seconds=0)

    def cleanup(self) -> int:
        now = self._now()
        max_window = max(
            self.default_window_seconds,
            settings.RATE_LIMIT_AUTH_WINDOW_SECONDS,
            settings.RATE_LIMIT_IP_CEILING_WINDOW_SECONDS,
        )
        threshold = now - max_window
        keys_to_delete = [
            k for k, timestamps in self.requests.items()
            if not timestamps or timestamps[-1] <= threshold
        ]
        for k in keys_to_delete:
            del self.requests[k]
        return len(keys_to_delete)

    def reset(self) -> None:
        self.requests.clear()
        self._call_counter = 0


class RedisRateLimiter(RateLimiter):
    """
    Redis-backed sliding-window rate limiter using sorted sets (ZSET).
    Retained as an optional implementation for future multi-worker scaling.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        max_requests: int = 10,
        window_seconds: int = 900,
        redis_client=None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_url = redis_url
        self._redis_client = redis_client

    async def _get_client(self):
        if self._redis_client is not None:
            return self._redis_client
        import redis.asyncio as aioredis
        self._redis_client = aioredis.from_url(
            self.redis_url or settings.REDIS_URL,
            decode_responses=True,
        )
        return self._redis_client

    async def check_and_increment(
        self,
        key: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        client = await self._get_client()
        redis_key = f"rate_limit:{key}"
        now = time.time()
        win_sec = window_seconds if window_seconds is not None else self.window_seconds
        max_req = max_requests if max_requests is not None else self.max_requests
        window_start = now - win_sec

        async with client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            res = await pipe.execute()

        count = res[1]
        oldest = res[2]

        if count >= max_req:
            retry_after = 1
            if oldest:
                oldest_ts = float(oldest[0][1])
                retry_after = max(1, int(oldest_ts + win_sec - now) + 1)
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        async with client.pipeline(transaction=True) as pipe:
            member = f"{now}:{time.time_ns()}"
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, win_sec + 60)
            await pipe.execute()

        return RateLimitResult(allowed=True, retry_after_seconds=0)

    async def reset(self) -> None:
        client = await self._get_client()
        keys = await client.keys("rate_limit:*")
        if keys:
            await client.delete(*keys)

    def cleanup(self) -> int:
        return 0


# Global in-memory instance used as the single default implementation
_in_memory_instance = InMemoryRateLimiter(
    default_max_requests=settings.RATE_LIMIT_AUTH_ATTEMPTS,
    default_window_seconds=settings.RATE_LIMIT_AUTH_WINDOW_SECONDS,
)
_limiter_instance: RateLimiter = _in_memory_instance


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency yielding the configured RateLimiter instance."""
    return _limiter_instance
