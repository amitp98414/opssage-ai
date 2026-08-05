from enum import StrEnum

from app.models.membership import MembershipRole


class Permission(StrEnum):
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    WORKSPACE_DELETE = "workspace:delete"

    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_ROLE_UPDATE = "member:role-update"
    MEMBER_REMOVE = "member:remove"

    AGENT_READ = "agent:read"
    AGENT_RUN = "agent:run"
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[
    MembershipRole,
    frozenset[Permission],
] = {
    MembershipRole.OWNER: frozenset(Permission),
    MembershipRole.ADMIN: frozenset(
        permission
        for permission in Permission
        if permission is not Permission.WORKSPACE_DELETE
    ),
    MembershipRole.ENGINEER: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.MEMBER_READ,
            Permission.AGENT_READ,
            Permission.AGENT_RUN,
        }
    ),
    MembershipRole.VIEWER: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.MEMBER_READ,
            Permission.AGENT_READ,
        }
    ),
}


def permissions_for(
    role: MembershipRole,
) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def has_permission(
    role: MembershipRole,
    permission: Permission,
) -> bool:
    return permission in permissions_for(role)
