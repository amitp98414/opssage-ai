import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.passwords import hash_password
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _):
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


def create_user(email: str = "owner@novacloud.example") -> User:
    return User(
        email=email.lower(),
        full_name="NovaCloud Owner",
        password_hash=hash_password(
            "Secure-Test-Password-2026!"
        ),
    )


def create_organization(
    slug: str = "novacloud-technologies",
) -> Organization:
    return Organization(
        name="NovaCloud Technologies",
        slug=slug,
    )


def test_owner_membership_is_created():
    with TestSession() as db:
        user = create_user()
        organization = create_organization()

        membership = Membership(
            user=user,
            organization=organization,
            role=MembershipRole.OWNER,
        )

        db.add(membership)
        db.commit()

        stored = db.scalar(select(Membership))

        assert stored is not None
        assert stored.role == MembershipRole.OWNER
        assert stored.user.email == "owner@novacloud.example"
        assert stored.organization.slug == "novacloud-technologies"


def test_duplicate_user_email_is_rejected():
    with TestSession() as db:
        db.add(create_user())
        db.commit()

        db.add(create_user())

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()


def test_duplicate_organization_slug_is_rejected():
    with TestSession() as db:
        db.add(create_organization())
        db.commit()

        db.add(create_organization())

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()


def test_duplicate_membership_is_rejected():
    with TestSession() as db:
        user = create_user()
        organization = create_organization()

        db.add(
            Membership(
                user=user,
                organization=organization,
                role=MembershipRole.OWNER,
            )
        )
        db.commit()

        duplicate = Membership(
            user_id=user.id,
            organization_id=organization.id,
            role=MembershipRole.VIEWER,
        )
        db.add(duplicate)

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()


def test_deleting_organization_removes_membership():
    with TestSession() as db:
        user = create_user()
        organization = create_organization()

        db.add(
            Membership(
                user=user,
                organization=organization,
                role=MembershipRole.ENGINEER,
            )
        )
        db.commit()

        db.delete(organization)
        db.commit()

        remaining = db.scalars(select(Membership)).all()

        assert remaining == []
