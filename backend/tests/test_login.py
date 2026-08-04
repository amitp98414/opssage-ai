import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.passwords import hash_password
from app.core.tokens import decode_token, hash_token
from app.main import app
from app.models.auth_session import AuthSession
from app.models.membership import Membership  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.user import User


test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


def override_get_db():
    database = TestSessionLocal()
    try:
        yield database
    finally:
        database.close()


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(settings, "AUTH_SECRET_KEY", "a" * 96)
    monkeypatch.setattr(settings, "REFRESH_TOKEN_SECRET", "b" * 96)
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "SESSION_COOKIE_SAMESITE", "lax")
    monkeypatch.setattr(settings, "LOGIN_MAX_ATTEMPTS", 5)
    monkeypatch.setattr(settings, "LOGIN_LOCK_MINUTES", 15)

    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    test_client = TestClient(app)
    test_client.cookies.clear()
    return test_client


def create_user(
    *,
    email: str = "login-owner@example.com",
    password: str = "Secure-Login-Password-2026!",
    verified: bool = True,
    active: bool = True,
) -> User:
    user = User(
        email=email,
        full_name="Login Owner",
        password_hash=hash_password(password),
        is_verified=verified,
        is_active=active,
    )

    with TestSessionLocal() as db:
        db.add(user)
        db.commit()

    return user


def test_successful_login_creates_secure_cookies_and_session(client):
    user = create_user()

    response = client.post(
        "/auth/login",
        json={
            "email": "LOGIN-OWNER@EXAMPLE.COM",
            "password": "Secure-Login-Password-2026!",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Login successful."

    access_token = response.cookies.get("opssage_access")
    refresh_token = response.cookies.get("opssage_refresh")

    assert access_token
    assert refresh_token

    access_payload = decode_token(
        access_token,
        expected_type="access",
    )
    refresh_payload = decode_token(
        refresh_token,
        expected_type="refresh",
    )

    assert access_payload["sub"] == str(user.id)
    assert refresh_payload["sub"] == str(user.id)

    set_cookie_headers = response.headers.get_list("set-cookie")
    combined_headers = "\n".join(set_cookie_headers).lower()

    assert "opssage_access=" in combined_headers
    assert "opssage_refresh=" in combined_headers
    assert "httponly" in combined_headers
    assert "samesite=lax" in combined_headers

    with TestSessionLocal() as db:
        session = db.scalar(select(AuthSession))

        assert session is not None
        assert session.user_id == user.id
        assert session.refresh_token_hash == hash_token(refresh_token)
        assert session.refresh_token_hash != refresh_token


def test_wrong_password_and_unknown_email_use_generic_response(client):
    create_user()

    wrong_password = client.post(
        "/auth/login",
        json={
            "email": "login-owner@example.com",
            "password": "Wrong-Password-2026!",
        },
    )

    unknown_email = client.post(
        "/auth/login",
        json={
            "email": "unknown-user@example.com",
            "password": "Wrong-Password-2026!",
        },
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401

    assert wrong_password.json()["detail"] == "Invalid email or password."
    assert unknown_email.json()["detail"] == "Invalid email or password."


def test_account_is_locked_after_repeated_failures(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_ATTEMPTS", 3)

    create_user()

    payload = {
        "email": "login-owner@example.com",
        "password": "Wrong-Password-2026!",
    }

    for _ in range(3):
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 401

    locked_response = client.post(
        "/auth/login",
        json={
            "email": "login-owner@example.com",
            "password": "Secure-Login-Password-2026!",
        },
    )

    assert locked_response.status_code == 429
    assert "Retry-After" in locked_response.headers

    with TestSessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.email == "login-owner@example.com"
            )
        )

        assert user is not None
        assert user.failed_login_attempts == 3
        assert user.locked_until is not None


def test_unverified_account_cannot_login(client):
    create_user(verified=False)

    response = client.post(
        "/auth/login",
        json={
            "email": "login-owner@example.com",
            "password": "Secure-Login-Password-2026!",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Email verification is required before login."
    )

    assert response.cookies.get("opssage_access") is None
    assert response.cookies.get("opssage_refresh") is None

    with TestSessionLocal() as db:
        sessions = db.scalars(select(AuthSession)).all()
        assert sessions == []
