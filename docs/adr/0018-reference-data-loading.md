# 0018. Reference Data Loading

**Status:** Accepted
**Date:** 2026-11-12

## Context

Public sources update on different schedules and can rename or restructure their fields without notice. Reference users must never see a half-loaded layer.

The Risk Management and Estimating team needs the data before Atlas reaches MVP. The team may not be able to log into the database server.

## Decision

Each layer has one loader function in `src/reference/loaders/`, for example `load_wetlands()`.

Every load follows the same steps:

1. **Download** the source data.
2. **Stage** it into the `staging` schema as-is with `ogr2ogr`, reprojecting to `EPSG:4326`.
3. **Swap** it into the final table in one transaction, mapping source fields to the table's columns.
4. **Record** the run in `public.load_runs`: layer, status, source version, row count, error, start and finish times.

A separate change check asks each source for its current version or last-updated date without downloading the data. It records the result in `public.source_checks`. A check never starts a load.

### Before Atlas MVP

A maintainer runs loads and checks from the Atlas code on their own machine, connected to the `reference` database with the maintainer role:

```sh
uv run python -m src.reference.load wetlands
uv run python -m src.reference.check
```

### At Atlas MVP

- A maintainer-only admin page shows each layer's last load, status, row count, source version, and whether an update is available.
- A "Load" button queues a job. A worker (ADR 0007) runs the same loader function.
- The change check runs on a weekly schedule as a worker job. Its results and any failures appear on the admin page.

## Consequences

- Column names stay stable when a source renames fields, so QGIS styles and saved queries keep working.
- A source structure change makes the load fail loudly instead of silently changing a table.
- Users see the previous data until the swap commits.
- Each layer needs a field mapping, written once when its loader is built.
- Loader code written before MVP is the same code the worker runs after MVP.
- Nothing requires logging into the database server.
- The machine running a load needs GDAL installed for `ogr2ogr`.
