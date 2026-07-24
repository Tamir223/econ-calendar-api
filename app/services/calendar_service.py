"""Combines upstream calendar sources with fallback, filtering, and pagination."""
import logging
from datetime import date as date_
from datetime import timedelta

import httpx
from redis.asyncio import Redis

from app.config import Settings
from app.models import CalendarEvent, ImpactLevel, PaginatedCalendarResponse
from app.services import finnhub, forexfactory

logger = logging.getLogger("econ_calendar_api.calendar_service")

# How far around "today" to query Finnhub when falling back, since ForexFactory's
# weekly feeds are unavailable and Finnhub requires an explicit date range.
_FINNHUB_FALLBACK_WINDOW_DAYS = 7


class CalendarService:
    def __init__(self, http_client: httpx.AsyncClient, redis: Redis, settings: Settings):
        self._client = http_client
        self._redis = redis
        self._settings = settings

    async def get_events(
        self,
        from_date: date_ | None = None,
        to_date: date_ | None = None,
        impact: list[ImpactLevel] | None = None,
        currency: str | None = None,
    ) -> list[CalendarEvent]:
        events = await self._fetch_all()

        if from_date is not None:
            events = [e for e in events if e.date >= from_date]
        if to_date is not None:
            events = [e for e in events if e.date <= to_date]
        if impact:
            impact_set = set(impact)
            events = [e for e in events if e.impact in impact_set]
        if currency:
            code = currency.upper()
            events = [e for e in events if e.currency == code]

        events.sort(key=lambda e: (e.date, e.datetime or e.date))
        return events

    async def _fetch_all(self) -> list[CalendarEvent]:
        try:
            return await forexfactory.fetch_events(self._client, self._redis, self._settings)
        except forexfactory.ForexFactoryUnavailableError as exc:
            logger.warning("ForexFactory unavailable, falling back to Finnhub: %s", exc)

        today = date_.today()
        window_from = today - timedelta(days=_FINNHUB_FALLBACK_WINDOW_DAYS)
        window_to = today + timedelta(days=_FINNHUB_FALLBACK_WINDOW_DAYS)
        try:
            return await finnhub.fetch_events(self._client, self._redis, self._settings, window_from, window_to)
        except finnhub.FinnhubUnavailableError as exc:
            logger.error("Finnhub fallback also unavailable: %s", exc)
            raise


def paginate(events: list[CalendarEvent], page: int, page_size: int) -> PaginatedCalendarResponse:
    total = len(events)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    return PaginatedCalendarResponse(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        data=events[start:end],
    )
