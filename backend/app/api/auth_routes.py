import re
import secrets
from typing import Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.passwords import hash_password
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


COMMON_PASSWORDS = {
    "password123",
    "admin123456",
    "qwerty123456",
    "letmein123456",
    "123456789012",
}


class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    organization_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    accept_terms: bool

    @model_validator(mode="after")
    def validate_security_requirements(self) -> Self:
        if not self.accept_terms:
            raise ValueError("Terms and privacy policy must be accepted.")

        normalized_password = self.password.casefold()
        if normalized_password in COMMON_PASSWORDS:
            raise ValueError("This password is too common.")

        email_local_part = str(self.email).split("@", maxsplit=1)[0].casefold()
        if len(email_local_part) >= 4 and email_local_part in normalized_password:
            raise ValueError("Password must not contain the email username.")

        return self


class SignupResponse(BaseModel):
    message: str
    user_id: UUID
    organization_id: UUID
    organization_slug: str
    role: MembershipRole
    verification_required: bool


def create_slug(value: str) -> str:
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        value.casefold(),
    ).strip("-")

    return slug[:100] or f"workspace-{secrets.token_hex(4)}"


def create_unique_slug(
    db: Session,
    organization_name: str,
) -> str:
    base_slug = create_slug(organization_name)
    slug = base_slug

    while db.scalar(
        select(Organization.id).where(Organization.slug == slug)
    ):
        suffix = secrets.token_hex(3)
        slug = f"{base_slug[:110]}-{suffix}"

    return slug


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db),
) -> SignupResponse:
    normalized_email = str(payload.email).strip().lower()

    existing_user = db.scalar(
        select(User.id).where(User.email == normalized_email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account cannot be created with these details.",
        )

    organization = Organization(
        name=payload.organization_name,
        slug=create_unique_slug(
            db,
            payload.organization_name,
        ),
    )

    user = User(
        email=normalized_email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_verified=False,
    )

    membership = Membership(
        user=user,
        organization=organization,
        role=MembershipRole.OWNER,
    )

    db.add(membership)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account cannot be created with these details.",
        ) from exc

    return SignupResponse(
        message="Account created. Email verification is required.",
        user_id=user.id,
        organization_id=organization.id,
        organization_slug=organization.slug,
        role=membership.role,
        verification_required=True,
    )
