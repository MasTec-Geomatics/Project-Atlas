# 0021. Reference Data by State, and Boundaries

**Status:** Accepted
**Date:** 2026-11-17

## Context

The `reference` database starts with Texas and expands to the lower 48. Adding a state must not require restructuring tables or running major migrations on a live system.

Users want to move straight to a place: pick a state, then a county, then a city, and zoom there without searching the map.

PostgreSQL schemas cannot be nested, so a state → subject → table layout (for example `texas` → `hydro` → `wetlands`) is not possible.

## Decision

### One Set of Tables for Every State

- Schemas stay grouped by subject (`hydro`, `land`, …). There are no per-state schemas or tables.
- Every layer table has a `state` column holding the two-letter state code, for example `TX`.
- Each state is loaded on its own. A load replaces only that state's rows (ADR 0018).
- Download links are kept per layer and state in `public.sources`.
- Sources published per state (for example NWI wetlands) are downloaded per state.
- National sources (for example USGS 3DHP) are cut at state lines using `boundaries.states`. A feature that crosses a state line is split, and each part is stored with its own state. Unique keys on those tables include `state`, for example `(state, id3dhp)`.

### Boundaries

A `boundaries` schema holds the areas users navigate by, loaded from the U.S. Census Bureau's full-detail TIGER/Line Shapefiles:

| Table                 | Census file          | Columns                          |
| --------------------- | -------------------- | -------------------------------- |
| `boundaries.states`   | National state file  | `state`, `name`, `geom`          |
| `boundaries.counties` | National county file | `state`, `geoid`, `name`, `geom` |
| `boundaries.places`   | Per-state place file | `state`, `geoid`, `name`, `geom` |

- `geoid` is the Census GEOID, unique nationally.
- Places (cities, towns, villages, and Census designated places) nest within a state but can cross county lines, so `boundaries.places` has no county column. The places in a county are the ones whose shape overlaps the county's shape, found with the spatial index.

## Consequences

- Adding a state is new `public.sources` rows and a load. No new tables, schemas, or migrations.
- A project near a state line uses one layer per subject, not one per state.
- A new layer or survey system is a new table, added by a migration that does not change existing tables.
- `boundaries.states` must be loaded before any national source.
- In QGIS, the **Type to locate** box can search a boundaries layer by name and zoom to it. A state → county → city picker would read from these three tables.
- Full-detail boundaries draw more slowly at a national zoom than simplified ones. Users zoom to an area through these tables, so that cost is rarely paid.
