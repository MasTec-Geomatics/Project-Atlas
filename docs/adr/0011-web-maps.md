# 0011. MapLibre GL JS and USGS Basemaps for Web Maps

**Status:** Accepted
**Date:** 2026-11-09
**Revised:** 2026-11-19

## Context

Atlas needs a web map showing project locations, with room to grow into more advanced mapping.

All Atlas work is in the United States.

## Decision

Use MapLibre GL JS for web maps, through `react-map-gl` (its `react-map-gl/maplibre` entry point) in React components (ADR 0024). The underlying MapLibre map is still available through `getMap()` for anything the wrapper does not cover.

Use the USGS National Map as the basemap:

- USGS Topo: `https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}`
- USGS Imagery: `https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}`

Both are loaded as MapLibre raster sources. The map displays USGS attribution.

Atlas spatial data is served by the API as GeoJSON in EPSG:4326.

## Consequences

- No basemap account, API key, or usage fees.
- USGS basemaps are public domain and cover the United States.
- USGS basemaps are raster tiles and cannot be restyled.
- No service-level guarantee from USGS.
- The basemap can be swapped by changing the source URLs.

Closes #10.
