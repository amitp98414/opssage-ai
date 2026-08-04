import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.passwords import hash_password
from app.core.tokens import create_token
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

    monkeypatch.setattr(
        settings,
        "AUTH_SECRET_KEY",
        "a" * 96,
    )
    monkeypatch.setattr(
        settings,
        "REFRESH_TOKEN_SECRET",
        "b" * 96,
    )
    monkeypatch.setattr(
        settings,
        "SESSION_COOKIE_SECURE",
        False,
    )

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


def create_identity(
    *,
    role: MembershipRole = MembershipRole.OWNER,
    membership_active: bool = True,
):
    user = User(
        email=f"{role.value}@example.com",
        full_name=f"Test {role.value.title()}",
        password_hash=hash_password(
            "Secure-Workspace-Password-2026!"
        ),
        is_verified=True,
        is_active=True,
    )

    workspace = Organization(
        name=f"{role.value.title()} Workspace",
        slug=f"{role.value}-workspace",
    )

    membership = Membership(
        user=user,
        organization=workspace,
        role=role,
        is_active=membership_active,
    )

    with TestSessionLocal() as db:
        db.add(membership)
        db.commit()
        db.refresh(user)
        db.refresh(workspace)

    return user, workspace


def authenticate(client, user):
    token = create_token(
        user_id=user.id,
        token_version=user.token_version,
        token_type="access",
    )
    client.cookies.set("opssage_access", token)


def test_owner_can_access_own_workspace(client):
    user, workspace = create_identity()
    authenticate(client, user)

    response = client.get(
        f"/workspaces/{workspace.id}/access"
    )

    assert response.status_code == 200
    assert response.json()["workspace_id"] == str(workspace.id)
    assert response.json()["role"] == "owner"
    assert "workspace:read" in response.json()["permissions"]


def test_viewer_has_read_only_workspace_access(client):
    user, workspace = create_identity(
        role=MembershipRole.VIEWER
    )
    authenticate(client, user)

    response = client.get(
        f"/workspaces/{workspace.id}/access"
    )

    assert response.status_code == 200
    assert response.json()["role"] == "viewer"
    assert "workspace:read" in response.json()["permissions"]
    assert "workspace:delete" not in response.json()["permissions"]


def test_unauthenticated_request_is_rejected(client):
    _, workspace = create_identity()

    response = client.get(
        f"/workspaces/{workspace.id}/access"
    )

    assert response.status_code == 401


def test_cross_tenant_access_is_hidden(client):
    user, _ = create_identity()
    authenticate(client, user)

    other_workspace = Organization(
        name="Other Company",
        slug="other-company",
    )

    with TestSessionLocal() as db:
        db.add(other_workspace)
        db.commit()
        db.refresh(other_workspace)

    response = client.get(
        f"/workspaces/{other_workspace.id}/access"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found."


def test_inactive_membership_is_rejected(client):
    user, workspace = create_identity(
        membership_active=False
    )
    authenticate(client, user)

    response = client.get(
        f"/workspaces/{workspace.id}/access"
    )

    assert response.status_code == 404
