from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_auth_routes_exist_in_openapi():
    paths = app.openapi().get("paths", {})

    assert "/auth/login" in paths
    assert "post" in paths["/auth/login"]

    assert "/auth/signup" in paths
    assert "post" in paths["/auth/signup"]


def test_login_route_is_reachable():
    probe_email = f"route-probe-{uuid4().hex}@example.com"

    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={
                "email": probe_email,
                "password": "Incorrect-Test-Password-2026!",
            },
        )

    # 401 proves the login endpoint executed.
    # A missing route would return 404.
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_signup_route_is_reachable():
    with TestClient(app) as client:
        response = client.post(
            "/auth/signup",
            json={},
        )

    # 422 proves FastAPI reached the signup endpoint
    # and validated its request body.
    assert response.status_code == 422
