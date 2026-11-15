"""Tests for the reference migrations (issue #68, ADR 0017)."""

import re
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.migrations import migrate_reference

DBML = (Path(__file__).resolve().parents[2] / "docs" / "reference-db.dbml").read_text()

# Every table and every GiST index name, read from the DBML so the tests follow it.
TABLES = re.findall(r"^Table (\w+\.\w+) \{", DBML, flags=re.MULTILINE)
GIST_INDEXES = re.findall(r"\[name: '(\w+)', note: 'GiST'\]", DBML)

SCHEMAS = [
    "hydro",
    "cultural",
    "environment",
    "energy",
    "utilities",
    "land",
    "soils",
    "storage",
    "staging",
]
LAYER_SCHEMAS = [schema for schema in SCHEMAS if schema != "staging"]
LOAD_RUN_STATUSES = ["running", "succeeded", "failed"]


def test_postgis_extension_exists(reference_engine: Engine) -> None:
    """The migration enables PostGIS."""
    with reference_engine.connect() as connection:
        found = connection.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'"))

    assert found == 1


def test_schemas_exist(reference_engine: Engine) -> None:
    """Every reference schema is created."""
    schemas = inspect(reference_engine).get_schema_names()

    assert set(SCHEMAS) <= set(schemas)


@pytest.mark.parametrize("qualified_name", TABLES)
def test_table_exists(reference_engine: Engine, qualified_name: str) -> None:
    """Every table in docs/reference-db.dbml exists.

    Args:
        reference_engine: Engine for the migrated reference test database.
        qualified_name: Table name with its schema, such as ``hydro.wetlands``.
    """
    schema, table = qualified_name.split(".")

    assert inspect(reference_engine).has_table(table, schema=schema)


@pytest.mark.parametrize("index_name", GIST_INDEXES)
def test_spatial_index_is_gist(reference_engine: Engine, index_name: str) -> None:
    """Every spatial index exists with its DBML name and uses GiST.

    Args:
        reference_engine: Engine for the migrated reference test database.
        index_name: Index name from the DBML, such as ``wetlands_geom_idx``.
    """
    with reference_engine.connect() as connection:
        definition = connection.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
            {"name": index_name},
        )

    assert definition is not None
    assert "USING gist" in definition


def test_source_checks_columns(reference_engine: Engine) -> None:
    """public.source_checks has the columns from ADR 0018 and the DBML."""
    columns = inspect(reference_engine).get_columns("source_checks", schema="public")

    assert [column["name"] for column in columns] == [
        "id",
        "layer",
        "state",
        "checked_at",
        "source_version",
        "update_available",
        "error",
    ]


def test_load_runs_started_at_defaults_to_now(reference_engine: Engine) -> None:
    """public.load_runs.started_at defaults to now()."""
    columns = inspect(reference_engine).get_columns("load_runs", schema="public")
    started_at = next(column for column in columns if column["name"] == "started_at")

    assert started_at["default"] == "now()"


def test_load_runs_index(reference_engine: Engine) -> None:
    """public.load_runs has its lookup index from the DBML."""
    indexes = inspect(reference_engine).get_indexes("load_runs", schema="public")
    by_name = {index["name"]: index["column_names"] for index in indexes}

    assert by_name["load_runs_layer_state_started_idx"] == ["layer", "state", "started_at"]


@pytest.mark.parametrize("status", LOAD_RUN_STATUSES)
def test_load_runs_accepts_valid_status(reference_engine: Engine, status: str) -> None:
    """public.load_runs accepts each allowed status.

    Args:
        reference_engine: Engine for the migrated reference test database.
        status: An allowed status value.
    """
    with reference_engine.connect() as connection:
        connection.execute(
            text("INSERT INTO public.load_runs (layer, state, status) VALUES ('t', 'TX', :s)"),
            {"s": status},
        )
        connection.rollback()


def test_load_runs_rejects_unknown_status(reference_engine: Engine) -> None:
    """The status check constraint rejects a value that isn't allowed."""
    with reference_engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text("INSERT INTO public.load_runs (layer, state, status) VALUES ('t', 'TX', 'done')")
        )


@pytest.mark.parametrize("role", ["reference_reader", "reference_maintainer"])
@pytest.mark.parametrize("schema", SCHEMAS)
def test_roles_can_use_schemas(reference_engine: Engine, role: str, schema: str) -> None:
    """Both group roles have USAGE on every reference schema.

    Args:
        reference_engine: Engine for the migrated reference test database.
        role: Group role name.
        schema: Reference schema name.
    """
    with reference_engine.connect() as connection:
        allowed = connection.scalar(
            text("SELECT has_schema_privilege(:role, :schema, 'USAGE')"),
            {"role": role, "schema": schema},
        )

    assert allowed


@pytest.mark.parametrize("qualified_name", TABLES)
def test_reader_is_read_only(reference_engine: Engine, qualified_name: str) -> None:
    """reference_reader can SELECT every table but can't change it.

    Args:
        reference_engine: Engine for the migrated reference test database.
        qualified_name: Table name with its schema.
    """
    with reference_engine.connect() as connection:
        can_select = connection.scalar(
            text("SELECT has_table_privilege('reference_reader', :t, 'SELECT')"),
            {"t": qualified_name},
        )
        can_insert = connection.scalar(
            text("SELECT has_table_privilege('reference_reader', :t, 'INSERT')"),
            {"t": qualified_name},
        )

    assert can_select
    assert not can_insert


@pytest.mark.parametrize("qualified_name", TABLES)
def test_maintainer_can_write(reference_engine: Engine, qualified_name: str) -> None:
    """reference_maintainer can SELECT, INSERT, UPDATE, and DELETE every table.

    Args:
        reference_engine: Engine for the migrated reference test database.
        qualified_name: Table name with its schema.
    """
    with reference_engine.connect() as connection:
        allowed = connection.scalar(
            text("SELECT has_table_privilege('reference_maintainer', :t, :p)"),
            {"t": qualified_name, "p": "SELECT, INSERT, UPDATE, DELETE"},
        )

    assert allowed


@pytest.mark.parametrize("schema", LAYER_SCHEMAS)
def test_future_tables_get_grants(reference_engine: Engine, schema: str) -> None:
    """Default privileges give both roles access to tables created later.

    Args:
        reference_engine: Engine for the migrated reference test database.
        schema: Reference schema name.
    """
    table = f"{schema}.future_table_check"
    with reference_engine.connect() as connection:
        connection.execute(text(f"CREATE TABLE {table} (id integer)"))
        reader = connection.scalar(
            text("SELECT has_table_privilege('reference_reader', :t, 'SELECT')"), {"t": table}
        )
        maintainer = connection.scalar(
            text("SELECT has_table_privilege('reference_maintainer', :t, 'INSERT')"),
            {"t": table},
        )
        connection.rollback()

    assert reader
    assert maintainer


def test_downgrade_to_base_removes_schemas(reference_engine: Engine) -> None:
    """Downgrading to base removes the schemas and load_runs; upgrading restores them."""
    migrate_reference(reference_engine, "base", upgrade=False)
    inspector = inspect(reference_engine)
    schemas_left = set(SCHEMAS) & set(inspector.get_schema_names())
    load_runs_left = inspector.has_table("load_runs", schema="public")

    migrate_reference(reference_engine, "head", upgrade=True)

    assert schemas_left == set()
    assert not load_runs_left
