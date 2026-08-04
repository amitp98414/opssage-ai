from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Convert a plain password into a secure Argon2id hash."""

    if not plain_password:
        raise ValueError("Password cannot be empty.")

    return _password_hash.hash(plain_password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Safely verify a password against its stored hash."""

    if not plain_password or not hashed_password:
        return False

    try:
        return _password_hash.verify(
            plain_password,
            hashed_password,
        )
    except Exception:
        return False
