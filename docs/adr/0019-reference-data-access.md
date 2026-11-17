# 0019. Reference Data Access

**Status:** Accepted
**Date:** 2026-11-12
**Updated:** 2026-11-17

## Context

Reference data must be read-only for users and editable only by a small group of Geomatics maintainers. Users work remotely on locked-down company laptops that cannot install VPN clients. Outbound port `25060`, used by the production managed PostgreSQL cluster, is allowed on those laptops.

The database may later be opened to the whole company.

## Decision

### Roles

Permissions are granted to two group roles, never to individual people:

- `reference_reader`: read-only.
- `reference_maintainer`: read and write. Includes `reference_reader`.

Each person gets an individual login that is a member of one of these roles. Logins are created and managed from the Atlas admin portal (ADR 0022), never with SQL.

Roles belong to the whole PostgreSQL server, so the two group roles are created once at server setup (`deploy/local/reference-setup.sql` for local development). Reference migrations grant them access inside the `reference` database.

### QGIS

QGIS connects directly to the `reference` database, encrypted with TLS (`SSL mode = verify-full`). There is no service layer between QGIS and the database.

| Environment | Port    |
| ----------- | ------- |
| Production  | `25060` |
| Local       | `5432`  |

## Consequences

- Individual logins show who did what. One person can be disabled without affecting anyone else.
- A shared reader login can be added later with no redesign.
- Each user sets up one PostgreSQL connection in QGIS.
- The database port is reachable from the internet. TLS and individual logins protect it.
- If port `25060` is blocked in the future, layers can be served read-only over HTTPS through a standard OGC web service.
- Reading the elevation files in S3 requires read-only AWS credentials, set once in QGIS's environment settings.
