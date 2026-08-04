from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.passwords import verify_password
from app.main import app
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User


test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def override_get_db():
    database = TestSessionLocal()
    try:
        yield database
    finally:
        database.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db

    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)


def signup_payload(
    email: str | None = None,
    organization_name: str = "NovaCloud Technologies",
):
    return {
        "email": email or f"owner-{uuid4().hex}@example.com",
        "full_name": "NovaCloud Owner",
        "organization_name": organization_name,
        "password": "Secure-OpsSage-Password-2026!",
        "accept_terms": True,
    }


def test_signup_creates_user_organization_and_owner_membership():
    payload = signup_payload("Owner@Example.com")

    response = client.post("/auth/signup", json=payload)

    assert response.status_code == 201
    body = response.json()

    assert body["role"] == "owner"
    assert body["verification_required"] is True

    with TestSessionLocal() as db:
        user = db.scalar(
            select(User).where(User.email == "owner@example.com")
        )
        organization = db.scalar(select(Organization))
        membership = db.scalar(select(Membership))

        assert user is not None
        assert organization is not None
        assert membership is not None

        assert membership.user_id == user.id
        assert membership.organization_id == organization.id
        assert membership.role == MembershipRole.OWNER


def test_password_is_stored_only_as_argon2id_hash():
    password = "Secure-OpsSage-Password-2026!"
    payload = signup_payload()
    payload["password"] = password

    response = client.post("/auth/signup", json=payload)

    assert response.status_code == 201

    with TestSessionLocal() as db:
        user = db.scalar(select(User))

        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert password not in user.password_hash
        assert verify_password(password, user.password_hash) is True


def test_duplicate_email_is_rejected():
    payload = signup_payload("duplicate@example.com")

    first = client.post("/auth/signup", json=payload)
    second = client.post("/auth/signup", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409

    with TestSessionLocal() as db:
        users = db.scalars(select(User)).all()
        assert len(users) == 1


def test_terms_must_be_accepted():
    payload = signup_payload()
    payload["accept_terms"] = False

    response = client.post("/auth/signup", json=payload)

    assert response.status_code == 422


def test_common_password_is_rejected():
    payload = signup_payload()
    payload["password"] = "password123"

    response = client.post("/auth/signup", json=payload)

    assert response.status_code == 422


def test_same_company_name_generates_unique_slugs():
    first = client.post(
        "/auth/signup",
        json=signup_payload(
            "first@example.com",
            "NovaCloud Technologies",
        ),
    )

    second = client.post(
        "/auth/signup",
        json=signup_payload(
            "second@example.com",
            "NovaCloud Technologies",
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    first_slug = first.json()["organization_slug"]
    second_slug = second.json()["organization_slug"]

    assert first_slug == "novacloud-technologies"
    assert second_slug != first_slug
    assert second_slug.startswith("novacloud-technologies-")
