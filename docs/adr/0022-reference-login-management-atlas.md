# 0022. Reference Login Management in Atlas

**Status:** Accepted
**Date:** 2026-11-17

## Context

Each `reference` user has an individual PostgreSQL login (ADR 0019). Adding and removing users and setting passwords must be easy for whoever is acting as an Admin, and must not require writing SQL or logging into the database server.

## Decision

- `reference` logins are managed entirely from the Atlas admin portal by any Atlas user with the Admin role (ADR 0012).
- From the portal, an Admin can add a login as a reader or maintainer, change its role, remove it, and set a new initial password.
- Atlas sets only the initial password. The user must change it on first login.
- Users change and reset their own password in the Atlas portal afterward.

## Consequences

- No one writes SQL or logs into the server to manage `reference` users.
- The API's connection for managing logins needs a PostgreSQL role allowed to create and alter roles (`CREATEROLE`).
- PostgreSQL has no setting that forces a password change, so Atlas tracks which logins still have to change their password.
- QGIS connections use the PostgreSQL login and password, so users update the password saved in QGIS after changing it.
