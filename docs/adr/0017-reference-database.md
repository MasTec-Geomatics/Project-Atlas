# 0017. Reference Database for Public GIS Layers

**Status:** Accepted
**Date:** 2026-11-12

## Context

The Risk Management and Estimating team needs shared public GIS data in QGIS: wetlands, floodplain, parcels, soils, pipelines and wells, protected lands, and similar layers. Coverage starts with Texas and expands to the continental United States. Free sources come first. Paid sources come later.

This data behaves differently from Atlas's working data:

- **Atlas data** is edited daily by Geomatics.
- **Reference data** is replaced in bulk from public sources and is read-only for everyone except maintainers.

The team needs this data before Atlas reaches MVP.

## Decision

Create a separate database named `reference` on the same PostgreSQL server as `atlas`. This replaces the `reference` schema proposed in the README.

- Layers are grouped into schemas by subject: `hydro`, `cultural`, `environment`, `energy`, `utilities`, `land`, `soils`, and `storage`. Raw downloads land in `staging` before being swapped into the final tables (ADR 0018).
- Load history (`public.load_runs`) and change checks (`public.source_checks`) live in the `reference` database.
- Every geometry column is stored in WGS84 (`EPSG:4326`). Loaders reproject on load.
- Elevation rasters (USGS 3DEP DEMs) are stored as Cloud Optimized GeoTIFFs in AWS S3. Each file is recorded in `storage.raster_assets` with its S3 key, source date, and footprint.
- The code lives in Atlas as the `src/reference/` domain.
- Tables are SQLAlchemy models on a second declarative base, `ReferenceBase`, using the naming convention from ADR 0015.
- The `reference` database has its own Alembic environment, `migrations_reference/`, configured in the `[reference]` section of `alembic.ini`:

```sh
  uv run alembic -n reference revision --autogenerate -m "..."
  uv run alembic -n reference upgrade head
```

- The table design is in `docs/reference-db.dbml`.

## Consequences

- Bulk loads cannot affect Atlas data.
- QGIS users are granted access to `reference` only and never see `atlas`.
- Each database is backed up and restored on its own.
- One server to run.
- A single SQL query cannot join tables across the two databases. Atlas code reads reference data through its own connection.
- Atlas has two database connections: `DATABASE_URL` and `REFERENCE_DATABASE_URL`.
- Distances and areas are not meaningful in degrees. Measurements use the PostGIS `geography` type or reproject within the query.
- NAD83(2011) and WGS84 differ by up to about 1–2 m in the continental United States. This is acceptable for risk screening.
- Autogenerate creates tables but not schemas. The first reference migration creates the schemas with SQLAlchemy's `CreateSchema`. It also creates the PostGIS extension and the grants (ADR 0019), which are written as SQL because SQLAlchemy has no construct for them.
