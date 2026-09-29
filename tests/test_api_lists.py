from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db.models import Reminder, ShoppingListItem
from db.session import get_db
from domain.clock import household_today


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    c.get("/login/test-login-token", follow_redirects=False)
    yield c
    app.dependency_overrides.clear()


def test_today_reports_household_date_and_zone(client):
    body = client.get("/api/today").json()
    assert body == {"date": household_today().isoformat(), "timezone": "Australia/Brisbane"}


def test_shopping_list_and_check_off(client, db):
    db.add_all([ShoppingListItem(name="milk"), ShoppingListItem(name="bread")])
    db.commit()
    items = client.get("/api/shopping").json()
    assert [i["name"] for i in items] == ["milk", "bread"]

    assert client.post(f"/api/shopping/{items[0]['id']}/check").json()["checked"] is True
    assert [i["name"] for i in client.get("/api/shopping").json()] == ["bread"]
    assert client.post("/api/shopping/999999/check").status_code == 404


def test_reminders_due_today_and_complete(client, db):
    today = household_today()
    db.add_all([
        Reminder(text="Bins out", due_date=today),
        Reminder(text="Car service", due_date=date(today.year + 1, 1, 1)),
        Reminder(text="Someday"),
    ])
    db.commit()

    due = client.get("/api/reminders?due_today=true").json()
    assert [r["text"] for r in due] == ["Bins out"]
    assert len(client.get("/api/reminders").json()) == 3

    client.post(f"/api/reminders/{due[0]['id']}/complete")
    assert client.get("/api/reminders?due_today=true").json() == []


def test_lists_require_login(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        assert TestClient(app).get("/api/shopping").status_code == 401
    finally:
        app.dependency_overrides.clear()
