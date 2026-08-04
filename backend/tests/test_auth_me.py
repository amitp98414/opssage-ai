import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.passwords import hash_password
from app.core.tokens import create_token
from app.main import app
from app.models.auth_session import AuthSession  # noqa: F401
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
    verified: bool = True,
    active: bool = True,
) -> User:
    user = User(
        email="profile-owner@example.com",
        full_name="Profile Owner",
        password_hash=hash_password(
            "Secure-Profile-Password-2026!"
        ),
        is_verified=verified,
        is_active=active,
    )

    with TestSessionLocal() as db:
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def create_access_token(user: User) -> str:
    return create_token(
        user_id=user.id,
        token_version=user.token_version,
        token_type="access",
    )


def test_authenticated_user_can_access_profile(client):
    user = create_user()
    token = create_access_token(user)

    client.cookies.set("opssage_access", token)

    response = client.get("/auth/me")

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"] == str(user.id)
    assert body["email"] == "profile-owner@example.com"
    assert body["full_name"] == "Profile Owner"
    assert body["is_verified"] is True

    assert "password" not in body
    assert "password_hash" not in body


def test_missing_access_cookie_is_rejected(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


def test_tampered_access_token_is_rejected(client):
    user = create_user()
    token = create_access_token(user)

    tampered = token[:-1] + (
        "a" if token[-1] != "a" else "b"
    )

    client.cookies.set("opssage_access", tampered)

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_old_token_is_rejected_after_token_version_change(client):
    user = create_user()
    old_token = create_access_token(user)

    with TestSessionLocal() as db:
        stored_user = db.scalar(
            select(User).where(User.id == user.id)
        )
        stored_user.token_version += 1
        db.commit()

    client.cookies.set("opssage_access", old_token)

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_inactive_user_is_rejected(client):
    user = create_user(active=False)
    token = create_access_token(user)

    client.cookies.set("opssage_access", token)

    response = client.get("/auth/me")

    assert response.status_code == 401
