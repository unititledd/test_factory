# AGENTS.md — project guide for Droid

Restaurant reservations backend: FastAPI + SQLAlchemy 2 + PostgreSQL
(SQLite fallback for zero-setup runs).

## Commands

- Run tests: `.venv\Scripts\python.exe -m pytest` (from repo root)
- Run dev server: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
- Install deps: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- OpenAPI docs: http://127.0.0.1:8000/docs

## Conventions

- `app/main.py` exposes `create_app(engine)`; tests inject in-memory
  engines. Keep the factory pattern.
- Business rules live in `app/services/`; routers stay thin.
- Raise domain errors from `app/errors.py` (mapped to HTTP in `main.py`);
  never raise HTTPException from services.
- Times are naive restaurant-local datetimes; read "now" via
  `app.clock.now()` (tests pin it — never call `datetime.now()` directly).
- Reservations are exactly 2 hours and grid-aligned to operating windows
  (see `app/services/availability.py`).
- Double-booking safety = service pre-check + partial unique index
  `uq_active_reservation_slot`; don't drop either.
- Database: PostgreSQL in dev/prod via `DATABASE_URL` from a git-ignored
  `.env`; falls back to `./reservations.db` (SQLite) when unset. Tests run
  on in-memory SQLite.
- Never commit `.env` or any credentials.
