"""Fetches and normalizes economic calendar data from ForexFactory's public JSON feed."""
from datetime import datetime

import httpx

from app.cache import get_cached_json, set_cached_json
from app.config import Settings
from app.models import CalendarEvent, ImpactLevel

# ForexFactory publishes rolling weekly windows of calendar data as static JSON files.
# Fetching all three gives full coverage of "recent past" through "near future".
SCOPES = ("lastweek", "thisweek", "nextweek")

_IMPACT_MAP = {
    "high": ImpactLevel.HIGH,
    "medium": ImpactLevel.MEDIUM,
    "low": ImpactLevel.LOW,
    "holiday": ImpactLevel.HOLIDAY,
    "non-economic": ImpactLevel.HOLIDAY,
}


class ForexFactoryUnavailableError(Exception):
    """Raised when the ForexFactory feed cannot be fetched or parsed."""


def _parse_impact(raw: str | None) -> ImpactLevel:
    if not raw:
        return ImpactLevel.LOW
    return _IMPACT_MAP.get(raw.strip().lower(), ImpactLevel.LOW)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_entry(entry: dict) -> CalendarEvent | None:
    dt = _parse_datetime(entry.get("date"))
    if dt is None:
        return None
    return CalendarEvent(
        event=entry.get("title", "Unknown Event"),
        currency=(entry.get("country") or "").upper() or "UNKNOWN",
        impact=_parse_impact(entry.get("impact")),
        date=dt.date(),
        datetime=dt,
        forecast=entry.get("forecast") or None,
        previous=entry.get("previous") or None,
        actual=entry.get("actual") or None,
        source="forexfactory",
    )


async def _fetch_scope(client: httpx.AsyncClient, settings: Settings, scope: str) -> list[dict]:
    url = f"{settings.forexfactory_base_url}/ff_calendar_{scope}.json"
    try:
        response = await client.get(url, timeout=settings.http_timeout_seconds)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ForexFactoryUnavailableError(f"Failed to fetch ForexFactory scope '{scope}': {exc}") from exc


async def fetch_events(client: httpx.AsyncClient, redis, settings: Settings) -> list[CalendarEvent]:
    """Fetch and normalize all available ForexFactory events (last/this/next week), using the cache when possible."""
    events: list[CalendarEvent] = []
    scope_errors: list[str] = []

    for scope in SCOPES:
        cache_key = f"calendar:ff:{scope}"
        cached = await get_cached_json(redis, cache_key)

        if cached is not None:
            raw_entries = cached
        else:
            try:
                raw_entries = await _fetch_scope(client, settings, scope)
            except ForexFactoryUnavailableError as exc:
                print(f"ForexFactory scope '{scope}' unavailable, skipping: {exc}")
                scope_errors.append(scope)
                continue
            await set_cached_json(redis, cache_key, raw_entries, settings.cache_ttl_seconds)

        for entry in raw_entries:
            normalized = _normalize_entry(entry)
            if normalized is not None:
                events.append(normalized)

    if scope_errors and len(scope_errors) == len(SCOPES):
        raise ForexFactoryUnavailableError(
            f"All ForexFactory scopes unavailable: {', '.join(scope_errors)}"
        )

    return events

