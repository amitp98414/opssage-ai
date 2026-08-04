from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


TokenType = Literal["access", "refresh"]
ALLOWED_ALGORITHMS = {"HS256"}


class TokenValidationError(ValueError):
    """Raised when an authentication token is invalid or unsafe."""


def _get_algorithm() -> str:
    algorithm = settings.JWT_ALGORITHM

    if algorithm not in ALLOWED_ALGORITHMS:
        raise RuntimeError("Unsupported JWT signing algorithm.")

    return algorithm


def _get_secret(token_type: TokenType) -> str:
    secret = (
        settings.AUTH_SECRET_KEY
        if token_type == "access"
        else settings.REFRESH_TOKEN_SECRET
    )

    if len(secret) < 64:
        raise RuntimeError(
            f"{token_type.title()} token secret is not securely configured."
        )

    return secret


def create_token(
    *,
    user_id: UUID,
    token_version: int,
    token_type: TokenType,
) -> str:
    """Create a signed, expiring authentication token."""

    now = datetime.now(timezone.utc)

    lifetime = (
        timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
        if token_type == "access"
        else timedelta(days=settings.REFRESH_TOKEN_DAYS)
    )

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "typ": token_type,
        "ver": token_version,
        "jti": uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + lifetime,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }

    return jwt.encode(
        payload,
        _get_secret(token_type),
        algorithm=_get_algorithm(),
    )


def decode_token(
    token: str,
    *,
    expected_type: TokenType,
) -> dict[str, Any]:
    """Verify signature, claims, audience, issuer, expiry and token type."""

    if not token:
        raise TokenValidationError("Token is missing.")

    try:
        payload = jwt.decode(
            token,
            _get_secret(expected_type),
            algorithms=[_get_algorithm()],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=5,
            options={
                "require": [
                    "sub",
                    "typ",
                    "ver",
                    "jti",
                    "iat",
                    "nbf",
                    "exp",
                    "iss",
                    "aud",
                ],
            },
        )
    except InvalidTokenError as exc:
        raise TokenValidationError("Token is invalid or expired.") from exc

    if payload.get("typ") != expected_type:
        raise TokenValidationError("Incorrect token type.")

    try:
        UUID(str(payload["sub"]))
        int(payload["ver"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("Token claims are invalid.") from exc

    return payload
