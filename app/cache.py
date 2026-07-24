"""Thin JSON caching helpers on top of Redis, used for calendar responses."""
import json
from typing import Any

from redis.asyncio import Redis


async def get_cached_json(redis: Redis, key: str) -> Any | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_json(redis: Redis, key: str, value: Any, ttl_seconds: int) -> None:
    await redis.set(key, json.dumps(value), ex=ttl_seconds)
