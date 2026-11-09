# 0013. Same-Origin Reverse Proxy

**Status:** Accepted
**Date:** 2026-11-09

## Context

The Vue app and the API run as separate services. A browser blocks cross-origin requests unless the API allows them through CORS.

## Decision

The browser only talks to one origin.

- `/api/*` is routed to the API service.
- Every other path is routed to the web service.

In development, the Vite dev server forwards `/api` to `localhost:8000`.

In deployment, a reverse proxy applies the same routing. In Kubernetes, an ingress applies it.

The API does not enable CORS.

## Consequences

- No CORS configuration in the API.
- Development and deployment use the same URL structure.
- The reverse proxy also terminates HTTPS.

Closes #8.
