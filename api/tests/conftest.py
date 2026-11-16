"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, make_url, text

from src.core.config import settings
from tests.migrations import migrate_reference

TEST_DATABASE = "reference_test"


@pytest.fixture(scope="session")
def reference_engine() -> Iterator[Engine]:
    """Engine for a temporary reference test database, migrated to head.

    Creates ``reference_test`` on the same server as ``REFERENCE_DATABASE_URL`` when the
    test run starts and drops it when the run ends, so it never sits next to the real
    ``reference`` database. The tests downgrade to base, which drops every table, so they
    must never run against ``reference`` itself.

    Yields:
        Engine connected to the migrated reference test database.
    """
    reference_url = make_url(str(settings.reference_database_url))
    admin = create_engine(reference_url.set(database="postgres"), isolation_level="AUTOCOMMIT")

    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)"))  # type: ignore[SqlInjection]
        connection.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))  # type: ignore[SqlInjection]

    engine = create_engine(reference_url.set(database=TEST_DATABASE))
    migrate_reference(engine, "head", upgrade=True)
    yield engine
    engine.dispose()

    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE {TEST_DATABASE} WITH (FORCE)"))  # type: ignore[SqlInjection]
    admin.dispose()
