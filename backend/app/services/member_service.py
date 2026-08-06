from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.rbac import Permission, has_permission
from app.models.membership import Membership, MembershipRole
from app.models.user import User


class MemberOperationError(ValueError):
    pass


def list_members(
    db: Session,
    *,
    actor_membership: Membership,
) -> list[Membership]:
    if not actor_membership.is_active:
        raise MemberOperationError("Inactive membership.")

    return list(
        db.scalars(
            select(Membership).where(
                Membership.organization_id
                == actor_membership.organization_id
            )
        ).all()
    )


def update_member_role(
    db: Session,
    *,
    actor_membership: Membership,
    target_membership: Membership,
    role: MembershipRole,
) -> Membership:

    if not has_permission(
        actor_membership.role,
        Permission.MEMBER_ROLE_UPDATE,
    ):
        raise PermissionError(
            "Member role update not permitted."
        )

    if (
        actor_membership.organization_id
        != target_membership.organization_id
    ):
        raise MemberOperationError(
            "Tenant mismatch."
        )

    if target_membership.role is MembershipRole.OWNER:
        raise MemberOperationError(
            "Owner role cannot be changed."
        )

    target_membership.role = MembershipRole(role)

    db.flush()

    return target_membership


def remove_member(
    db: Session,
    *,
    actor_membership: Membership,
    target_membership: Membership,
) -> None:

    if not has_permission(
        actor_membership.role,
        Permission.MEMBER_REMOVE,
    ):
        raise PermissionError(
            "Member removal not permitted."
        )

    if (
        actor_membership.organization_id
        != target_membership.organization_id
    ):
        raise MemberOperationError(
            "Tenant mismatch."
        )

    if target_membership.role is MembershipRole.OWNER:
        raise MemberOperationError(
            "Owner cannot be removed."
        )

    db.execute(
        update(Membership)
        .where(
            Membership.id == target_membership.id
        )
        .values(
            is_active=False
        )
    )

    db.flush()
