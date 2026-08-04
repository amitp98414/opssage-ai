import pytest

from app.core.passwords import hash_password, verify_password


def test_password_is_hashed_with_argon2id():
    password = "OpsSage-Secure-Test-Password-2026!"

    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert password not in hashed
    assert verify_password(password, hashed) is True


def test_wrong_password_is_rejected():
    hashed = hash_password("Correct-Secure-Password-2026!")

    assert verify_password(
        "Wrong-Password-2026!",
        hashed,
    ) is False


def test_empty_password_cannot_be_hashed():
    with pytest.raises(ValueError):
        hash_password("")
