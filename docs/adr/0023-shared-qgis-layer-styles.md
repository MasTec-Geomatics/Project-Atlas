# 0023. Shared QGIS Layer Styles

**Status:** Accepted
**Date:** 2026-11-17

## Context

Every `reference` user should see the same styling for each layer. QGIS can save a layer's style in the database it comes from, in a `public.layer_styles` table, and loads a layer's default style from there automatically.

When that table doesn't exist, QGIS creates it the first time someone saves a style, owned by whoever saved it, without the `reference` grants.

## Decision

- A reference migration creates `public.layer_styles`, with exactly the columns QGIS creates (`docs/reference-db.dbml`).
- Maintainers save styles to the database from QGIS, marked as the default style for the layer.
- The table gets the same grants as the other `public` tables: read for `reference_reader`, read and write for `reference_maintainer`.

## Consequences

- Layers load already styled for every user, with no files to hand out.
- Readers cannot change the shared styles.
- The table follows QGIS's column names and types instead of ADR 0015 (`serial` id, `varchar`, `timestamp` without time zone), because QGIS reads and writes it directly.
