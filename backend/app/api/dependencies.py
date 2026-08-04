from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.login_routes import (
    ACCESS_COOKIE_NAME,
    authentication_required,
)
from app.core.database import get_db
from app.core.rbac import Permission, has_permission
from app.core.tokens import TokenValidationError, decode_token
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    access_token = request.cookies.get(ACCESS_COOKIE_NAME)

    if not access_token:
        raise authentication_required()

    try:
        payload = decode_token(
            access_token,
            expected_type="access",
        )
        user_id = UUID(str(payload["sub"]))
        token_version = int(payload["ver"])
    except (
        TokenValidationError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise authentication_required() from exc

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise authentication_required()

    if not user.is_active or not user.is_verified:
        raise authentication_required()

    if token_version != user.token_version:
        raise authentication_required()

    return user


def workspace_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Workspace not found.",
    )


def get_workspace_membership(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership:
    membership = db.scalar(
        select(Membership)
        .join(
            Organization,
            Organization.id == Membership.organization_id,
        )
        .where(
            Membership.organization_id == workspace_id,
            Membership.user_id == current_user.id,
            Membership.is_active.is_(True),
            Organization.is_active.is_(True),
        )
    )

    if membership is None:
        raise workspace_not_found()

    return membership


def require_permission(
    permission: Permission,
) -> Callable[..., Membership]:
    def permission_dependency(
        membership: Membership = Depends(
            get_workspace_membership
        ),
    ) -> Membership:
        if not has_permission(
            membership.role,
            permission,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            )

        return membership

    return permission_dependency
