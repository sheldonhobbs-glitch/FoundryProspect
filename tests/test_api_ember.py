"""The /api/ember endpoints, with the model replaced by a scripted fake."""

import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.main import app
from brain import service
from db.models import ShoppingListItem, Subscription, BillingCycle
from db.session import get_db
from tests.fakes import FakeProvider, text_turn, tool_turn


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)  # not a context manager: skips startup migrations (conftest already ran them)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def logged_in(client):
    client.get("/login/test-login-token", follow_redirects=False)
    client.post("/api/auth/identity", json={"name": "sheldon"})
    return client


def use_model(monkeypatch, script):
    provider = FakeProvider(script)
    monkeypatch.setattr(service, "get_provider", lambda: provider)
    return provider


def test_requires_login(client):
    assert client.post("/api/ember/message", json={"text": "hi"}).status_code == 401


def test_not_configured_without_api_key(logged_in, monkeypatch):
    monkeypatch.setattr(service, "get_provider", lambda: None)
    resp = logged_in.post("/api/ember/message", json={"text": "hi"})
    assert resp.status_code == 503 and "API key" in resp.json()["detail"]
    assert logged_in.get("/api/ember/conversation").json()["available"] is False


def test_message_round_trip(logged_in, monkeypatch, db):
    use_model(monkeypatch, [tool_turn(("add_to_shopping_list", {"items": [{"name": "milk"}]})),
                            text_turn("Added milk.")])

    resp = logged_in.post("/api/ember/message", json={"text": "we need milk"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Added milk."
    assert body["actions"] == [{"tool": "add_to_shopping_list", "summary": "Added milk to the shopping list."}]
    assert db.query(ShoppingListItem).one().added_by == "sheldon"


def test_confirm_and_cancel_endpoints(logged_in, monkeypatch, db):
    subs = [Subscription(name=n, cost=10, billing_cycle=BillingCycle.monthly, renewal_date="2026-10-04",
                         category="streaming", active=True) for n in ("Netflix", "Stan")]
    db.add_all(subs)
    db.commit()
    use_model(monkeypatch, [
        tool_turn(("cancel_subscription", {"subscription_id": subs[0].id}),
                  ("cancel_subscription", {"subscription_id": subs[1].id})),
        text_turn("Confirm cancelling both?"),
    ])

    body = logged_in.post("/api/ember/message", json={"text": "cancel netflix and stan"}).json()
    first, second = (p["id"] for p in body["pending"])

    assert logged_in.post(f"/api/ember/actions/{first}/confirm").json()["result"] == "Marked Netflix as cancelled."
    assert logged_in.post(f"/api/ember/actions/{first}/confirm").status_code == 409
    assert logged_in.post(f"/api/ember/actions/{second}/cancel").json() == {"ok": True}
    assert logged_in.post("/api/ember/actions/999999/confirm").status_code == 404

    db.refresh(subs[0])
    db.refresh(subs[1])
    assert (subs[0].active, subs[1].active) == (False, True)


def test_conversation_shows_plain_thread_and_open_confirmations(logged_in, monkeypatch, db):
    db.add(Subscription(name="Netflix", cost=10, billing_cycle=BillingCycle.monthly, renewal_date="2026-10-04",
                        category="streaming", active=True))
    db.commit()
    sub_id = db.query(Subscription).one().id
    use_model(monkeypatch, [tool_turn(("cancel_subscription", {"subscription_id": sub_id})),
                            text_turn("Want me to mark Netflix cancelled?")])
    logged_in.post("/api/ember/message", json={"text": "cancel netflix"})

    convo = logged_in.get("/api/ember/conversation").json()

    assert convo["messages"] == [
        {"role": "user", "text": "cancel netflix"},
        {"role": "assistant", "text": "Want me to mark Netflix cancelled?"},
    ]
    assert len(convo["pending"]) == 1


def test_daily_limit_returns_429(logged_in, monkeypatch):
    monkeypatch.setattr(get_settings(), "ember_daily_request_limit", 1)
    use_model(monkeypatch, [text_turn("Hi."), text_turn("Hi again.")])
    assert logged_in.post("/api/ember/message", json={"text": "hi"}).status_code == 200
    assert logged_in.post("/api/ember/message", json={"text": "hi"}).status_code == 429


def test_rejects_oversized_input(logged_in, monkeypatch):
    use_model(monkeypatch, [])
    assert logged_in.post("/api/ember/message", json={"text": "x" * 2001}).status_code == 422
