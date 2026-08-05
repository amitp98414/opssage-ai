from datetime import datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    require_permission,
)
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.invitation import Invitation
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.services.invitation_service import (
    UNAVAILABLE_MESSAGE,
    InvitationUnavailableError,
    accept_invitation,
    create_invitation,
    revoke_invitation,
)


router = APIRouter(tags=["Invitations"])


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    email: EmailStr
    role: MembershipRole


class InvitationCreateResponse(BaseModel):
    invitation_id: UUID
    email: EmailStr
    role: MembershipRole
    expires_at: datetime
    token: str


class InvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)


class InvitationAcceptResponse(BaseModel):
    message: str
    membership_id: UUID
    workspace_id: UUID
    role: MembershipRole


def invitation_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Invitation not found.",
    )


def invitation_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=UNAVAILABLE_MESSAGE,
    )


@router.post(
    "/workspaces/{workspace_id}/invitations",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_invitation(
    payload: InvitationCreateRequest,
    response: Response,
    actor_membership: Membership = Depends(
        require_permission(Permission.MEMBER_INVITE)
    ),
    db: Session = Depends(get_db),
) -> InvitationCreateResponse:
    try:
        invitation, raw_token = create_invitation(
            db,
            actor_membership=actor_membership,
            email=str(payload.email),
            role=payload.role,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation could not be created.",
        ) from exc

    response.headers["Cache-Control"] = "no-store"

    return InvitationCreateResponse(
        invitation_id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        token=raw_token,
    )


@router.delete(
    "/workspaces/{workspace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_workspace_invitation(
    invitation_id: UUID,
    actor_membership: Membership = Depends(
        require_permission(Permission.MEMBER_INVITE)
    ),
    db: Session = Depends(get_db),
) -> None:
    invitation = db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id
            == actor_membership.organization_id,
        )
    )

    if invitation is None:
        raise invitation_not_found()

    try:
        revoke_invitation(
            db,
            actor_membership=actor_membership,
            invitation=invitation,
        )
        db.commit()
    except InvitationUnavailableError as exc:
        db.rollback()
        raise invitation_not_found() from exc
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        ) from exc

    return None


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptResponse,
)
def accept_workspace_invitation(
    payload: InvitationAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationAcceptResponse:
    try:
        membership = accept_invitation(
            db,
            raw_token=payload.token,
            user=current_user,
        )
        db.commit()
    except InvitationUnavailableError as exc:
        db.rollback()
        raise invitation_unavailable() from exc
    except IntegrityError as exc:
        db.rollback()
        raise invitation_unavailable() from exc

    return InvitationAcceptResponse(
        message="Invitation accepted successfully.",
        membership_id=membership.id,
        workspace_id=membership.organization_id,
        role=membership.role,
    )
