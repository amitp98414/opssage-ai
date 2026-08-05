import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url

    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_migrations_build_secure_schema(tmp_path: Path):
    database_url = (
        f"sqlite:///{tmp_path / 'migration-test.db'}"
    )

    run_alembic(database_url, "upgrade", "head")

    engine = create_engine(database_url)

    try:
        database = inspect(engine)

        expected_tables = {
            "auth_sessions",
            "memberships",
            "organizations",
            "subscribers",
            "users",
        }
        actual_tables = set(database.get_table_names())

        assert expected_tables <= actual_tables

        expected_foreign_keys = {
            (
                "auth_sessions",
                ("user_id",),
                "users",
                ("id",),
                "CASCADE",
            ),
            (
                "memberships",
                ("user_id",),
                "users",
                ("id",),
                "CASCADE",
            ),
            (
                "memberships",
                ("organization_id",),
                "organizations",
                ("id",),
                "CASCADE",
            ),
        }

        actual_foreign_keys = set()

        for table in expected_tables:
            for foreign_key in database.get_foreign_keys(table):
                options = foreign_key.get("options") or {}

                actual_foreign_keys.add(
                    (
                        table,
                        tuple(
                            foreign_key["constrained_columns"]
                        ),
                        foreign_key["referred_table"],
                        tuple(foreign_key["referred_columns"]),
                        str(
                            options.get("ondelete") or ""
                        ).upper(),
                    )
                )

        assert expected_foreign_keys <= actual_foreign_keys

        expected_unique_names = {
            "uq_auth_sessions_refresh_token_hash",
            "uq_memberships_user_organization",
            "uq_organizations_slug",
            "uq_subscribers_email",
            "uq_users_email",
        }

        actual_unique_names = {
            constraint["name"]
            for table in expected_tables
            for constraint
            in database.get_unique_constraints(table)
            if constraint.get("name")
        }

        assert expected_unique_names <= actual_unique_names

        expected_index_names = {
            "ix_auth_sessions_refresh_token_hash",
            "ix_auth_sessions_user_id",
            "ix_memberships_organization_id",
            "ix_memberships_user_id",
            "ix_organizations_slug",
            "ix_subscribers_email",
            "ix_users_email",
        }

        actual_index_names = {
            index["name"]
            for table in expected_tables
            for index in database.get_indexes(table)
            if index.get("name")
        }

        assert expected_index_names <= actual_index_names
    finally:
        engine.dispose()

    run_alembic(database_url, "check")
    run_alembic(database_url, "downgrade", "base")

    engine = create_engine(database_url)

    try:
        remaining_tables = set(
            inspect(engine).get_table_names()
        )
        assert expected_tables.isdisjoint(remaining_tables)
    finally:
        engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    run_alembic(database_url, "check")
