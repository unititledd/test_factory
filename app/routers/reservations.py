"""Booking endpoints: create, list, fetch, cancel."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.errors import NotFoundError
from app.models import Reservation
from app.schemas import ReservationCreate, ReservationOut
from app.services import reservations as service

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


@router.post("", response_model=ReservationOut, status_code=201)
def book(payload: ReservationCreate, session: Session = Depends(get_session)) -> Reservation:
    """Book a table for the 2-hour slot starting at `payload.start`."""
    return service.create_reservation(
        session,
        table_id=payload.table_id,
        start=payload.start,
        guest_count=payload.guest_count,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
    )


@router.get("", response_model=list[ReservationOut])
def list_reservations(
    session: Session = Depends(get_session),
    day: date | None = Query(default=None, alias="date", description="Filter by calendar day"),
) -> list[Reservation]:
    """List reservations, newest slot first; optional `date` filter."""
    stmt = select(Reservation).order_by(Reservation.start_time, Reservation.id)
    if day is not None:
        window_start = datetime.combine(day, time.min)
        window_end = window_start + timedelta(days=1)
        stmt = stmt.where(
            Reservation.start_time >= window_start,
            Reservation.start_time < window_end,
        )
    return list(session.execute(stmt).scalars())


@router.get("/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int, session: Session = Depends(get_session)) -> Reservation:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise NotFoundError(f"Reservation {reservation_id} does not exist")
    return reservation


@router.post("/{reservation_id}/cancel", response_model=ReservationOut)
def cancel(reservation_id: int, session: Session = Depends(get_session)) -> Reservation:
    """Cancel a reservation; the slot becomes bookable again."""
    return service.cancel_reservation(session, reservation_id)
