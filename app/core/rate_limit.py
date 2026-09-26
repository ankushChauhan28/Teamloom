"""
IP Rate Limiter Interface & In-Memory Implementation.

ARCHITECTURE & SCALING NOTE:
The current InMemoryRateLimiter stores IP request timestamps in process memory.
It is designed for single-instance deployments and will NOT work correctly across
multiple horizontally-scaled worker processes or container instances.
For multi-instance or cluster deployments, a RedisRateLimiter implementing the same
RateLimiter interface/protocol should be created and injected into the FastAPI app dependency,
requiring zero changes to route or service code.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    retry_after_seconds: int = 0


class RateLimiter(ABC):
    """Abstract interface for rate limiting implementations."""

    @abstractmethod
    async def check_and_increment(self, key: str) -> RateLimitResult:
        """Checks if key is within rate limit and increments request count."""
        pass


class InMemoryRateLimiter(RateLimiter):
    """
    In-memory sliding-window rate limiter implementation.
    Tracks timestamps per key (e.g. client IP) in a dictionary.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 900):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = {}

    async def check_and_increment(self, key: str) -> RateLimitResult:
        now = time.time()
        window_start = now - self.window_seconds

        # Retrieve and filter timestamps within the sliding window
        timestamps = self.requests.get(key, [])
        valid_timestamps = [ts for ts in timestamps if ts > window_start]

        if len(valid_timestamps) >= self.max_requests:
            # Exceeded rate limit: calculate seconds until oldest request expires out of window
            oldest_ts = valid_timestamps[0]
            retry_after = int(oldest_ts + self.window_seconds - now) + 1
            self.requests[key] = valid_timestamps
            return RateLimitResult(allowed=False, retry_after_seconds=max(1, retry_after))

        # Under rate limit: record current request timestamp
        valid_timestamps.append(now)
        self.requests[key] = valid_timestamps
        return RateLimitResult(allowed=True, retry_after_seconds=0)

    def reset(self) -> None:
        """Clears all stored rate limit states (useful for testing)."""
        self.requests.clear()


class RedisRateLimiter(RateLimiter):
    """
    Redis-backed sliding-window rate limiter using sorted sets (ZSET).
    Guarantees shared state across multiple Uvicorn workers and container replicas.
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
        from app.core.config import settings

        self._redis_client = aioredis.from_url(
            self.redis_url or settings.REDIS_URL,
            decode_responses=True,
        )
        return self._redis_client

    async def check_and_increment(self, key: str) -> RateLimitResult:
        client = await self._get_client()
        redis_key = f"rate_limit:{key}"
        now = time.time()
        window_start = now - self.window_seconds

        async with client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            res = await pipe.execute()

        count = res[1]
        oldest = res[2]

        if count >= self.max_requests:
            retry_after = 1
            if oldest:
                oldest_ts = float(oldest[0][1])
                retry_after = max(1, int(oldest_ts + self.window_seconds - now) + 1)
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        async with client.pipeline(transaction=True) as pipe:
            member = f"{now}:{time.time_ns()}"
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, self.window_seconds + 60)
            await pipe.execute()

        return RateLimitResult(allowed=True, retry_after_seconds=0)

    async def reset(self) -> None:
        """Clears all rate limit keys in Redis (useful for testing)."""
        client = await self._get_client()
        keys = await client.keys("rate_limit:*")
        if keys:
            await client.delete(*keys)


# Global instances for dependency injection
_in_memory_instance = InMemoryRateLimiter(max_requests=10, window_seconds=900)
_limiter_instance = _in_memory_instance
_redis_limiter_instance: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency yielding the configured RateLimiter instance."""
    global _redis_limiter_instance
    from app.core.config import settings

    if settings.RATE_LIMITER_BACKEND == "redis":
        if _redis_limiter_instance is None:
            _redis_limiter_instance = RedisRateLimiter(
                redis_url=settings.REDIS_URL,
                max_requests=10,
                window_seconds=900,
            )
        return _redis_limiter_instance
    return _in_memory_instance
