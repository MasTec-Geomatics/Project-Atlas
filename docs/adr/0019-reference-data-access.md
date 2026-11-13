# 0019. Reference Data Access

**Status:** Accepted
**Date:** 2026-11-12

## Context

Reference data must be read-only for users and editable only by a small group of Geomatics maintainers. Users work remotely on locked-down company laptops that cannot install VPN clients. Outbound port `5432` is allowed on those laptops.

The database may later be opened to the whole company.

## Decision

### Roles

Permissions are granted to two group roles, never to individual people:

- `reference_reader`: read-only.
- `reference_maintainer`: read and write. Includes `reference_reader`.

Each person gets an individual login that is a member of one of these roles:

```sql
CREATE ROLE jsmith LOGIN PASSWORD '...' IN ROLE reference_reader;
```

Roles belong to the whole PostgreSQL server, so they are created once at server setup (`deploy/local/reference-setup.sql` for local development). Reference migrations grant them access inside the `reference` database.

### QGIS

QGIS connects directly to the `reference` database on port `5432`, encrypted with TLS (`SSL mode = verify-full`). There is no service layer between QGIS and the database.

## Consequences

- Individual logins show who did what. One person can be disabled without affecting anyone else.
- A shared reader login can be added later with one statement and no redesign.
- Each user sets up one PostgreSQL connection in QGIS.
- The database port is reachable from the internet. TLS and individual logins protect it.
- If port `5432` is blocked in the future, layers can be served read-only over HTTPS through a standard OGC web service.
- Reading the elevation files in S3 requires read-only AWS credentials, set once in QGIS's environment settings.
