"""Availability search behavior."""

from datetime import datetime

ALL_SLOTS = [datetime(2026, 10, 1, h) for h in (11, 13, 15, 17, 19, 21)]


def test_lists_tables_that_fit(restaurant):
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T17:00", "guests": 2}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert datetime.fromisoformat(body["start"]) == datetime(2026, 10, 1, 17, 0)
    assert datetime.fromisoformat(body["end"]) == datetime(2026, 10, 1, 19, 0)
    assert [t["name"] for t in body["available_tables"]] == ["Window-2", "Booth-4", "Big-8"]


def test_filters_by_party_size(restaurant):
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T17:00", "guests": 6}
    )
    assert [t["name"] for t in resp.json()["available_tables"]] == ["Big-8"]


def test_no_table_large_enough(restaurant):
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T17:00", "guests": 9}
    )
    assert resp.status_code == 200
    assert resp.json()["available_tables"] == []


def test_non_slot_start_lists_valid_slots(restaurant):
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T18:00", "guests": 2}
    )
    assert resp.status_code == 422
    assert [datetime.fromisoformat(s) for s in resp.json()["allowed_slots"]] == ALL_SLOTS


def test_closed_day_has_no_slots(client):
    # The bare `client` fixture configures no hours: every day is closed.
    resp = client.get(
        "/api/availability", params={"start": "2026-10-01T17:00", "guests": 2}
    )
    assert resp.status_code == 422
    assert resp.json()["allowed_slots"] == []


def test_past_search_rejected(restaurant):
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T09:00", "guests": 2}
    )
    assert resp.status_code == 422


def test_timezone_offset_rejected(restaurant):
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T17:00:00+08:00", "guests": 2}
    )
    assert resp.status_code == 422


def test_booked_table_excluded(restaurant):
    booking = {
        "table_id": 2,
        "start": "2026-10-01T17:00",
        "guest_count": 4,
        "customer_name": "Alice",
        "customer_phone": "13800000000",
    }
    assert restaurant.post("/api/reservations", json=booking).status_code == 201
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T17:00", "guests": 3}
    )
    # Window-2 seats 2 (too small), Booth-4 is booked -> only Big-8 remains.
    assert [t["name"] for t in resp.json()["available_tables"]] == ["Big-8"]


def test_cancelled_reservation_frees_table(restaurant):
    booking = {
        "table_id": 2,
        "start": "2026-10-01T17:00",
        "guest_count": 4,
        "customer_name": "Alice",
        "customer_phone": "13800000000",
    }
    restaurant.post("/api/reservations", json=booking)
    restaurant.post("/api/reservations/1/cancel")
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T17:00", "guests": 3}
    )
    assert [t["name"] for t in resp.json()["available_tables"]] == ["Booth-4", "Big-8"]


def test_other_slot_unaffected(restaurant):
    booking = {
        "table_id": 2,
        "start": "2026-10-01T17:00",
        "guest_count": 4,
        "customer_name": "Alice",
        "customer_phone": "13800000000",
    }
    restaurant.post("/api/reservations", json=booking)
    resp = restaurant.get(
        "/api/availability", params={"start": "2026-10-01T19:00", "guests": 3}
    )
    assert [t["name"] for t in resp.json()["available_tables"]] == ["Booth-4", "Big-8"]
