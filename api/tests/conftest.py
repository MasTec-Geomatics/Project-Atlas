"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, delete, make_url, text

from src.app import app
from src.core.config import settings
from src.reference.api import get_reference_engine
from src.reference.models.public import LoadRun, Source, SourceCheck
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


def empty_sources_and_runs(engine: Engine) -> None:
    """Delete every ``public.sources``, ``public.load_runs``, and ``public.source_checks`` row."""
    with engine.begin() as connection:
        connection.execute(delete(Source))
        connection.execute(delete(LoadRun))
        connection.execute(delete(SourceCheck))


@pytest.fixture
def clean_engine(reference_engine: Engine) -> Iterator[Engine]:
    """The reference test database with no sources, load runs, or source checks, before and after.

    Yields:
        Engine connected to the reference test database.
    """
    empty_sources_and_runs(reference_engine)
    yield reference_engine
    empty_sources_and_runs(reference_engine)


@pytest.fixture
def api_engine(clean_engine: Engine) -> Iterator[Engine]:
    """Point the API at the reference test database, with no sources, load runs, or source checks.

    Yields:
        Engine connected to the reference test database.
    """
    app.dependency_overrides[get_reference_engine] = lambda: clean_engine
    yield clean_engine
    app.dependency_overrides.clear()
