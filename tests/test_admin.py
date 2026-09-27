"""Admin configuration: table inventory and operating hours."""

BOOKING = {
    "table_id": 2,
    "start": "2026-10-01T17:00",
    "guest_count": 4,
    "customer_name": "Alice",
    "customer_phone": "13800000000",
}


def test_create_and_list_tables(client):
    resp = client.post("/api/admin/tables", json={"name": "Patio-6", "capacity": 6})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Patio-6"
    assert body["capacity"] == 6
    assert body["id"] == 1

    listing = client.get("/api/admin/tables")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_duplicate_table_name_rejected(client):
    client.post("/api/admin/tables", json={"name": "Booth-4", "capacity": 4})
    resp = client.post("/api/admin/tables", json={"name": "Booth-4", "capacity": 6})
    assert resp.status_code == 409


def test_update_table(restaurant):
    resp = restaurant.put("/api/admin/tables/2", json={"capacity": 6})
    assert resp.status_code == 200
    assert resp.json()["capacity"] == 6
    assert resp.json()["name"] == "Booth-4"


def test_cannot_shrink_below_active_booking(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    resp = restaurant.put("/api/admin/tables/2", json={"capacity": 2})
    assert resp.status_code == 409


def test_delete_table_without_reservations(restaurant):
    assert restaurant.delete("/api/admin/tables/1").status_code == 204
    names = {t["name"] for t in restaurant.get("/api/admin/tables").json()}
    assert names == {"Booth-4", "Big-8"}


def test_delete_table_with_active_reservation_rejected(restaurant):
    assert restaurant.post("/api/reservations", json=BOOKING).status_code == 201
    assert restaurant.delete("/api/admin/tables/2").status_code == 409


def test_delete_unknown_table(restaurant):
    assert restaurant.delete("/api/admin/tables/99").status_code == 404


def test_hours_roundtrip(restaurant):
    hours = restaurant.get("/api/admin/hours")
    assert hours.status_code == 200
    windows = hours.json()
    assert len(windows) == 7
    first = {k: v for k, v in windows[0].items() if k != "id"}
    assert first == {"weekday": 0, "opens": "11:00:00", "closes": "23:00:00"}


def test_invalid_window_rejected(client):
    resp = client.put(
        "/api/admin/hours",
        json={"windows": [{"weekday": 0, "opens": "12:00", "closes": "11:00"}]},
    )
    assert resp.status_code == 422


def test_duplicate_window_rejected(client):
    resp = client.put(
        "/api/admin/hours",
        json={
            "windows": [
                {"weekday": 0, "opens": "11:00", "closes": "14:00"},
                {"weekday": 0, "opens": "11:00", "closes": "23:00"},
            ]
        },
    )
    assert resp.status_code == 422


def test_admin_key_enforced(client_factory):
    guarded = client_factory(admin_key="s3cret")
    assert guarded.get("/api/admin/tables").status_code == 401
    assert guarded.get("/api/admin/tables", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert guarded.get("/api/admin/tables", headers={"X-Admin-Key": "s3cret"}).status_code == 200
    # Public routes stay open.
    assert guarded.get("/health").status_code == 200
