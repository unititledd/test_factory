# test_factory — Restaurant Reservations API

A backend service that manages restaurant dining reservations: search
available tables for a party and time window, book a table, and let
administrators configure table inventory and operating hours.

Stack: **Python 3.12 · FastAPI · SQLAlchemy 2 · SQLite**

## Quickstart

```powershell
cd test_factory
python -m venv .venv                      # once
.venv\Scripts\pip install -e ".[dev]"     # once
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Interactive OpenAPI docs: http://127.0.0.1:8000/docs

## How the domain works

- **Fixed two-hour seatings.** Every reservation is exactly 2 hours.
- **Grid-aligned slots.** Each operating window `[opens, closes)` generates
  seatings at `opens`, `opens+2h`, `opens+4h`, ... while the full seating
  still ends by `closes`. Example: hours 11:00-23:00 → seatings at
  11:00, 13:00, 15:00, 17:00, 19:00, 21:00.
- **Availability.** A table is available when its capacity fits the party
  and no active reservation on it overlaps the requested slot. Results are
  ordered smallest-fit-first.
- **Closed days.** A weekday with no configured hours is closed: no slots,
  no bookings. Multiple windows per day (lunch/dinner) are supported.
- **Admin config.** Tables (name + capacity) and the weekly operating
  schedule, via `/api/admin/*`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/api/availability?start=…&guests=…` | Free tables for a 2-hour slot + party size |
| POST | `/api/reservations` | Book a table |
| GET | `/api/reservations?date=…` | List reservations (optional day filter) |
| GET | `/api/reservations/{id}` | Fetch one reservation |
| POST | `/api/reservations/{id}/cancel` | Cancel (frees the table) |
| GET / POST | `/api/admin/tables` | List / add tables |
| PUT / DELETE | `/api/admin/tables/{id}` | Update / remove a table |
| GET / PUT | `/api/admin/hours` | Read / replace the weekly schedule |

Admin routes require the `X-Admin-Key` header when `ADMIN_API_KEY` is set;
unset (local dev) leaves them open.

### Walkthrough (curl)

```powershell
# 1. Configure operating hours: 11:00-23:00, all seven days
curl.exe -X PUT http://127.0.0.1:8000/api/admin/hours -H "Content-Type: application/json" -d "{\"windows\":[{\"weekday\":0,\"opens\":\"11:00\",\"closes\":\"23:00\"},{\"weekday\":1,\"opens\":\"11:00\",\"closes\":\"23:00\"},{\"weekday\":2,\"opens\":\"11:00\",\"closes\":\"23:00\"},{\"weekday\":3,\"opens\":\"11:00\",\"closes\":\"23:00\"},{\"weekday\":4,\"opens\":\"11:00\",\"closes\":\"23:00\"},{\"weekday\":5,\"opens\":\"11:00\",\"closes\":\"23:00\"},{\"weekday\":6,\"opens\":\"11:00\",\"closes\":\"23:00\"}]}"

# 2. Add a table
curl.exe -X POST http://127.0.0.1:8000/api/admin/tables -H "Content-Type: application/json" -d "{\"name\":\"Booth-4\",\"capacity\":4}"

# 3. Search free tables for 3 guests at 17:00
curl.exe "http://127.0.0.1:8000/api/availability?start=2026-10-01T17:00&guests=3"

# 4. Book table 1
curl.exe -X POST http://127.0.0.1:8000/api/reservations -H "Content-Type: application/json" -d "{\"table_id\":1,\"start\":\"2026-10-01T17:00\",\"guest_count\":3,\"customer_name\":\"Alice\",\"customer_phone\":\"13800000000\"}"

# 5. Try the same slot again -> 409 Conflict
# 6. Cancel -> the slot becomes bookable again
curl.exe -X POST http://127.0.0.1:8000/api/reservations/1/cancel
```

## Design decisions

- **SQLite via SQLAlchemy 2.** Zero-config, file-based; switch databases by
  setting `DATABASE_URL` (e.g. Postgres). The double-booking guard uses a
  partial unique index declared with both SQLite and Postgres variants.
- **Database-enforced atomicity.** A partial `UNIQUE (table_id, start_time)`
  index over active reservations means two concurrent bookings of the same
  slot cannot both commit — the loser gets a 409. The service does a
  friendly pre-check, but the database is the last line of defense.
- **Naive restaurant-local times.** All timestamps are wall-clock times in
  the restaurant's own timezone (`2026-10-01T17:00`); offsets are rejected.
  This matches how restaurants think about seatings and sidesteps DST
  edge cases for v1.
- **App factory.** `create_app(engine)` lets every test run against a
  private in-memory database.
- **Domain errors decoupled from HTTP.** Services raise typed domain errors
  (`app/errors.py`); a single handler maps them to status codes
  (404 / 409 / 422) so business logic stays framework-free.
- **Clock injection.** All "now" reads go through `app.clock.now()`, which
  tests pin for deterministic time-dependent behavior.

## Edge cases handled

- Overlapping / duplicate bookings → 409 (pre-check + unique index)
- Party larger than table capacity → 422
- Start not on the day's 2-hour grid → 422 with the valid `allowed_slots` list
- Booking or searching in the past → 422
- Closed weekday / day without hours → 422 (empty slot list)
- Slot that would run past closing time → 422
- Cancelling twice → 409; a cancelled slot becomes bookable again
- Deleting a table that still has active reservations → 409
- Shrinking a table below an existing booking's party size → 409
- Duplicate table names → 409; windows must open before close; no duplicate windows
- Timezone offsets in request times → 422

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```

~28 tests cover admin config, availability search, the booking lifecycle,
and the database-level race guard.

## Production hardening (out of scope for v1)

Alembic migrations, real authentication (per-admin JWT), pagination on
list endpoints, timezone-aware scheduling, observability, rate limiting.
