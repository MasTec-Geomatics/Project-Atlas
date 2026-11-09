# 0003. Vue for the Frontend

**Status:** Accepted
**Date:** 2026-11-02
**Revised:** 2026-11-09

## Context

Project Atlas requires a browser-based application for project dashboards, task management, geographic visualization, and access to project information.

The frontend will contain interactive maps, forms, tables, and visualization components.

React, Vue, Svelte, and server-rendered approaches were considered.

The frontend must not be tightly coupled to the backend implementation.

## Decision

Use Vue 3 with TypeScript for the frontend.

Vue will operate as an independent application and communicate with the core backend through documented HTTP APIs.

The frontend will not access the application database directly.

API request and response contracts will remain independent of Vue-specific implementation details.

Map viewers, point cloud viewers, and other specialized interfaces will be encapsulated within appropriate frontend components.

Styling is written as plain CSS in Vue scoped styles. Tailwind and design tokens are not used.

## Libraries

| Purpose          | Library                            |
| ---------------- | ---------------------------------- |
| UI components    | Vuetify 4                          |
| Tables           | TanStack Table                     |
| Server state     | TanStack Vue Query                 |
| API client       | openapi-typescript + openapi-fetch |
| Forms            | VeeValidate + Zod                  |
| Client state     | Pinia                              |
| Routing          | Vue Router                         |
| Maps             | MapLibre GL JS (see ADR 0011)      |
| Authentication   | See ADR 0012                       |
| Tooling          | Vite+ and Bun                      |

API types are generated from the FastAPI OpenAPI schema. They are not written by hand.

Pinia holds browser-only state. Data owned by the API is fetched and cached through TanStack Vue Query.

Zod validation in forms improves the user experience. The API remains the authoritative validator.

## Consequences

- Vue and the API can be developed and deployed independently.
- The frontend can be replaced without changing the backend's core responsibilities.
- The API must provide stable, documented interfaces.
- Frontend-specific state management remains separate from authoritative server state.
- Changes to API contracts require compatibility management.
- API contract changes surface as TypeScript errors once types are regenerated.

## Future Considerations

The frontend framework may be replaced if project requirements change.

React, Svelte, or another framework could consume the same API without requiring a redesign of the core backend.
