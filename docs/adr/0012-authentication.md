# 0012. Provider-Neutral Authentication

**Status:** Accepted
**Date:** 2026-11-09

## Context

Atlas will use Okta, the company identity provider. Okta access requires IT involvement.

A hosted demo is needed before Okta is available.

## Decision

Use Clerk for authentication until Okta is available.

Build authentication so the provider can be replaced without changing the rest of the application.

### API

- The API verifies login tokens (JWTs) itself using PyJWT and the provider's published signing keys (JWKS).
- All verification lives in `api/src/core/auth.py`, exposed as one FastAPI dependency: `get_current_user`.
- Provider details are settings: `AUTH_ISSUER` and `AUTH_JWKS_URL`.
- The Clerk SDK is not used in the API.

### Roles

- Roles (viewer, editor, admin) are stored in the Atlas `users` table.
- Each user is linked to the provider by the token's subject (`sub`) claim.
- Roles are not stored in Clerk.

### Frontend

- `@clerk/vue` is only imported in `web/src/composables/useAuth.ts`.
- The rest of the app uses `useAuth` for the current user, token, sign-in, and sign-out.

## Consequences

- Switching to Okta changes `auth.py` settings, `useAuth.ts`, and the login screen.
- Routes, roles, and business logic do not change.
- Users must be re-linked to Okta subjects when switching providers.
