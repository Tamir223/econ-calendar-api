"""Economic calendar endpoints."""
from datetime import date as date_

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models import CalendarListResponse, ImpactLevel, PaginatedCalendarResponse
from app.services.calendar_service import CalendarService, paginate

router = APIRouter(prefix="/v1/calendar", tags=["calendar"])

PAGE_DESCRIPTION = "Page number, 1-indexed."
PAGE_SIZE_DESCRIPTION = "Number of events per page (max 200)."
IMPACT_DESCRIPTION = "Filter by one or more impact levels: high, medium, low, holiday. Omit to include all levels."
CURRENCY_DESCRIPTION = "Filter by currency code, e.g. USD, EUR, GBP."
FROM_DATE_DESCRIPTION = "Only include events on or after this date (YYYY-MM-DD)."
TO_DATE_DESCRIPTION = "Only include events on or before this date (YYYY-MM-DD)."


def get_calendar_service(request: Request) -> CalendarService:
    return CalendarService(
        http_client=request.app.state.http_client,
        redis=request.app.state.redis,
        settings=request.app.state.settings,
    )


async def _get_events_or_503(service: CalendarService, **kwargs):
    try:
        return await service.get_events(**kwargs)
    except Exception as exc:  # upstream sources (ForexFactory + Finnhub fallback) both failed
        raise HTTPException(
            status_code=503,
            detail="Economic calendar data is temporarily unavailable. Please try again shortly.",
        ) from exc


@router.get(
    "",
    response_model=PaginatedCalendarResponse,
    summary="List calendar events",
    description="Returns the full economic calendar across all impact levels and currencies, paginated.",
)
async def list_calendar(
    page: int = Query(1, ge=1, description=PAGE_DESCRIPTION),
    page_size: int = Query(50, ge=1, le=200, description=PAGE_SIZE_DESCRIPTION),
    impact: list[ImpactLevel] | None = Query(None, description=IMPACT_DESCRIPTION),
    currency: str | None = Query(None, description=CURRENCY_DESCRIPTION),
    from_date: date_ | None = Query(None, description=FROM_DATE_DESCRIPTION),
    to_date: date_ | None = Query(None, description=TO_DATE_DESCRIPTION),
    service: CalendarService = Depends(get_calendar_service),
) -> PaginatedCalendarResponse:
    events = await _get_events_or_503(
        service, from_date=from_date, to_date=to_date, impact=impact, currency=currency
    )
    return paginate(events, page, page_size)


@router.get(
    "/high-impact",
    response_model=PaginatedCalendarResponse,
    summary="List high-impact events",
    description="Returns only high-impact economic events, paginated.",
)
async def high_impact_calendar(
    page: int = Query(1, ge=1, description=PAGE_DESCRIPTION),
    page_size: int = Query(50, ge=1, le=200, description=PAGE_SIZE_DESCRIPTION),
    currency: str | None = Query(None, description=CURRENCY_DESCRIPTION),
    from_date: date_ | None = Query(None, description=FROM_DATE_DESCRIPTION),
    to_date: date_ | None = Query(None, description=TO_DATE_DESCRIPTION),
    service: CalendarService = Depends(get_calendar_service),
) -> PaginatedCalendarResponse:
    events = await _get_events_or_503(
        service,
        from_date=from_date,
        to_date=to_date,
        impact=[ImpactLevel.HIGH],
        currency=currency,
    )
    return paginate(events, page, page_size)


@router.get(
    "/today",
    response_model=CalendarListResponse,
    summary="List today's events",
    description="Returns all economic events scheduled for today (UTC), optionally filtered by impact or currency.",
)
async def today_calendar(
    impact: list[ImpactLevel] | None = Query(None, description=IMPACT_DESCRIPTION),
    currency: str | None = Query(None, description=CURRENCY_DESCRIPTION),
    service: CalendarService = Depends(get_calendar_service),
) -> CalendarListResponse:
    today = date_.today()
    events = await _get_events_or_503(
        service, from_date=today, to_date=today, impact=impact, currency=currency
    )
    return CalendarListResponse(count=len(events), data=events)


@router.get(
    "/currency/{code}",
    response_model=PaginatedCalendarResponse,
    summary="List events by currency",
    description="Returns economic events affecting the given currency code (e.g. USD, EUR, GBP), paginated.",
)
async def currency_calendar(
    code: str,
    page: int = Query(1, ge=1, description=PAGE_DESCRIPTION),
    page_size: int = Query(50, ge=1, le=200, description=PAGE_SIZE_DESCRIPTION),
    impact: list[ImpactLevel] | None = Query(None, description=IMPACT_DESCRIPTION),
    from_date: date_ | None = Query(None, description=FROM_DATE_DESCRIPTION),
    to_date: date_ | None = Query(None, description=TO_DATE_DESCRIPTION),
    service: CalendarService = Depends(get_calendar_service),
) -> PaginatedCalendarResponse:
    events = await _get_events_or_503(
        service, from_date=from_date, to_date=to_date, impact=impact, currency=code
    )
    return paginate(events, page, page_size)
