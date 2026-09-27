"""Pydantic models: the public API contract (request/response shapes)."""

from datetime import datetime, time

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


# ---------- admin: tables ----------


class TableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, examples=["Booth-4"])
    capacity: int = Field(ge=1, le=50, examples=[4])


class TableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    capacity: int | None = Field(default=None, ge=1, le=50)


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    capacity: int


# ---------- admin: operating hours ----------


class HoursWindowIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")
    opens: time = Field(examples=["11:00"])
    closes: time = Field(examples=["23:00"])


class HoursUpdate(BaseModel):
    windows: list[HoursWindowIn] = Field(min_length=1)


class HoursWindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weekday: int
    opens: time
    closes: time


# ---------- reservations ----------


class ReservationCreate(BaseModel):
    table_id: int = Field(ge=1)
    start: datetime = Field(examples=["2026-10-01T17:00"])
    guest_count: int = Field(ge=1, le=50)
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(min_length=1, max_length=30)

    @field_validator("start")
    @classmethod
    def start_must_be_naive_local(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            raise ValueError(
                "times are restaurant-local; omit the timezone offset "
                "(2026-10-01T17:00, not 2026-10-01T17:00:00+08:00)"
            )
        return value


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    table: TableOut
    # Public API says `start`/`end`; the ORM columns are `start_time`/`end_time`.
    start: datetime = Field(validation_alias=AliasChoices("start", "start_time"))
    end: datetime = Field(validation_alias=AliasChoices("end", "end_time"))
    guest_count: int
    status: str
    customer_name: str
    customer_phone: str
    created_at: datetime
