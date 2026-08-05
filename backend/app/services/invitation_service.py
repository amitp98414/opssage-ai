from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.rbac import Permission, has_permission
from app.core.tokens import hash_token
from app.models.invitation import Invitation
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User


INVITATION_TOKEN_BYTES = 32
INVITATION_LIFETIME = timedelta(hours=72)
UNAVAILABLE_MESSAGE = "Invitation is invalid or unavailable."


class InvitationUnavailableError(ValueError):
    """Raised without revealing why an invitation cannot be used."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _unavailable() -> InvitationUnavailableError:
    return InvitationUnavailableError(UNAVAILABLE_MESSAGE)


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()

    if not normalized:
        raise ValueError("Invitation email cannot be empty.")

    return normalized


def create_invitation(
    db: Session,
    *,
    actor_membership: Membership,
    email: str,
    role: MembershipRole,
    now: datetime | None = None,
    lifetime: timedelta = INVITATION_LIFETIME,
) -> tuple[Invitation, str]:
    """Create an invitation while returning its secret only once."""

    if (
        not actor_membership.is_active
        or not has_permission(
            actor_membership.role,
            Permission.MEMBER_INVITE,
        )
    ):
        raise PermissionError("Member invitation is not permitted.")

    target_role = MembershipRole(role)

    if target_role is MembershipRole.OWNER:
        raise ValueError("Owner invitations are not permitted.")

    if lifetime <= timedelta(0):
        raise ValueError("Invitation lifetime must be positive.")

    created_at = _as_utc(now or _utc_now())
    raw_token = secrets.token_urlsafe(INVITATION_TOKEN_BYTES)

    invitation = Invitation(
        organization_id=actor_membership.organization_id,
        invited_by_id=actor_membership.user_id,
        email=_normalize_email(email),
        role=target_role,
        token_hash=hash_token(raw_token),
        expires_at=created_at + lifetime,
        created_at=created_at,
    )

    db.add(invitation)
    db.flush()

    return invitation, raw_token


def _get_pending_invitation(
    db: Session,
    *,
    raw_token: str,
    now: datetime,
) -> Invitation:
    try:
        token_hash = hash_token(raw_token)
    except ValueError as exc:
        raise _unavailable() from exc

    invitation = db.scalar(
        select(Invitation).where(
            Invitation.token_hash == token_hash
        )
    )

    if invitation is None:
        raise _unavailable()

    if invitation.accepted_at is not None:
        raise _unavailable()

    if invitation.revoked_at is not None:
        raise _unavailable()

    if _as_utc(invitation.expires_at) <= now:
        raise _unavailable()

    return invitation


def revoke_invitation(
    db: Session,
    *,
    actor_membership: Membership,
    invitation: Invitation,
    now: datetime | None = None,
) -> Invitation:
    """Atomically revoke an invitation within the actor's tenant."""

    if (
        not actor_membership.is_active
        or actor_membership.organization_id
        != invitation.organization_id
        or not has_permission(
            actor_membership.role,
            Permission.MEMBER_INVITE,
        )
    ):
        raise PermissionError(
            "Invitation revocation is not permitted."
        )

    revoked_at = _as_utc(now or _utc_now())

    result = db.execute(
        update(Invitation)
        .where(
            Invitation.id == invitation.id,
            Invitation.organization_id
            == actor_membership.organization_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > revoked_at,
        )
        .values(revoked_at=revoked_at)
    )

    if result.rowcount != 1:
        raise _unavailable()

    db.flush()
    db.refresh(invitation)

    return invitation


def accept_invitation(
    db: Session,
    *,
    raw_token: str,
    user: User,
    now: datetime | None = None,
) -> Membership:
    """Consume an invitation once and create its tenant membership."""

    accepted_at = _as_utc(now or _utc_now())

    invitation = _get_pending_invitation(
        db,
        raw_token=raw_token,
        now=accepted_at,
    )

    if not user.is_active or not user.is_verified:
        raise _unavailable()

    if _normalize_email(user.email) != invitation.email:
        raise _unavailable()

    organization_is_active = db.scalar(
        select(Organization.is_active).where(
            Organization.id == invitation.organization_id
        )
    )

    if organization_is_active is not True:
        raise _unavailable()

    existing_membership = db.scalar(
        select(Membership.id).where(
            Membership.organization_id
            == invitation.organization_id,
            Membership.user_id == user.id,
        )
    )

    if existing_membership is not None:
        raise _unavailable()

    result = db.execute(
        update(Invitation)
        .where(
            Invitation.id == invitation.id,
            Invitation.token_hash == hash_token(raw_token),
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > accepted_at,
        )
        .values(accepted_at=accepted_at)
    )

    if result.rowcount != 1:
        raise _unavailable()

    membership = Membership(
        user_id=user.id,
        organization_id=invitation.organization_id,
        role=invitation.role,
        is_active=True,
    )

    db.add(membership)
    db.flush()

    return membership
