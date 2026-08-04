from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def unique_email() -> str:
    return f"test-{uuid4().hex}@example.com"


def test_create_subscription():
    response = client.post(
        "/subscriptions",
        json={
            "email": unique_email(),
            "company": "NovaCloud Technologies",
            "source": "test_suite",
            "consent": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "subscribed"


def test_duplicate_subscription_is_idempotent():
    email = unique_email()
    payload = {
        "email": email,
        "company": "NovaCloud Technologies",
        "source": "test_suite",
        "consent": True,
    }

    first = client.post("/subscriptions", json=payload)
    second = client.post("/subscriptions", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["status"] == "already_subscribed"


def test_subscription_requires_consent():
    response = client.post(
        "/subscriptions",
        json={
            "email": unique_email(),
            "source": "test_suite",
            "consent": False,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Consent is required to subscribe."


def test_subscription_rejects_invalid_email():
    response = client.post(
        "/subscriptions",
        json={
            "email": "not-an-email",
            "source": "test_suite",
            "consent": True,
        },
    )

    assert response.status_code == 422
