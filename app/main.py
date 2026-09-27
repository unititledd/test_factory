"""Application factory and wiring."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app import config
from app.database import make_engine, make_sessionmaker
from app.errors import DomainError
from app.models import Base
from app.routers import admin, availability, reservations


def create_app(engine=None) -> FastAPI:
    """Build the app. Tests pass their own (in-memory) engine."""
    if engine is None:
        engine = make_engine(config.DATABASE_URL)

    app = FastAPI(
        title="Restaurant Reservations API",
        version="0.1.0",
        description=(
            "Manages restaurant dining reservations.\n\n"
            "* Reservations are fixed at **two-hour intervals**, aligned to operating hours.\n"
            "* `GET /api/availability` finds free tables for a party and a slot.\n"
            "* `POST /api/reservations` books a table.\n"
            "* `/api/admin/*` configures table inventory and operating hours.\n\n"
            "All times are restaurant-local (e.g. `2026-10-01T17:00`)."
        ),
    )
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.admin_api_key = config.ADMIN_API_KEY

    Base.metadata.create_all(engine)

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail, **exc.extra}
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        # Friendly landing: browsers hitting the API root land on the docs.
        return RedirectResponse(url="/docs")

    app.include_router(availability.router)
    app.include_router(reservations.router)
    app.include_router(admin.router)
    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
