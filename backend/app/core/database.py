from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all OpsSage AI database models."""


engine_options: dict = {
    "pool_pre_ping": True,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request."""

    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def init_db() -> None:
    """Create the current schema for local and preview deployments.

    Production deployments should run versioned Alembic migrations before
    starting the application.
    """
    from app.models.auth_session import AuthSession  # noqa: F401
    from app.models.invitation import Invitation  # noqa: F401
    from app.models.membership import Membership  # noqa: F401
    from app.models.organization import Organization  # noqa: F401
    from app.models.subscriber import Subscriber  # noqa: F401
    from app.models.user import User  # noqa: F401
    

    Base.metadata.create_all(bind=engine)
