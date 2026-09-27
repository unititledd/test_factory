"""Booking lifecycle: happy path, conflicts, validation, cancellation."""

from datetime import datetime

BOOKING = {
    "table_id": 2,
    "start": "2026-10-01T17:00",
    "guest_count": 4,
    "customer_name": "Alice",
    "customer_phone": "13800000000",
}


def test_book_happy_path(restaurant):
    resp = restaurant.post("/api/reservations", json=BOOKING)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert datetime.fromisoformat(body["start"]) == datetime(2026, 10, 1, 17, 0)
    assert datetime.fromisoformat(body["end"]) == datetime(2026, 10, 1, 19, 0)
    assert body["status"] == "booked"
    assert body["table"]["name"] == "Booth-4"
    assert body["guest_count"] == 4


def test_double_booking_rejected(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 409


def test_same_table_next_slot_ok(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    nxt = dict(BOOKING, start="2026-10-01T19:00")
    assert restaurant.post("/api/reservations", json=nxt).status_code == 201


def test_another_table_same_slot_ok(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    other = dict(BOOKING, table_id=3, guest_count=8)
    assert restaurant.post("/api/reservations", json=other).status_code == 201


def test_guest_count_over_capacity(restaurant):
    resp = restaurant.post("/api/reservations", json=dict(BOOKING, guest_count=5))
    assert resp.status_code == 422


def test_unknown_table(restaurant):
    resp = restaurant.post("/api/reservations", json=dict(BOOKING, table_id=99))
    assert resp.status_code == 404


def test_past_start(restaurant):
    resp = restaurant.post("/api/reservations", json=dict(BOOKING, start="2026-09-30T17:00"))
    assert resp.status_code == 422


def test_non_slot_start(restaurant):
    resp = restaurant.post("/api/reservations", json=dict(BOOKING, start="2026-10-01T18:00"))
    assert resp.status_code == 422


def test_timezone_offset_rejected(restaurant):
    resp = restaurant.post(
        "/api/reservations", json=dict(BOOKING, start="2026-10-01T17:00:00+08:00")
    )
    assert resp.status_code == 422


def test_slot_must_fit_before_close(restaurant):
    # Open only 11:00-13:00 on Thursday: the single slot is 11:00-13:00;
    # a 13:00 start would run past closing and must be rejected.
    restaurant.put(
        "/api/admin/hours",
        json={"windows": [{"weekday": 3, "opens": "11:00", "closes": "13:00"}]},
    )
    ok = restaurant.post("/api/reservations", json=dict(BOOKING, start="2026-10-01T11:00"))
    assert ok.status_code == 201
    late = restaurant.post(
        "/api/reservations", json=dict(BOOKING, table_id=3, guest_count=8, start="2026-10-01T13:00")
    )
    assert late.status_code == 422


def test_db_unique_index_guards_race(restaurant, monkeypatch):
    """Even when the friendly pre-check race window is hit, the partial
    unique index rejects the second insert — the database is the source
    of truth, not the application check."""
    from app.services import availability

    monkeypatch.setattr(availability, "has_conflict", lambda *args, **kwargs: False)
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 409


def test_cancel_then_rebook(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    cancelled = restaurant.post("/api/reservations/1/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201


def test_cannot_cancel_twice(restaurant):
    restaurant.post("/api/reservations", json=BOOKING)
    assert restaurant.post("/api/reservations/1/cancel").status_code == 200
    assert restaurant.post("/api/reservations/1/cancel").status_code == 409


def test_get_by_id_and_by_date(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201

    got = restaurant.get("/api/reservations/1")
    assert got.status_code == 200
    assert got.json()["id"] == 1
    assert restaurant.get("/api/reservations/99").status_code == 404

    same_day = restaurant.get("/api/reservations", params={"date": "2026-10-01"})
    assert len(same_day.json()) == 1
    other_day = restaurant.get("/api/reservations", params={"date": "2026-10-02"})
    assert other_day.json() == []
    unfiltered = restaurant.get("/api/reservations")
    assert len(unfiltered.json()) == 1
