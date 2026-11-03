# 0003. Vue for the Frontend

**Status:** Accepted

**Date:** 2026-11-02

## Context

The web app has a map, project pages, many project management forms, and charts. It will eventually be shared with other departments.

React, Vue, Svelte, and server-rendered templates were considered. A framework with component libraries was preferred over hand-building everything with templates.

## Decision

Use Vue for the frontend, running on Node as its own service, separate from the FastAPI backend.

Styling uses modern CSS with Vue's built-in scoped styles rather than Tailwind.

## Consequences

- Frontend and backend stay separate.
- `v-model` two-way binding reduces code on form-heavy screens.
- Vue Router and Pinia are maintained by the Vue team.
- Map and point cloud libraries are wrapped in Vue components.
- The frontend talks to the backend only through the API.
