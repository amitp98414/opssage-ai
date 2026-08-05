from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.passwords import hash_password
from app.models.invitation import Invitation
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.services.invitation_service import (
    InvitationUnavailableError,
    accept_invitation,
    create_invitation,
    revoke_invitation,
)


FIXED_NOW = datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc)

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSession = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def create_identities(
    db,
    *,
    actor_role=MembershipRole.OWNER,
):
    actor = User(
        email="owner@example.com",
        full_name="Workspace Owner",
        password_hash=hash_password(
            "Secure-Invitation-Owner-Password-2026!"
        ),
        is_verified=True,
    )

    invitee = User(
        email="invitee@example.com",
        full_name="Invited Engineer",
        password_hash=hash_password(
            "Secure-Invitation-User-Password-2026!"
        ),
        is_verified=True,
    )

    organization = Organization(
        name="Invitation Test Workspace",
        slug="invitation-test-workspace",
    )

    actor_membership = Membership(
        user=actor,
        organization=organization,
        role=actor_role,
    )

    db.add_all([actor_membership, invitee])
    db.commit()

    return actor_membership, invitee


def test_create_invitation_returns_secret_once_and_stores_only_hash():
    with TestSession() as db:
        actor_membership, _ = create_identities(db)

        invitation, raw_token = create_invitation(
            db,
            actor_membership=actor_membership,
            email="  INVITEE@EXAMPLE.COM  ",
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
        )
        db.commit()

        stored = db.scalar(select(Invitation))

        assert stored is not None
        assert stored.id == invitation.id
        assert stored.email == "invitee@example.com"
        assert stored.role is MembershipRole.ENGINEER
        assert stored.token_hash != raw_token
        assert len(stored.token_hash) == 64
        assert len(raw_token) >= 43
        assert invitation.expires_at == (
            FIXED_NOW + timedelta(hours=72)
        )


def test_owner_role_cannot_be_invited():
    with TestSession() as db:
        actor_membership, _ = create_identities(db)

        with pytest.raises(ValueError):
            create_invitation(
                db,
                actor_membership=actor_membership,
                email="invitee@example.com",
                role=MembershipRole.OWNER,
                now=FIXED_NOW,
            )


def test_viewer_cannot_create_invitation():
    with TestSession() as db:
        actor_membership, _ = create_identities(
            db,
            actor_role=MembershipRole.VIEWER,
        )

        with pytest.raises(PermissionError):
            create_invitation(
                db,
                actor_membership=actor_membership,
                email="invitee@example.com",
                role=MembershipRole.ENGINEER,
                now=FIXED_NOW,
            )


def test_invitation_email_must_match_without_consuming_token():
    with TestSession() as db:
        actor_membership, invitee = create_identities(db)

        invitation, raw_token = create_invitation(
            db,
            actor_membership=actor_membership,
            email="different@example.com",
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
        )
        db.commit()

        with pytest.raises(InvitationUnavailableError):
            accept_invitation(
                db,
                raw_token=raw_token,
                user=invitee,
                now=FIXED_NOW + timedelta(minutes=1),
            )

        db.refresh(invitation)
        assert invitation.accepted_at is None


def test_expired_invitation_is_rejected():
    with TestSession() as db:
        actor_membership, invitee = create_identities(db)

        _, raw_token = create_invitation(
            db,
            actor_membership=actor_membership,
            email=invitee.email,
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
            lifetime=timedelta(minutes=5),
        )
        db.commit()

        with pytest.raises(InvitationUnavailableError):
            accept_invitation(
                db,
                raw_token=raw_token,
                user=invitee,
                now=FIXED_NOW + timedelta(minutes=5),
            )


def test_revoked_invitation_is_rejected():
    with TestSession() as db:
        actor_membership, invitee = create_identities(db)

        invitation, raw_token = create_invitation(
            db,
            actor_membership=actor_membership,
            email=invitee.email,
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
        )

        revoke_invitation(
            db,
            actor_membership=actor_membership,
            invitation=invitation,
            now=FIXED_NOW + timedelta(minutes=1),
        )
        db.commit()

        with pytest.raises(InvitationUnavailableError):
            accept_invitation(
                db,
                raw_token=raw_token,
                user=invitee,
                now=FIXED_NOW + timedelta(minutes=2),
            )


def test_viewer_cannot_revoke_invitation():
    with TestSession() as db:
        actor_membership, invitee = create_identities(db)

        invitation, _ = create_invitation(
            db,
            actor_membership=actor_membership,
            email=invitee.email,
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
        )

        actor_membership.role = MembershipRole.VIEWER
        db.commit()

        with pytest.raises(PermissionError, match="revocation"):
            revoke_invitation(
                db,
                actor_membership=actor_membership,
                invitation=invitation,
                now=FIXED_NOW + timedelta(minutes=1),
            )

        db.refresh(invitation)
        assert invitation.revoked_at is None


def test_spoofed_invitation_cannot_bypass_tenant_boundary():
    with TestSession() as db:
        actor_membership, _ = create_identities(db)

        other_owner = User(
            email="spoof-test-owner@example.com",
            full_name="Spoof Test Owner",
            password_hash=hash_password(
                "Spoof-Test-Owner-Password-2026!"
            ),
            is_verified=True,
        )

        other_organization = Organization(
            name="Spoof Test Workspace",
            slug="spoof-test-workspace",
        )

        other_membership = Membership(
            user=other_owner,
            organization=other_organization,
            role=MembershipRole.OWNER,
        )

        db.add(other_membership)
        db.commit()

        victim_invitation, _ = create_invitation(
            db,
            actor_membership=other_membership,
            email="victim@example.com",
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
        )
        db.commit()

        spoofed_invitation = Invitation(
            id=victim_invitation.id,
            organization_id=actor_membership.organization_id,
            invited_by_id=actor_membership.user_id,
            email=victim_invitation.email,
            role=victim_invitation.role,
            token_hash=victim_invitation.token_hash,
            expires_at=victim_invitation.expires_at,
            created_at=victim_invitation.created_at,
        )

        with pytest.raises(InvitationUnavailableError):
            revoke_invitation(
                db,
                actor_membership=actor_membership,
                invitation=spoofed_invitation,
                now=FIXED_NOW + timedelta(minutes=1),
            )

        db.refresh(victim_invitation)
        assert victim_invitation.revoked_at is None


def test_member_cannot_revoke_invitation_from_another_workspace():
    with TestSession() as db:
        actor_membership, invitee = create_identities(db)

        invitation, _ = create_invitation(
            db,
            actor_membership=actor_membership,
            email=invitee.email,
            role=MembershipRole.ENGINEER,
            now=FIXED_NOW,
        )

        other_owner = User(
            email="other-owner@example.com",
            full_name="Other Workspace Owner",
            password_hash=hash_password(
                "Other-Workspace-Owner-Password-2026!"
            ),
            is_verified=True,
        )

        other_organization = Organization(
            name="Other Workspace",
            slug="other-workspace",
        )

        other_membership = Membership(
            user=other_owner,
            organization=other_organization,
            role=MembershipRole.OWNER,
        )

        db.add(other_membership)
        db.commit()

        with pytest.raises(PermissionError, match="revocation"):
            revoke_invitation(
                db,
                actor_membership=other_membership,
                invitation=invitation,
                now=FIXED_NOW + timedelta(minutes=1),
            )

        db.refresh(invitation)
        assert invitation.revoked_at is None


def test_accept_invitation_creates_membership_exactly_once():
    with TestSession() as db:
        actor_membership, invitee = create_identities(db)

        invitation, raw_token = create_invitation(
            db,
            actor_membership=actor_membership,
            email=invitee.email,
            role=MembershipRole.ADMIN,
            now=FIXED_NOW,
        )
        db.commit()

        membership = accept_invitation(
            db,
            raw_token=raw_token,
            user=invitee,
            now=FIXED_NOW + timedelta(minutes=1),
        )
        db.commit()
        db.refresh(invitation)

        assert invitation.accepted_at is not None
        assert membership.user_id == invitee.id
        assert membership.organization_id == (
            actor_membership.organization_id
        )
        assert membership.role is MembershipRole.ADMIN

        with pytest.raises(InvitationUnavailableError):
            accept_invitation(
                db,
                raw_token=raw_token,
                user=invitee,
                now=FIXED_NOW + timedelta(minutes=2),
            )

        memberships = db.scalars(
            select(Membership).where(
                Membership.user_id == invitee.id,
                Membership.organization_id
                == actor_membership.organization_id,
            )
        ).all()

        assert len(memberships) == 1
