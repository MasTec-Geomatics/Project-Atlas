"""Table models for the reference database, one module per schema.

Every module must be imported here. Alembic only sees tables whose module has been
imported, and autogenerate would write a ``drop_table`` for any it can't see. See
ADR 0017 and ``docs/reference-db.dbml``.

Attributes:
    metadata: The ``MetaData`` holding every reference table.
"""

from src.core.database import ReferenceBase
from src.reference.models import (
    cultural,
    energy,
    environment,
    hydro,
    land,
    public,
    soils,
    storage,
    utilities,
)

__all__ = [
    "cultural",
    "energy",
    "environment",
    "hydro",
    "land",
    "metadata",
    "public",
    "soils",
    "storage",
    "utilities",
]

metadata = ReferenceBase.metadata
