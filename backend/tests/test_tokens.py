from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.tokens import (
    TokenValidationError,
    create_token,
    decode_token,
)


@pytest.fixture(autouse=True)
def secure_test_secrets(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AUTH_SECRET_KEY",
        "a" * 96,
    )
    monkeypatch.setattr(
        settings,
        "REFRESH_TOKEN_SECRET",
        "b" * 96,
    )


def test_access_token_is_signed_and_verified():
    user_id = uuid4()

    token = create_token(
        user_id=user_id,
        token_version=1,
        token_type="access",
    )

    payload = decode_token(
        token,
        expected_type="access",
    )

    assert payload["sub"] == str(user_id)
    assert payload["typ"] == "access"
    assert payload["ver"] == 1
    assert payload["jti"]


def test_refresh_token_uses_separate_token_type():
    user_id = uuid4()

    token = create_token(
        user_id=user_id,
        token_version=3,
        token_type="refresh",
    )

    payload = decode_token(
        token,
        expected_type="refresh",
    )

    assert payload["sub"] == str(user_id)
    assert payload["typ"] == "refresh"
    assert payload["ver"] == 3


def test_refresh_token_cannot_be_used_as_access_token():
    token = create_token(
        user_id=uuid4(),
        token_version=1,
        token_type="refresh",
    )

    with pytest.raises(TokenValidationError):
        decode_token(
            token,
            expected_type="access",
        )


def test_tampered_token_is_rejected():
    token = create_token(
        user_id=uuid4(),
        token_version=1,
        token_type="access",
    )

    header, payload, signature = token.split(".")

    tampered_signature = (
        ("a" if signature[0] != "a" else "b")
        + signature[1:]
    )

    tampered = ".".join(
        (header, payload, tampered_signature)
    )

    with pytest.raises(TokenValidationError):
        decode_token(
            tampered,
            expected_type="access",
        )


def test_missing_secure_secret_is_rejected(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AUTH_SECRET_KEY",
        "",
    )

    with pytest.raises(RuntimeError):
        create_token(
            user_id=uuid4(),
            token_version=1,
            token_type="access",
        )
