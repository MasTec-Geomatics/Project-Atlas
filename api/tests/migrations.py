"""Helper for running the reference migrations from tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def migrate_reference(engine: Engine, revision: str, *, upgrade: bool) -> None:
    """Run the reference migrations against the given engine's database.

    Args:
        engine: Engine for the database to migrate.
        revision: Target revision, such as "head" or "base".
        upgrade: Whether to upgrade or downgrade.
    """
    config = Config(ALEMBIC_INI, ini_section="reference")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        if upgrade:
            command.upgrade(config, revision)
        else:
            command.downgrade(config, revision)
