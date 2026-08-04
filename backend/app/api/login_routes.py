from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.passwords import hash_password, verify_password
from app.core.tokens import (
    TokenValidationError,
    create_token,
    decode_token,
    hash_token,
)
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


class CurrentUserResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    is_verified: bool


def authentication_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Cookie"},
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    access_token = request.cookies.get(ACCESS_COOKIE_NAME)

    if not access_token:
        raise authentication_required()

    try:
        payload = decode_token(
            access_token,
            expected_type="access",
        )
    except TokenValidationError as exc:
        raise authentication_required() from exc

    user = db.scalar(
        select(User).where(
            User.id == UUID(str(payload["sub"]))
        )
    )

    if user is None:
        raise authentication_required()

    if not user.is_active or not user.is_verified:
        raise authentication_required()

    if int(payload["ver"]) != user.token_version:
        raise authentication_required()

    return CurrentUserResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_verified=user.is_verified,
    )


def clear_auth_cookies(response: Response) -> None:
    """Remove authentication cookies using their original paths."""

    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
    )

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    """
    Revoke the user's authentication sessions and remove browser cookies.

    The endpoint intentionally returns the same response for valid, missing,
    expired or malformed cookies to avoid leaking authentication state.
    """

    now = datetime.now(timezone.utc)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    # Browser cookies must always be removed, even for invalid tokens.
    clear_auth_cookies(response)

    if not refresh_token:
        return None

    try:
        payload = decode_token(
            refresh_token,
            expected_type="refresh",
        )
        user_id = UUID(str(payload["sub"]))
        token_version = int(payload["ver"])
    except (TokenValidationError, TypeError, ValueError, KeyError):
        return None

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.refresh_token_hash == hash_token(refresh_token),
        )
    )

    if user is None or auth_session is None:
        return None

    expires_at = as_utc(auth_session.expires_at)

    if (
        auth_session.is_revoked
        or expires_at is None
        or expires_at <= now
        or token_version != user.token_version
    ):
        return None

    # Incrementing token_version immediately invalidates old access tokens.
    user.token_version += 1

    active_sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()

    for session in active_sessions:
        session.revoked_at = now
        session.last_used_at = now

    db.commit()

    return None

