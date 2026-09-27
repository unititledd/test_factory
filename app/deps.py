"""Shared FastAPI dependencies."""

from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """One session per request, bound to the app's engine."""
    session = request.app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()


def require_admin(request: Request) -> None:
    """Guard for /api/admin/*.

    When ADMIN_API_KEY is configured, requests must carry a matching
    `X-Admin-Key` header. When it is unset (local development), the admin
    routes are open — the README calls this out for production.
    """
    expected = request.app.state.admin_api_key
    if expected is not None and request.headers.get("X-Admin-Key") != expected:
        raise HTTPException(status_code=401, detail="A valid X-Admin-Key header is required")
