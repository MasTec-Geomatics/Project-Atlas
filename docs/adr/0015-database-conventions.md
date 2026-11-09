# 0015. Database Conventions

**Status:** Accepted
**Date:** 2026-11-09

## Decision

### Constraint Naming

Set a naming convention on `Base.metadata` so Alembic can find and change constraints reliably.

| Type        | Pattern                                                    |
| ----------- | ---------------------------------------------------------- |
| Index       | `ix_<column label>`                                        |
| Unique      | `uq_<table>_<column>`                                      |
| Check       | `ck_<table>_<constraint name>`                             |
| Foreign key | `fk_<table>_<column>_<referenced table>`                   |
| Primary key | `pk_<table>`                                               |

### Columns

- Primary keys: `bigint` identity.
- Timestamps: `timestamptz`.
- Status values: `text` with a check constraint, not a PostgreSQL enum.
- Foreign key columns are indexed.

### Spatial Data

- Web-facing geometry is stored in EPSG:4326.
- Data in other coordinate systems is stored with its SRID and converted with `ST_Transform` in SQL when needed.
- Alembic uses GeoAlchemy2's Alembic helpers so spatial indexes are handled correctly.
