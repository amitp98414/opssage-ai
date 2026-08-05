from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.invitation import Invitation
from app.models.membership import MembershipRole


def test_invitation_model_enforces_secure_persistence():
    table = Invitation.__table__

    assert set(table.columns.keys()) == {
        "id",
        "organization_id",
        "invited_by_id",
        "email",
        "role",
        "token_hash",
        "expires_at",
        "accepted_at",
        "revoked_at",
        "created_at",
    }

    assert "token" not in table.columns
    assert table.c.token_hash.type.length == 64
    assert table.c.email.type.length == 320
    assert table.c.role.default.arg is MembershipRole.VIEWER

    foreign_keys = {
        foreign_key.parent.name: (
            foreign_key.target_fullname,
            foreign_key.ondelete,
        )
        for foreign_key in table.foreign_keys
    }

    assert foreign_keys == {
        "organization_id": ("organizations.id", "CASCADE"),
        "invited_by_id": ("users.id", "RESTRICT"),
    }

    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "uq_invitations_token_hash" in unique_names
    assert "ck_invitations_role_not_owner" in check_names
