"""Fallback economic calendar source, used when ForexFactory is unavailable."""
from datetime import date as date_
from datetime import datetime

import httpx

from app.cache import get_cached_json, set_cached_json
from app.config import Settings
from app.models import CalendarEvent, ImpactLevel

# Finnhub reports country as an ISO country code rather than a currency code.
# This maps the major economies to the currency they issue.
_COUNTRY_TO_CURRENCY = {
    "US": "USD",
    "EU": "EUR",
    "GB": "GBP",
    "JP": "JPY",
    "CA": "CAD",
    "AU": "AUD",
    "NZ": "NZD",
    "CH": "CHF",
    "CN": "CNY",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
}

_IMPACT_MAP = {
    "high": ImpactLevel.HIGH,
    "medium": ImpactLevel.MEDIUM,
    "low": ImpactLevel.LOW,
}


class FinnhubUnavailableError(Exception):
    """Raised when the Finnhub fallback cannot be fetched or parsed."""


def _parse_impact(raw) -> ImpactLevel:
    if raw is None:
        return ImpactLevel.LOW
    if isinstance(raw, (int, float)):
        return {0: ImpactLevel.LOW, 1: ImpactLevel.MEDIUM, 2: ImpactLevel.HIGH, 3: ImpactLevel.HIGH}.get(
            int(raw), ImpactLevel.LOW
        )
    return _IMPACT_MAP.get(str(raw).strip().lower(), ImpactLevel.LOW)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _normalize_entry(entry: dict) -> CalendarEvent | None:
    dt = _parse_datetime(entry.get("time"))
    if dt is None:
        return None
    country = (entry.get("country") or "").upper()
    currency = _COUNTRY_TO_CURRENCY.get(country, country or "UNKNOWN")
    return CalendarEvent(
        event=entry.get("event", "Unknown Event"),
        currency=currency,
        impact=_parse_impact(entry.get("impact")),
        date=dt.date(),
        datetime=dt,
        forecast=_stringify(entry.get("estimate")),
        previous=_stringify(entry.get("prev")),
        actual=_stringify(entry.get("actual")),
        source="finnhub",
    )


def _stringify(value) -> str | None:
    if value is None:
        return None
    return str(value)


async def fetch_events(
    client: httpx.AsyncClient, redis, settings: Settings, from_date: date_, to_date: date_
) -> list[CalendarEvent]:
    """Fetch and normalize Finnhub economic calendar events for the given date range."""
    if not settings.finnhub_api_key:
        raise FinnhubUnavailableError("FINNHUB_API_KEY is not configured")

    cache_key = f"calendar:finnhub:{from_date.isoformat()}:{to_date.isoformat()}"
    cached = await get_cached_json(redis, cache_key)

    if cached is not None:
        raw_entries = cached
    else:
        url = f"{settings.finnhub_base_url}/calendar/economic"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "token": settings.finnhub_api_key}
        try:
            response = await client.get(url, params=params, timeout=settings.http_timeout_seconds)
            response.raise_for_status()
            raw_entries = response.json().get("economicCalendar", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise FinnhubUnavailableError(f"Failed to fetch Finnhub economic calendar: {exc}") from exc
        await set_cached_json(redis, cache_key, raw_entries, settings.cache_ttl_seconds)

    events = []
    for entry in raw_entries:
        normalized = _normalize_entry(entry)
        if normalized is not None:
            events.append(normalized)
    return events
