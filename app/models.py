"""ORM models — the database schema."""

from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: 0 = Monday ... 6 = Sunday (matches Python's date.weekday()).
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class Base(DeclarativeBase):
    pass


class Table(Base):
    """A physical dining table and how many guests it seats."""

    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="table")

    __table_args__ = (CheckConstraint("capacity >= 1", name="ck_tables_capacity"),)

    def __repr__(self) -> str:
        return f"Table(id={self.id!r}, name={self.name!r}, capacity={self.capacity!r})"


class OperatingHours(Base):
    """Service windows per weekday (0 = Monday ... 6 = Sunday).

    A day can carry several windows (lunch and dinner, say); a day with no
    rows is closed. Windows never cross midnight: opens < closes.
    """

    __tablename__ = "operating_hours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    opens: Mapped[time] = mapped_column(Time, nullable=False)
    closes: Mapped[time] = mapped_column(Time, nullable=False)

    __table_args__ = (
        UniqueConstraint("weekday", "opens", name="uq_operating_hours_weekday_opens"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_operating_hours_weekday"),
        CheckConstraint("opens < closes", name="ck_operating_hours_window"),
    )


class Reservation(Base):
    """A dining reservation. Always exactly SLOT_DURATION_HOURS long.

    `end_time` is denormalized on purpose: overlap checks read a plain column
    and the 2-hour invariant is enforced at creation time.
    """

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("tables.id"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="booked")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    table: Mapped["Table"] = relationship(back_populates="reservations", lazy="joined")

    __table_args__ = (
        CheckConstraint("guest_count >= 1", name="ck_reservations_guest_count"),
        CheckConstraint("status IN ('booked', 'cancelled')", name="ck_reservations_status"),
        # The double-booking guard: at most one ACTIVE reservation per table
        # per start time, enforced by the database itself, so two concurrent
        # requests can never both commit the same slot — the loser gets
        # IntegrityError, which the service maps to 409.
        Index(
            "uq_active_reservation_slot",
            "table_id",
            "start_time",
            unique=True,
            sqlite_where=sa_text("status = 'booked'"),
            postgresql_where=sa_text("status = 'booked'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Reservation(id={self.id!r}, table_id={self.table_id!r}, "
            f"start={self.start_time!r}, status={self.status!r})"
        )
