"""Shared fixtures: a fresh app per test, a pinned clock, a standard restaurant."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import make_memory_engine
from app.main import create_app

# Deterministic "now": Thursday, 2026-10-01, 10:00 restaurant-local time.
# All future-dated requests in tests use Thursday 2026-10-01 slots.
TEST_NOW = datetime(2026, 10, 1, 10, 0)


def make_client(admin_key: str | None = None) -> TestClient:
    """An app backed by a private in-memory database."""
    app = create_app(engine=make_memory_engine())
    if admin_key is not None:
        app.state.admin_api_key = admin_key
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return make_client()


@pytest.fixture
def client_factory():
    """Factory for apps with a specific admin key; use in one-off tests."""
    return make_client


@pytest.fixture(autouse=True)
def pin_clock(monkeypatch):
    from app import clock

    monkeypatch.setattr(clock, "now", lambda: TEST_NOW)


@pytest.fixture
def restaurant(client) -> TestClient:
    """Standard setup: open 11:00-23:00 daily; tables of 2, 4, and 8 seats.

    Table ids: 1 = Window-2 (2 seats), 2 = Booth-4 (4 seats), 3 = Big-8 (8 seats).
    Daily slots at 11:00, 13:00, 15:00, 17:00, 19:00, 21:00.
    """
    client.put(
        "/api/admin/hours",
        json={
            "windows": [
                {"weekday": d, "opens": "11:00", "closes": "23:00"} for d in range(7)
            ]
        },
    )
    client.post("/api/admin/tables", json={"name": "Window-2", "capacity": 2})
    client.post("/api/admin/tables", json={"name": "Booth-4", "capacity": 4})
    client.post("/api/admin/tables", json={"name": "Big-8", "capacity": 8})
    return client
