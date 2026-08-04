from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_token, hash_token
from app.models.auth_session import AuthSession
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])

ACCESS_COOKIE_NAME = "opssage_access"
REFRESH_COOKIE_NAME = "opssage_refresh"

# Prevent major timing differences when an email does not exist.
DUMMY_PASSWORD_HASH = hash_password(
    "OpsSage-Dummy-Authentication-Password-2026!"
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    message: str
    user_id: UUID
    email: EmailStr


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def cookie_samesite() -> str:
    value = settings.SESSION_COOKIE_SAMESITE.lower()

    if value not in {"lax", "strict", "none"}:
        return "lax"

    if value == "none" and not settings.SESSION_COOKIE_SECURE:
        return "lax"

    return value


def invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Cookie"},
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    now = datetime.now(timezone.utc)
    normalized_email = str(payload.email).strip().lower()

    user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    if user is None:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise invalid_credentials()

    locked_until = as_utc(user.locked_until)

    if locked_until is not None and locked_until > now:
        retry_after = max(
            1,
            int((locked_until - now).total_seconds()),
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    if locked_until is not None and locked_until <= now:
        user.locked_until = None
        user.failed_login_attempts = 0

    password_valid = verify_password(
        payload.password,
        user.password_hash,
    )

    if not password_valid:
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(
                minutes=settings.LOGIN_LOCK_MINUTES
            )

        db.commit()
        raise invalid_credentials()

    if not user.is_active:
        raise invalid_credentials()

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification is required before login.",
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    access_token = create_token(
        user_id=user.id,
        token_version=user.token_version,
        token_type="access",
    )

    refresh_token = create_token(
        user_id=user.id,
        token_version=user.token_version,
        token_type="refresh",
    )

    refresh_expires_at = now + timedelta(
        days=settings.REFRESH_TOKEN_DAYS
    )

    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        expires_at=refresh_expires_at,
    )

    db.add(auth_session)
    db.commit()

    same_site = cookie_samesite()

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_MINUTES * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=same_site,
        path="/",
    )

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=same_site,
        path="/auth",
    )

    return LoginResponse(
        message="Login successful.",
        user_id=user.id,
        email=user.email,
    )
