import pytest

from app.core.rbac import (
    Permission,
    ROLE_PERMISSIONS,
    has_permission,
)
from app.models.membership import MembershipRole


def test_permission_matrix_covers_every_role():
    assert set(ROLE_PERMISSIONS) == set(MembershipRole)


def test_owner_has_every_permission():
    assert ROLE_PERMISSIONS[MembershipRole.OWNER] == frozenset(
        Permission
    )


def test_admin_can_manage_members_but_cannot_delete_workspace():
    role = MembershipRole.ADMIN

    assert has_permission(role, Permission.MEMBER_INVITE)
    assert has_permission(role, Permission.MEMBER_ROLE_UPDATE)
    assert has_permission(role, Permission.MEMBER_REMOVE)
    assert not has_permission(role, Permission.WORKSPACE_DELETE)


def test_engineer_can_run_agent_but_cannot_manage_members():
    role = MembershipRole.ENGINEER

    assert has_permission(role, Permission.AGENT_RUN)
    assert has_permission(role, Permission.AGENT_READ)
    assert not has_permission(role, Permission.MEMBER_INVITE)
    assert not has_permission(role, Permission.WORKSPACE_UPDATE)


def test_viewer_has_read_only_access():
    role = MembershipRole.VIEWER

    assert has_permission(role, Permission.WORKSPACE_READ)
    assert has_permission(role, Permission.MEMBER_READ)
    assert has_permission(role, Permission.AGENT_READ)
    assert not has_permission(role, Permission.AGENT_RUN)
    assert not has_permission(role, Permission.MEMBER_INVITE)


@pytest.mark.parametrize("role", list(MembershipRole))
def test_every_role_can_read_workspace(role):
    assert has_permission(role, Permission.WORKSPACE_READ)
