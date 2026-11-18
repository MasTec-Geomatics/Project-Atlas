# 0018. Reference Data Loading

**Status:** Accepted **Date:** 2026-11-12 **Updated:** 2026-11-18

## Context

Public sources update on different schedules and can rename or restructure their fields without notice. Reference users
must never see a half-loaded layer.

The Risk Management and Estimating team needs the data before Atlas reaches MVP. The team may not be able to log into
the database server or the server running Atlas, so nothing can depend on running a command there.

## Decision

### Loads Run Through the API

Loads are never run from a command line. They are started through the versioned API (ADR 0020):

```text
POST /api/v1/reference/loads
```

- The request is a list of layer and state pairs, for example
  `[{"layer": "counties", "state": "TX"}, {"layer": "counties", "state": "LA"}]`. On the admin page, each pair is one
  checked box in a table of states by layers, and one **Load** button sends them all.
- The endpoint answers `202 Accepted` right away and runs the loads as a FastAPI background task.
- A pair with no loader or no enabled source answers `422`, listing every problem, and nothing is started.
- Until the maintainer admin page exists, the endpoint is run from the API's `/docs` page.

### Loaders

Each layer has one loader module in `src/reference/loaders/`, for example `loaders/wetlands.py` with `load_wetlands()`.
`LOADERS` in `src/reference/loaders/__init__.py` maps the layer name used in the route to its loader.

A loader only describes what is different about its layer, as a `LayerSource`: the final table, the state, the download
link, the layer name inside the file, the field mapping, and an optional `keep` filter. `keep` limits a load to listed
values; `hydro.wetlands` uses it to load wetland types only, leaving out open water.

### Load Steps

Each download link follows the same steps, in `src/reference/load.py`. Pairs that share a link, such as several states
from one national file, go through these steps together, so the file is downloaded and staged once:

1. **Download** the source file with `httpx` into a temporary folder under `REFERENCE_WORK_DIR`. The folder is deleted
   when the load ends.
2. **Stage** it into the `staging` schema as-is with `ogr2ogr`, reprojecting to `EPSG:4326`.
3. **Swap** each state into the final table in its own transaction, mapping source fields to the table's columns. Only
   that state's rows are replaced (ADR 0021).
4. **Record** each state's run in `public.load_runs`: layer, state, status, source version, row count, error, start and
   finish times.

If the download or staging fails, every state that uses that link is recorded as `failed`.

### Change Checks

A separate change check asks each source for its current version or last-updated date without downloading the data. It
runs weekly and records the result in `public.source_checks`. A check never starts a load.

### Maintainer Admin Page

A maintainer-only admin page shows each layer's last load, status, row count, source version, and whether an update is
available, with the **Load** button for each layer.

## Consequences

- Column names stay stable when a source renames fields, so QGIS styles and saved queries keep working.
- A source structure change makes the load fail loudly instead of silently changing a table.
- Users see the previous data until the swap commits.
- Loading one state never touches another state's rows.
- Each layer needs a field mapping, written once when its loader is built.
- Nothing requires logging into the database server or the Atlas server.
- The machine running the API needs GDAL installed for `ogr2ogr`, and enough free disk in `REFERENCE_WORK_DIR` for the
  largest download (about 10 GB for Texas wetlands).