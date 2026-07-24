"""Public data models for the economic calendar API."""
from datetime import date as date_
from datetime import datetime as dt
from enum import Enum

from pydantic import BaseModel, Field


class ImpactLevel(str, Enum):
    """Impact classification as reported by the upstream source."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    HOLIDAY = "holiday"


class CalendarEvent(BaseModel):
    """A single economic calendar event, normalized across upstream sources."""

    event: str = Field(..., description="Name of the economic event or release.")
    currency: str = Field(..., description="Currency code the event affects, e.g. USD, EUR, GBP.")
    impact: ImpactLevel = Field(..., description="Impact level of the event.")
    date: date_ = Field(..., description="Calendar date of the event (UTC).")
    datetime: dt | None = Field(
        None, description="Full timestamp of the event when a time is known, otherwise null (all-day event)."
    )
    forecast: str | None = Field(None, description="Consensus forecast value, if available.")
    previous: str | None = Field(None, description="Previous period's value, if available.")
    actual: str | None = Field(None, description="Actual reported value, if available.")
    source: str = Field(..., description="Upstream data source this event was fetched from.")


class PaginatedCalendarResponse(BaseModel):
    """Paginated envelope for calendar event listings."""

    page: int = Field(..., description="Current page number, 1-indexed.")
    page_size: int = Field(..., description="Number of items per page.")
    total: int = Field(..., description="Total number of matching events across all pages.")
    total_pages: int = Field(..., description="Total number of pages available.")
    data: list[CalendarEvent] = Field(..., description="Calendar events for this page.")


class CalendarListResponse(BaseModel):
    """Unpaginated envelope for naturally bounded calendar listings (e.g. a single day)."""

    count: int = Field(..., description="Number of events returned.")
    data: list[CalendarEvent] = Field(..., description="Calendar events matching the request.")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
