"""GET /api/availability — search free tables for a party and time."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import clock
from app.deps import get_session
from app.errors import ValidationError
from app.schemas import TableOut
from app.services import availability

router = APIRouter(prefix="/api/availability", tags=["availability"])


class AvailabilityResponse(BaseModel):
    start: datetime
    end: datetime
    guests: int
    available_tables: list[TableOut]


@router.get("", response_model=AvailabilityResponse)
def search_availability(
    start: datetime = Query(..., description="Slot start, restaurant-local, e.g. 2026-10-01T17:00"),
    guests: int = Query(..., ge=1),
    session: Session = Depends(get_session),
) -> AvailabilityResponse:
    """Find tables that can seat `guests` for the 2-hour slot starting at `start`.

    The start must be one of the day's two-hour slots; when it is not, the
    error response lists every valid slot for that day under `allowed_slots`.
    """
    if start.tzinfo is not None:
        raise ValidationError(
            "Times are restaurant-local; omit the timezone offset (e.g. 2026-10-01T17:00)"
        )
    if start <= clock.now():
        raise ValidationError("Cannot search for a time in the past")

    allowed = availability.slot_starts_for(session, start.date())
    if start not in allowed:
        raise ValidationError(
            "Start time is not one of this day's two-hour slots.",
            allowed_slots=[s.isoformat() for s in allowed],
        )

    return AvailabilityResponse(
        start=start,
        end=start + availability.SLOT,
        guests=guests,
        available_tables=[
            TableOut.model_validate(t)
            for t in availability.available_tables(session, start, guests)
        ],
    )
