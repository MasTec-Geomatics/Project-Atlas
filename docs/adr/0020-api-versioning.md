# 0020. API Versioning

**Status:** Accepted
**Date:** 2026-11-17

## Context

The Vue portal, and possibly other tools later, call the API. They need routes and responses that do not change underneath them.

`api/pyproject.toml` also has a `version`, which is the release number of the Atlas code.

## Decision

- API routes live under a version prefix in the URL: `/api/v1/...`. Example: `POST /api/v1/reference/loads/{layer}`.
- `GET /api/health` is the only route outside the version prefix.
- The URL version is independent of the `pyproject.toml` version. A release does not change it.
- The URL version changes only when a route's request or response changes in a way that would break callers. Then `/api/v2` is added next to `/api/v1`, both run while callers move over, and `/api/v1` is removed once nothing uses it.

## Consequences

- Releasing a new Atlas version, including a major version, never moves or breaks existing routes.
- Changes that don't break callers (new routes, new optional fields) go into the current version.
- A breaking change is a deliberate decision, with both versions running for a while.
- The release version is still visible to callers through `/api/health`.
