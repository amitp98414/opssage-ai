from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.passwords import hash_password
from app.core.tokens import create_token, hash_token
from app.main import app
from app.models.invitation import Invitation
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


def create_identity(
    *,
    email: str,
    slug: str,
    role: MembershipRole = MembershipRole.OWNER,
):
    actor = User(
        email=email,
        full_name="Invitation API Actor",
        password_hash=hash_password(
            "Secure-Invitation-API-Password-2026!"
        ),
        is_verified=True,
    )
    workspace = Organization(
        name="Invitation API Workspace",
        slug=slug,
    )
    membership = Membership(
        user=actor,
        organization=workspace,
        role=role,
    )

    with TestSessionLocal() as db:
        db.add(membership)
        db.commit()

    return actor, workspace


def create_user(email: str) -> User:
    invited_user = User(
        email=email,
        full_name="Invited User",
        password_hash=hash_password(
            "Secure-Invited-User-Password-2026!"
        ),
        is_verified=True,
    )

    with TestSessionLocal() as db:
        db.add(invited_user)
        db.commit()

    return invited_user


def authenticate(client: TestClient, user: User) -> None:
    access_token = create_token(
        user_id=user.id,
        token_version=user.token_version,
        token_type="access",
    )
    client.cookies.set("opssage_access", access_token)


def invite(
    client: TestClient,
    *,
    actor: User,
    workspace: Organization,
    email: str,
    role: str = "engineer",
):
    authenticate(client, actor)
    return client.post(
        f"/workspaces/{workspace.id}/invitations",
        json={"email": email, "role": role},
    )


def test_owner_creates_non_cacheable_hashed_invitation(client):
    owner, workspace = create_identity(
        email="owner@example.com",
        slug="owner-workspace",
    )

    response = invite(
        client,
        actor=owner,
        workspace=workspace,
        email="  INVITEE@EXAMPLE.COM  ",
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["email"] == "invitee@example.com"
    assert body["role"] == "engineer"
    assert len(body["token"]) >= 43

    with TestSessionLocal() as db:
        invitation = db.scalar(select(Invitation))
        assert invitation is not None
        assert invitation.token_hash == hash_token(body["token"])
        assert invitation.token_hash != body["token"]


def test_owner_role_cannot_be_invited_through_api(client):
    owner, workspace = create_identity(
        email="owner-role@example.com",
        slug="owner-role-workspace",
    )

    response = invite(
        client,
        actor=owner,
        workspace=workspace,
        email="invitee@example.com",
        role="owner",
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Owner invitations are not permitted."
    )


@pytest.mark.parametrize(
    ("case", "expected_status", "expected_detail"),
    [
        ("unauthenticated", 401, "Authentication required."),
        ("engineer", 403, "Permission denied."),
        ("cross-tenant", 404, "Workspace not found."),
    ],
)
def test_invitation_creation_access_controls(
    client,
    case,
    expected_status,
    expected_detail,
):
    _, target_workspace = create_identity(
        email="target-owner@example.com",
        slug="target-workspace",
    )
    request_workspace = target_workspace

    if case == "engineer":
        actor, request_workspace = create_identity(
            email="engineer@example.com",
            slug="engineer-workspace",
            role=MembershipRole.ENGINEER,
        )
        authenticate(client, actor)
    elif case == "cross-tenant":
        actor, _ = create_identity(
            email="other-owner@example.com",
            slug="other-workspace",
        )
        authenticate(client, actor)

    response = client.post(
        f"/workspaces/{request_workspace.id}/invitations",
        json={"email": "invitee@example.com", "role": "engineer"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_owner_revokes_own_pending_invitation(client):
    owner, workspace = create_identity(
        email="revoke-owner@example.com",
        slug="revoke-workspace",
    )
    created = invite(
        client,
        actor=owner,
        workspace=workspace,
        email="revoke-invitee@example.com",
    )
    invitation_id = UUID(created.json()["invitation_id"])

    response = client.delete(
        f"/workspaces/{workspace.id}/invitations/{invitation_id}"
    )

    assert response.status_code == 204

    with TestSessionLocal() as db:
        invitation = db.get(Invitation, invitation_id)
        assert invitation is not None
        assert invitation.revoked_at is not None


def test_cross_tenant_revocation_is_hidden(client):
    first_owner, first_workspace = create_identity(
        email="first-owner@example.com",
        slug="first-workspace",
    )
    second_owner, second_workspace = create_identity(
        email="second-owner@example.com",
        slug="second-workspace",
    )
    created = invite(
        client,
        actor=second_owner,
        workspace=second_workspace,
        email="protected@example.com",
    )
    invitation_id = UUID(created.json()["invitation_id"])

    authenticate(client, first_owner)
    response = client.delete(
        f"/workspaces/{first_workspace.id}/invitations/{invitation_id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Invitation not found."

    with TestSessionLocal() as db:
        invitation = db.get(Invitation, invitation_id)
        assert invitation is not None
        assert invitation.revoked_at is None


def test_matching_user_accepts_invitation_exactly_once(client):
    owner, workspace = create_identity(
        email="accept-owner@example.com",
        slug="accept-workspace",
    )
    invited_user = create_user("accept-invitee@example.com")
    created = invite(
        client,
        actor=owner,
        workspace=workspace,
        email=invited_user.email,
        role="admin",
    )
    raw_token = created.json()["token"]

    authenticate(client, invited_user)
    accepted = client.post(
        "/invitations/accept",
        json={"token": raw_token},
    )

    assert accepted.status_code == 200
    assert accepted.json()["workspace_id"] == str(workspace.id)
    assert accepted.json()["role"] == "admin"

    replayed = client.post(
        "/invitations/accept",
        json={"token": raw_token},
    )
    assert replayed.status_code == 400
    assert replayed.json()["detail"] == (
        "Invitation is invalid or unavailable."
    )

    with TestSessionLocal() as db:
        memberships = db.scalars(
            select(Membership).where(
                Membership.user_id == invited_user.id,
                Membership.organization_id == workspace.id,
            )
        ).all()
        assert len(memberships) == 1


def test_wrong_user_gets_generic_error_without_token_consumption(client):
    owner, workspace = create_identity(
        email="generic-owner@example.com",
        slug="generic-workspace",
    )
    expected_user = create_user("expected@example.com")
    wrong_user = create_user("wrong@example.com")
    created = invite(
        client,
        actor=owner,
        workspace=workspace,
        email=expected_user.email,
    )
    invitation_id = UUID(created.json()["invitation_id"])
    raw_token = created.json()["token"]

    authenticate(client, wrong_user)
    wrong_email = client.post(
        "/invitations/accept",
        json={"token": raw_token},
    )
    invalid_token = client.post(
        "/invitations/accept",
        json={"token": "not-a-valid-invitation-token"},
    )

    assert wrong_email.status_code == 400
    assert invalid_token.status_code == 400
    assert wrong_email.json() == invalid_token.json()

    with TestSessionLocal() as db:
        invitation = db.get(Invitation, invitation_id)
        assert invitation is not None
        assert invitation.accepted_at is None
