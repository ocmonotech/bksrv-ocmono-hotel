"""Housekeeping API smoke tests."""


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_housekeeping_dashboard_requires_auth(client):
    response = client.get("/api/v1/housekeeping/dashboard")
    assert response.status_code in (401, 403)


def test_housekeeping_dashboard_with_auth(client):
    headers = _auth_headers(client)
    response = client.get("/api/v1/housekeeping/dashboard", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    data = payload.get("data", payload)
    assert "total_rooms" in data
    assert "occupancy_rate" in data


def test_list_housekeeping_rooms_with_auth(client):
    headers = _auth_headers(client)
    response = client.get("/api/v1/housekeeping/rooms", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    data = payload.get("data", payload)
    assert "items" in data
    assert "total" in data


def test_floor_assignments_and_schedules(client):
    headers = _auth_headers(client)
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"page_size": 1},
    )
    assert rooms_resp.status_code == 200
    rooms_payload = rooms_resp.json()
    rooms_data = rooms_payload.get("data", rooms_payload)
    items = rooms_data.get("items", [])
    if not items:
        return
    outlet_id = items[0]["outlet_id"]

    list_resp = client.get(
        "/api/v1/housekeeping/floor-assignments",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert list_resp.status_code == 200

    staff_resp = client.get("/api/v1/housekeeping/staff", headers=headers)
    assert staff_resp.status_code == 200
    staff_payload = staff_resp.json()
    staff = staff_payload if isinstance(staff_payload, list) else staff_payload.get("data", [])
    if staff:
        floor = items[0].get("floor", "1")
        housekeeper_id = staff[0]["id"]
        put_resp = client.put(
            "/api/v1/housekeeping/floor-assignments",
            headers=headers,
            json={
                "outlet_id": outlet_id,
                "assignments": [{"floor": floor, "housekeeper_id": housekeeper_id}],
            },
        )
        assert put_resp.status_code == 200
        saved = put_resp.json()
        saved_data = saved if isinstance(saved, list) else saved.get("data", saved)
        assert any(row["floor"] == floor for row in saved_data)

    sched_resp = client.get(
        "/api/v1/housekeeping/schedules",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert sched_resp.status_code == 200

    upsert_resp = client.put(
        "/api/v1/housekeeping/schedules",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "sweep_type": "checkout",
            "run_time": "06:30",
            "enabled": True,
            "distribute_by_floor": True,
            "use_floor_assignments": True,
        },
    )
    assert upsert_resp.status_code == 200


def test_run_due_sweep_schedules_all_tenants(client):
    headers = _auth_headers(client)
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"page_size": 1},
    )
    assert rooms_resp.status_code == 200
    items = rooms_resp.json().get("data", rooms_resp.json()).get("items", [])
    if not items:
        return
    outlet_id = items[0]["outlet_id"]

    upsert_resp = client.put(
        "/api/v1/housekeeping/schedules",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "sweep_type": "daily",
            "run_time": "00:00",
            "enabled": True,
            "distribute_by_floor": True,
            "use_floor_assignments": True,
        },
    )
    assert upsert_resp.status_code == 200

    run_resp = client.post(
        "/api/v1/housekeeping/schedules/run-due",
        headers=headers,
        params={"outlet_id": outlet_id, "force": True},
    )
    assert run_resp.status_code == 200
    payload = run_resp.json()
    data = payload.get("data", payload)
    assert data.get("schedules_run", 0) >= 1
