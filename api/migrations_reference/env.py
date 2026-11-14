"""Alembic environment for the reference database.

Uses the ``[reference]`` section of the ``[alembic]`` config.

Examples:
    Apply all migrations::

        uv run alembic -n reference upgrade head

    Generate a migration from the models::

        uv run alembic -n reference revision --autogenerate -m "describe the change"
"""

from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import Connection, create_engine, pool
from sqlalchemy.sql.schema import SchemaItem

from src.core.config import settings
from src.reference.models import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata
database_url = str(settings.reference_database_url)


def include_object(
    obj: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    """Decide whether autogenerate compares a database object.

    Skips PostGIS's own tables, such as ``spatial_ref_sys``, and any table that exists in the
    database but has no model, such as ``org2org`` staging tables or QGIS's ``layer_styles``.
    Autogenerate never proposed dropping those.

    Args:
        obj: The table, column, index, or constraint being compared.
        name: The object's name.
        type_: The kind of object, suck as ``"table"`` or ``"index"``.
        reflected: True if the object was read from the database.
        compare_to: The matching model object, or None if there is none.

    Returns:
        True to include the object in the comparison, False to skip it.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    return bool(alembic_helpers.include_object(obj, name, type_, reflected, compare_to))


def run_migrations_offline() -> None:
    """Write the migration SQL to stdout instead of running it."""
    context.configure(
        url=database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the migrations against the reference database.

    Uses the connection in ``config.attributes["connection"]`` when one is given, so the
    tests can migrate the reference test database. Otherwise connects to
    ``REFERENCE_DATABASE_URL``.
    """
    connection = config.attributes.get("connection")
    if connection is None:
        engine = create_engine(database_url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            _run_migrations(connection)
    else:
        _run_migrations(connection)


def _run_migrations(connection: Connection) -> None:
    """Configure Alembic with a connection and run the migrations.

    Args:
        connection: Open connection to the database being migrated.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
