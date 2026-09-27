"""Slot computation and availability search — the heart of the domain.

Reservation rules:
  * every reservation lasts exactly SLOT_DURATION_HOURS (2 hours);
  * start times are grid-aligned to the operating windows: each window
    [opens, closes) yields slots at opens, opens+2h, opens+4h, ... while
    the full slot still ends by `closes`;
  * a table is available for a slot when its capacity fits the party and
    no ACTIVE reservation on it overlaps the slot.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.models import OperatingHours, Reservation, Table

SLOT = timedelta(hours=config.SLOT_DURATION_HOURS)


def windows_for(session: Session, day: date) -> list[tuple[time, time]]:
    """The operating windows active on `day` (weekday-indexed, 0 = Monday)."""
    rows = session.execute(
        select(OperatingHours)
        .where(OperatingHours.weekday == day.weekday())
        .order_by(OperatingHours.opens)
    ).scalars()
    return [(row.opens, row.closes) for row in rows]


def slot_starts_for(session: Session, day: date) -> list[datetime]:
    """All valid reservation start times on `day`, sorted ascending."""
    starts: list[datetime] = []
    for opens, closes in windows_for(session, day):
        slot = datetime.combine(day, opens)
        limit = datetime.combine(day, closes)
        while slot + SLOT <= limit:
            starts.append(slot)
            slot += SLOT
    return sorted(set(starts))


def is_valid_start(session: Session, start: datetime) -> bool:
    return start in slot_starts_for(session, start.date())


def has_conflict(session: Session, table_id: int, start: datetime, end: datetime) -> bool:
    """True when the table has an ACTIVE reservation overlapping [start, end)."""
    stmt = (
        select(Reservation.id)
        .where(
            Reservation.table_id == table_id,
            Reservation.status == "booked",
            Reservation.start_time < end,
            Reservation.end_time > start,
        )
        .limit(1)
    )
    return session.execute(stmt).first() is not None


def available_tables(session: Session, start: datetime, guests: int) -> list[Table]:
    """Tables that seat `guests` and are free for the 2-hour slot starting at `start`.

    Ordered smallest-fit-first, the norm for party-size matching.
    """
    end = start + SLOT
    candidates = list(
        session.execute(
            select(Table).where(Table.capacity >= guests).order_by(Table.capacity, Table.id)
        ).scalars()
    )
    busy = set(
        session.execute(
            select(Reservation.table_id).where(
                Reservation.status == "booked",
                Reservation.start_time < end,
                Reservation.end_time > start,
            )
        ).scalars()
    )
    return [t for t in candidates if t.id not in busy]
