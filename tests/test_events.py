from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _first_outlet_id(client, headers: dict[str, str]) -> int:
    response = client.get("/api/v1/outlets", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items
    return items[0]["id"]


def _first_table_id(client, headers: dict[str, str], outlet_id: int) -> int:
    response = client.get("/api/v1/tables/tables", headers=headers, params={"outlet_id": outlet_id})
    assert response.status_code == 200
    tables = response.json()
    assert tables
    return tables[0]["id"]


def test_events_crud_and_confirm(client):
    headers = _auth_headers(client)
    outlet_id = _first_outlet_id(client, headers)
    table_id = _first_table_id(client, headers, outlet_id)
    event_date = (date.today() + timedelta(days=14)).isoformat()

    create_response = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "event_type": "birthday",
            "title": "Test Birthday Party",
            "customer_name": "Test Guest",
            "customer_phone": "+91 90000 00001",
            "event_date": event_date,
            "start_time": "19:00",
            "duration_minutes": 180,
            "expected_guests": 12,
            "estimated_amount": 5000,
            "advance_paid": 1000,
            "table_ids": [table_id],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    event_id = created["id"]
    assert created["status"] == "inquiry"
    assert created["title"] == "Test Birthday Party"

    list_response = client.get("/api/v1/events", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == event_id for item in list_response.json()["data"]["items"])

    detail_response = client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["tables"]

    patch_response = client.patch(
        f"/api/v1/events/{event_id}",
        headers=headers,
        json={"expected_guests": 15, "special_requests": "Balloon decor"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["expected_guests"] == 15

    confirm_response = client.post(
        f"/api/v1/events/{event_id}/confirm",
        headers=headers,
        json={"table_ids": [table_id], "send_whatsapp": False},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"


def test_event_packages_and_birthday_opportunities(client):
    headers = _auth_headers(client)

    packages_response = client.get("/api/v1/events/packages", headers=headers)
    assert packages_response.status_code == 200
    packages = packages_response.json()
    assert len(packages) >= 1
    assert packages[0]["name"]

    opportunities_response = client.get(
        "/api/v1/events/birthday-opportunities",
        headers=headers,
        params={"days_ahead": 30},
    )
    assert opportunities_response.status_code == 200
    assert isinstance(opportunities_response.json(), list)


def test_events_summary_report(client):
    headers = _auth_headers(client)
    response = client.get("/api/v1/reports/events-summary", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "total_events" in payload
    assert "events" in payload


def test_public_event_inquiry(client):
    outlet_id = _first_outlet_id(client, _auth_headers(client))
    event_date = (date.today() + timedelta(days=21)).isoformat()

    response = client.post(
        "/api/v1/events/public/inquiry",
        json={
            "outlet_id": outlet_id,
            "event_type": "birthday",
            "title": "Online Birthday Inquiry",
            "customer_name": "Online Guest",
            "customer_phone": "+91 90000 00099",
            "event_date": event_date,
            "expected_guests": 20,
            "package_id": "birthday-standard",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["event_id"]
    assert payload["status"] == "inquiry"


def test_event_preorders_and_pos_order(client):
    headers = _auth_headers(client)
    outlet_id = _first_outlet_id(client, headers)
    menu_response = client.get("/api/v1/menu/items", headers=headers, params={"page": 1, "page_size": 5})
    assert menu_response.status_code == 200
    menu_items = menu_response.json()["data"]["items"]
    assert menu_items

    event_date = (date.today() + timedelta(days=10)).isoformat()
    create_response = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "event_type": "corporate",
            "title": "Pre-order Test Lunch",
            "customer_name": "Corp Guest",
            "customer_phone": "+91 90000 00002",
            "event_date": event_date,
            "start_time": "12:30",
            "expected_guests": 12,
        },
    )
    event_id = create_response.json()["id"]

    preorder_response = client.put(
        f"/api/v1/events/{event_id}/preorders",
        headers=headers,
        json={
            "items": [
                {"menu_item_id": menu_items[0]["id"], "quantity": 12},
            ]
        },
    )
    assert preorder_response.status_code == 200
    assert len(preorder_response.json()) == 1

    confirm_response = client.post(
        f"/api/v1/events/{event_id}/confirm",
        headers=headers,
        json={},
    )
    assert confirm_response.status_code == 200

    pos_response = client.post(
        f"/api/v1/events/{event_id}/create-pos-order",
        headers=headers,
    )
    assert pos_response.status_code == 200
    pos_payload = pos_response.json()
    assert pos_payload["pos_order_id"]
    assert pos_payload["order_number"]
