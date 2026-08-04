from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.passwords import hash_password
from app.core.tokens import hash_token
from app.models.auth_session import AuthSession
from app.models.membership import Membership  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.user import User


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSession = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def create_user() -> User:
    return User(
        email="session-owner@example.com",
        full_name="Session Owner",
        password_hash=hash_password(
            "Secure-Session-Password-2026!"
        ),
    )


def test_refresh_token_is_stored_only_as_hash():
    raw_token = "high-entropy-refresh-token-value"
    token_hash = hash_token(raw_token)

    with TestSession() as db:
        user = create_user()
        db.add(user)
        db.flush()

        session = AuthSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=7)
            ),
        )

        db.add(session)
        db.commit()

        stored = db.scalar(select(AuthSession))

        assert stored is not None
        assert stored.refresh_token_hash == token_hash
        assert stored.refresh_token_hash != raw_token
        assert len(stored.refresh_token_hash) == 64


def test_empty_token_cannot_be_hashed():
    with pytest.raises(ValueError):
        hash_token("")


def test_duplicate_refresh_token_hash_is_rejected():
    token_hash = hash_token("unique-refresh-token")

    with TestSession() as db:
        user = create_user()
        db.add(user)
        db.flush()

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=7)
        )

        db.add_all(
            [
                AuthSession(
                    user_id=user.id,
                    refresh_token_hash=token_hash,
                    expires_at=expires_at,
                ),
                AuthSession(
                    user_id=user.id,
                    refresh_token_hash=token_hash,
                    expires_at=expires_at,
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()


def test_deleting_user_removes_auth_sessions():
    with TestSession() as db:
        user = create_user()
        db.add(user)
        db.flush()

        db.add(
            AuthSession(
                user_id=user.id,
                refresh_token_hash=hash_token(
                    "cascade-test-refresh-token"
                ),
                expires_at=(
                    datetime.now(timezone.utc)
                    + timedelta(days=7)
                ),
            )
        )
        db.commit()

        db.delete(user)
        db.commit()

        sessions = db.scalars(select(AuthSession)).all()

        assert sessions == []
