from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import require_permission
from app.core.rbac import (
    Permission,
    permissions_for,
)
from app.models.membership import (
    Membership,
    MembershipRole,
)


router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


class WorkspaceAccessResponse(BaseModel):
    workspace_id: UUID
    role: MembershipRole
    permissions: list[Permission]


@router.get(
    "/{workspace_id}/access",
    response_model=WorkspaceAccessResponse,
)
def workspace_access(
    membership: Membership = Depends(
        require_permission(Permission.WORKSPACE_READ)
    ),
) -> WorkspaceAccessResponse:
    permissions = sorted(
        permissions_for(membership.role),
        key=lambda permission: permission.value,
    )

    return WorkspaceAccessResponse(
        workspace_id=membership.organization_id,
        role=membership.role,
        permissions=permissions,
    )
