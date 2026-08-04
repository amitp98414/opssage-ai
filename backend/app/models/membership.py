from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PythonEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class MembershipRole(str, PythonEnum):
    OWNER = "owner"
    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


membership_role_type = Enum(
    MembershipRole,
    name="membership_role",
    native_enum=False,
    validate_strings=True,
    values_callable=lambda enum_class: [
        member.value for member in enum_class
    ],
)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_memberships_user_organization",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[MembershipRole] = mapped_column(
        membership_role_type,
        nullable=False,
        default=MembershipRole.VIEWER,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(
        back_populates="memberships",
    )

    organization: Mapped["Organization"] = relationship(
        back_populates="memberships",
    )
