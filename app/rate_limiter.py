"""Atomic, Redis-backed per-consumer monthly rate limiting."""
from datetime import datetime, timezone

from redis.asyncio import Redis

# Slightly over a month, so a key never expires before the next month's key takes over.
_KEY_TTL_SECONDS = 60 * 60 * 24 * 32

DEFAULT_TIER = "FREE"


def _month_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def check_and_increment(
    redis: Redis, consumer_id: str, tier: str, tier_limits: dict[str, int]
) -> tuple[bool, int, int]:
    """Atomically increments the consumer's usage counter for the current month.

    Returns (allowed, current_usage, limit).
    """
    key = f"ratelimit:{consumer_id}:{_month_bucket()}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, _KEY_TTL_SECONDS)

    limit = tier_limits.get(tier, tier_limits[DEFAULT_TIER])
    return current <= limit, current, limit
