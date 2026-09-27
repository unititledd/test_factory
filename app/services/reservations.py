"""Reservation lifecycle: create, cancel, look up."""

from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clock
from app.config import SLOT_DURATION_HOURS
from app.errors import ConflictError, NotFoundError, OverCapacityError, ValidationError
from app.models import Reservation, Table
from app.services import availability

SLOT = timedelta(hours=SLOT_DURATION_HOURS)


def create_reservation(
    session: Session,
    *,
    table_id: int,
    start: datetime,
    guest_count: int,
    customer_name: str,
    customer_phone: str,
) -> Reservation:
    """Book a table for the 2-hour slot starting at `start`.

    Validation order: table exists -> capacity fits -> start is in the future
    -> start is one of the day's two-hour slots -> no overlapping booking.
    """
    table = session.get(Table, table_id)
    if table is None:
        raise NotFoundError(f"Table {table_id} does not exist")

    if guest_count > table.capacity:
        raise OverCapacityError(
            f"Table {table.name} seats {table.capacity}; it cannot fit {guest_count} guests"
        )

    if start <= clock.now():
        raise ValidationError("Reservation start must be in the future")

    allowed = availability.slot_starts_for(session, start.date())
    if start not in allowed:
        raise ValidationError(
            "Start time is not one of this day's two-hour slots. Reservations "
            "are fixed at two-hour intervals aligned to the operating hours.",
            allowed_slots=[s.isoformat() for s in allowed],
        )

    end = start + SLOT
    if availability.has_conflict(session, table_id, start, end):
        raise ConflictError(f"Table {table.name} is already booked for that time slot")

    reservation = Reservation(
        table_id=table_id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        guest_count=guest_count,
        start_time=start,
        end_time=end,
        status="booked",
        created_at=clock.now(),
    )
    session.add(reservation)
    try:
        # The partial UNIQUE index (table_id, start_time) over active
        # reservations is the last line of defense: if a concurrent request
        # booked this exact slot between our check and this commit, the
        # commit itself fails instead of double-booking.
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(f"Table {table.name} was just booked by someone else") from None
    session.refresh(reservation)
    return reservation


def cancel_reservation(session: Session, reservation_id: int) -> Reservation:
    """Cancel a reservation, freeing the slot for future bookings."""
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise NotFoundError(f"Reservation {reservation_id} does not exist")
    if reservation.status == "cancelled":
        raise ConflictError(f"Reservation {reservation_id} is already cancelled")
    reservation.status = "cancelled"
    session.commit()
    session.refresh(reservation)
    return reservation
