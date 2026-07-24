"""Econ Calendar API — a standalone economic calendar data service.

Fetches economic calendar events from ForexFactory's public JSON feed (falling
back to Finnhub when unavailable), and exposes them through a clean, generic
REST API suitable for public distribution on RapidAPI.
"""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import get_settings
from app.middleware import RapidAPIAuthMiddleware, RateLimitMiddleware
from app.routers.calendar import router as calendar_router

DESCRIPTION = """
Econ Calendar API provides economic calendar events — releases, indicators, and
scheduled announcements — sourced from ForexFactory's public calendar feed,
with automatic fallback to Finnhub if that feed is unavailable.

Every event includes its **impact level** (high, medium, low, or holiday) and
**currency** as reported by the upstream source, so you can filter results to
whatever level of detail your application needs.

### Rate limits
Requests are metered per calendar month based on your RapidAPI subscription
tier: Free (50/mo), Basic (1,000/mo), Pro (10,000/mo), Business (100,000/mo).
Exceeding your tier's limit returns an HTTP 429 response.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.http_client = httpx.AsyncClient()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    yield

    await app.state.http_client.aclose()
    await app.state.redis.aclose()


app = FastAPI(
    title="Econ Calendar API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware executes in the reverse order it's added (last added runs first),
# so auth is checked before the request counts against the caller's rate limit.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RapidAPIAuthMiddleware)

app.include_router(calendar_router)


@app.get("/health", tags=["meta"], summary="Health check", description="Basic liveness check for uptime monitoring.")
async def health():
    return {"status": "ok"}
