"""Admin endpoints: table inventory and operating hours.

All routes require `X-Admin-Key` when ADMIN_API_KEY is configured.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clock, models
from app.deps import get_session, require_admin
from app.errors import ConflictError, NotFoundError, ValidationError
from app.schemas import HoursUpdate, HoursWindowOut, TableCreate, TableOut, TableUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------- tables ----------


@router.get("/tables", response_model=list[TableOut])
def list_tables(session: Session = Depends(get_session)) -> list[models.Table]:
    return list(session.execute(select(models.Table).order_by(models.Table.id)).scalars())


@router.post("/tables", response_model=TableOut, status_code=201)
def create_table(payload: TableCreate, session: Session = Depends(get_session)) -> models.Table:
    table = models.Table(
        name=payload.name.strip(), capacity=payload.capacity, created_at=clock.now()
    )
    session.add(table)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(f"A table named {payload.name!r} already exists") from None
    session.refresh(table)
    return table


@router.put("/tables/{table_id}", response_model=TableOut)
def update_table(
    table_id: int, payload: TableUpdate, session: Session = Depends(get_session)
) -> models.Table:
    table = session.get(models.Table, table_id)
    if table is None:
        raise NotFoundError(f"Table {table_id} does not exist")

    if payload.name is not None:
        table.name = payload.name.strip()
    if payload.capacity is not None:
        busiest = session.execute(
            select(func.max(models.Reservation.guest_count)).where(
                models.Reservation.table_id == table_id,
                models.Reservation.status == "booked",
            )
        ).scalar()
        if payload.capacity < (busiest or 0):
            raise ConflictError(
                f"Cannot shrink capacity to {payload.capacity}: an active "
                f"reservation on {table.name} seats {busiest} guests"
            )
        table.capacity = payload.capacity

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(f"A table named {payload.name!r} already exists") from None
    session.refresh(table)
    return table


@router.delete("/tables/{table_id}", status_code=204)
def delete_table(table_id: int, session: Session = Depends(get_session)) -> None:
    table = session.get(models.Table, table_id)
    if table is None:
        raise NotFoundError(f"Table {table_id} does not exist")
    active = session.execute(
        select(func.count())
        .select_from(models.Reservation)
        .where(
            models.Reservation.table_id == table_id,
            models.Reservation.status == "booked",
        )
    ).scalar()
    if active:
        raise ConflictError(
            f"Table {table.name} has {active} active reservation(s); cancel them first"
        )
    session.delete(table)
    session.commit()


# ---------- operating hours ----------


@router.get("/hours", response_model=list[HoursWindowOut])
def get_hours(session: Session = Depends(get_session)) -> list[models.OperatingHours]:
    return list(
        session.execute(
            select(models.OperatingHours).order_by(
                models.OperatingHours.weekday, models.OperatingHours.opens
            )
        ).scalars()
    )


@router.put("/hours", response_model=list[HoursWindowOut])
def replace_hours(payload: HoursUpdate, session: Session = Depends(get_session)):
    """Replace the whole weekly schedule in one call.

    Existing reservations are kept (they were valid against the schedule at
    booking time); new bookings are validated against the new schedule.
    """
    seen: set[tuple[int, object]] = set()
    for window in payload.windows:
        if window.opens >= window.closes:
            raise ValidationError(
                f"Window for weekday {window.weekday} must open before it closes "
                "(overnight windows are not supported)"
            )
        key = (window.weekday, window.opens)
        if key in seen:
            raise ValidationError(
                f"Duplicate window for weekday {window.weekday} at {window.opens}"
            )
        seen.add(key)

    session.execute(delete(models.OperatingHours))
    for window in payload.windows:
        session.add(
            models.OperatingHours(weekday=window.weekday, opens=window.opens, closes=window.closes)
        )
    session.commit()
    return get_hours(session)
