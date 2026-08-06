from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_workspace_membership,
)
from app.core.rbac import Permission
from app.models.membership import Membership, MembershipRole
from app.services.member_service import (
    list_members,
    update_member_role,
    remove_member,
    MemberOperationError,
)


router = APIRouter(tags=["Members"])


class MemberRoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MembershipRole


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: MembershipRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[MemberResponse],
)
def get_members(
    actor_membership: Membership = Depends(
        get_workspace_membership
    ),
    db: Session = Depends(get_db),
):
    try:
        return list_members(
            db,
            actor_membership=actor_membership,
        )
    except MemberOperationError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.patch(
    "/workspaces/{workspace_id}/members/{member_id}",
    response_model=MemberResponse,
)
def change_member_role(
    member_id: UUID,
    payload: MemberRoleUpdateRequest,
    actor_membership: Membership = Depends(
        get_workspace_membership
    ),
    db: Session = Depends(get_db),
):

    target = db.scalar(
        select(Membership).where(
            Membership.id == member_id,
            Membership.organization_id
            == actor_membership.organization_id,
        )
    )

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Member not found.",
        )

    try:
        return update_member_role(
            db,
            actor_membership=actor_membership,
            target_membership=target,
            role=payload.role,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except MemberOperationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.delete(
    "/workspaces/{workspace_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_member(
    member_id: UUID,
    actor_membership: Membership = Depends(
        get_workspace_membership
    ),
    db: Session = Depends(get_db),
):

    target = db.scalar(
        select(Membership).where(
            Membership.id == member_id,
            Membership.organization_id
            == actor_membership.organization_id,
        )
    )

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Member not found.",
        )

    try:
        remove_member(
            db,
            actor_membership=actor_membership,
            target_membership=target,
        )
        db.commit()

    except PermissionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except MemberOperationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
