"""Table models for reference database.

Every model in this module inherits from ``ReferenceBase``, which registers its
table on ``metadata``. The reference Alembic environment compares ``metadata``
against the database to generate migrations. See ADR 0017.

Attributes:
    metadata: the ``MetaData`` holding every reference table.
"""

from src.core.database import ReferenceBase

metadata = ReferenceBase.metadata