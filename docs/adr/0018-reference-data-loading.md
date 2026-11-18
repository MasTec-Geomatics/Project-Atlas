# 0018. Reference Data Loading

**Status:** Accepted **Date:** 2026-11-12 **Updated:** 2026-11-18

## Context

Public sources update on different schedules and can change their links, formats, and field names without notice.
Reference users must never see a half-loaded layer.

The Risk Management and Estimating team needs the data before Atlas reaches MVP. The team may not be able to log into
the database server or the server running Atlas, so nothing can depend on running a command there.

## Decision

### Loads Run Through the API

Loads are never run from a command line. They are started through the versioned API (ADR 0020):

```text
POST /api/v1/reference/loads
```

- The request is a list of layer and state pairs, for example
  `[{"layer": "boundaries.counties", "state": "TX"}, {"layer": "boundaries.counties", "state": "LA"}]`. On the admin
  page, each pair is one checked box in a table of states by layers, and one **Load** button sends them all.
- The endpoint answers `202 Accepted` right away and runs the loads as a FastAPI background task.
- A pair with an unknown layer or no enabled source answers `422`, listing every problem, and nothing is started.

### Sources

Everything a provider controls is data in `public.sources`, never code:

| Column          | Holds                                                             |
|-----------------|-------------------------------------------------------------------|
| `download_url`  | The link, with `{state}` and `{fips}` filled in for each state    |
| `access_type`   | `file` (downloaded) or `service` (read directly by GDAL)          |
| `format`        | GDAL format name, for example `ESRI Shapefile` or `GPKG`          |
| `source_layer`  | Layer name inside the file, with `{state}` filled in              |
| `field_mapping` | Final column to provider field                                    |
| `keep`          | Provider field to the values to keep, with `{state}` and `{fips}` |
| `clip_to_state` | Cut the data at the state line using `boundaries.states`          |

- A source with no `state` is a **federal source** and covers every state. A source with a `state` is a **state source**
  and covers only that state.
- A load uses the state source if there is one, otherwise the federal source.
- Atlas starts with federal sources for `boundaries.states`, `boundaries.counties`, `boundaries.places`, and
  `hydro.wetlands`, added by the migration.

### The Loader

There is one loader, in `src/reference/load.py`. It reads the source and runs the same steps for every layer. A new
layer needs its table (migration) and its source (admin page), not new loader code.

### Load Steps

Each download link follows the same steps. Pairs that share a link, such as several states from one national file, go
through these steps together, so the file is downloaded and staged once:

1. **Download** the file with `httpx` into a temporary folder under `REFERENCE_WORK_DIR`. The folder is deleted when the
   load ends. A `service` source is read directly instead.
2. **Stage** it into the `staging` schema as-is with `ogr2ogr`, reprojecting to `EPSG:4326`.
3. **Swap** each state into the final table in its own transaction, using the field mapping and `keep`, and cutting at
   the state line when `clip_to_state` is set. Only that state's rows are replaced (ADR 0021).
4. **Record** each state's run in `public.load_runs`: layer, state, status, source version, row count, error, start and
   finish times.

If the download or staging fails, every state that uses that link is recorded as `failed`.

### Checking a Link

`POST /api/v1/reference/sources/check` opens a link with `ogrinfo` before it's saved. It returns the format, the layers
inside, and each column's matched provider field: the field the current source uses if it's still there, otherwise a
field with the same name as the column. A column with no match is returned empty, and the admin page shows a dropdown of
the file's fields for it.

### Change Checks

A separate change check asks each source for its current version or last-updated date without downloading the data. It
runs weekly and records the result in `public.source_checks`. A check never starts a load.

### Maintainer Admin Page

- **Load:** a table of states by layers, with a state filter and one **Load** button.
- **Edit source:** paste a new link and click **Check link**. Atlas fills in the format, layer, and fields. Only an
  unmatched field needs a pick from a dropdown. **Save** sends `PATCH /api/v1/reference/sources/{id}`.
- **Add source:** pick the layer and the state, paste the link, and check it the same way. **Save** sends
  `POST /api/v1/reference/sources`.

## Consequences

- A new link, format, layer name, or renamed field is an edit on the admin page, not a code change.
- Column names stay stable when a source renames fields, so QGIS styles and saved queries keep working.
- A renamed field the source still maps makes the load fail loudly instead of silently changing a table.
- Users see the previous data until the swap commits.
- Loading one state never touches another state's rows.
- Nothing requires logging into the database server or the Atlas server.
- The machine running the API needs GDAL installed for `ogr2ogr` and `ogrinfo`, and enough free disk in
  `REFERENCE_WORK_DIR` for the largest download (about 10 GB for Texas wetlands).
- Checking a file link downloads the whole file, so it takes as long as the download.