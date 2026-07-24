"""RapidAPI request verification and per-consumer tiered rate limiting."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.rate_limiter import DEFAULT_TIER, check_and_increment

# Paths that must remain reachable without a RapidAPI proxy secret or rate limit,
# so docs and health checks work in local/dev environments and uptime monitors.
_EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/health"}

RAPIDAPI_PROXY_SECRET_HEADER = "X-RapidAPI-Proxy-Secret"
RAPIDAPI_USER_HEADER = "X-RapidAPI-User"
RAPIDAPI_SUBSCRIPTION_HEADER = "X-RapidAPI-Subscription"


class RapidAPIAuthMiddleware(BaseHTTPMiddleware):
    """Rejects requests that don't carry RapidAPI's proxy secret.

    RapidAPI injects this header into every request it forwards, so its presence
    proves the request actually came through the RapidAPI marketplace rather than
    being sent directly to the origin. If no secret is configured (local dev),
    the check is skipped entirely.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = request.app.state.settings

        if request.url.path in _EXEMPT_PATHS or not settings.rapidapi_proxy_secret:
            return await call_next(request)

        provided = request.headers.get(RAPIDAPI_PROXY_SECRET_HEADER)
        if provided != settings.rapidapi_proxy_secret:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "forbidden",
                    "message": "This API must be accessed through RapidAPI.",
                },
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces per-consumer, per-month request quotas based on RapidAPI's subscription tier."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        settings = request.app.state.settings
        redis = request.app.state.redis

        consumer_id = request.headers.get(RAPIDAPI_USER_HEADER) or (
            request.client.host if request.client else "anonymous"
        )
        tier = (request.headers.get(RAPIDAPI_SUBSCRIPTION_HEADER) or DEFAULT_TIER).upper()
        if tier not in settings.tier_limits:
            tier = DEFAULT_TIER

        allowed, current, limit = await check_and_increment(redis, consumer_id, tier, settings.tier_limits)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": (
                        f"You have exceeded your {tier} tier monthly limit of {limit} requests "
                        f"(used {current}). Upgrade your plan on RapidAPI to continue."
                    ),
                    "tier": tier,
                    "limit": limit,
                    "used": current,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        return response
