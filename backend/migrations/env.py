from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.core.database import Base, engine
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.membership import Membership  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.subscriber import Subscriber  # noqa: F401
from app.models.user import User  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=(
            settings.DATABASE_URL.lower().startswith("sqlite")
        ),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=(
                connection.dialect.name == "sqlite"
            ),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
