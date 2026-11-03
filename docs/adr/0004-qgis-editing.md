# 0004. QGIS for Editing

**Status:** Accepted

**Date:** 2026-11-02

## Context

The department needs to edit spatial data such as project boundaries. The company uses QGIS rather than Esri, for cost and licensing reasons.

## Decision

Department editors use QGIS desktop for geometry editing. Viewers use the web app in the browser.

## Consequences

- No geometry editing tools need to be built in the web app at first.
- The team already knows QGIS.
- Editing requires QGIS on the editor's machine.
- How QGIS connects to the database is not yet decided.
