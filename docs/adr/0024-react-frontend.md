# 0024. React for the Frontend

**Status:** Accepted
**Date:** 2026-11-19
**Supersedes:** [0003](0003-vue-frontend.md)

## Context

ADR 0003 chose Vue 3 for the frontend. The `web/` app is still the Vite starter, with no routes or pages, so the frontend framework can change now at almost no cost.

Atlas is map-centric: project locations, reference layers, imagery, and point clouds. React has the larger ecosystem for this work:

- `react-map-gl` is maintained by vis.gl, an OpenJS Foundation project, and has a dedicated entry point for MapLibre GL JS.
- deck.gl, from the same group, plugs into `react-map-gl` for large data layers.
- The Vue wrappers for MapLibre are smaller community projects.

React also has more component libraries, and the TanStack libraries' React adapters are their most widely used.

## Decision

Use React with TypeScript for the frontend.

Vue is replaced. Everything in ADR 0003 that is not framework-specific stays: the frontend is an independent application, it talks to the API only through documented HTTP APIs, and API types are generated, not written by hand.

## Libraries

| Purpose        | Library                            |
| -------------- | ---------------------------------- |
| UI components  | Mantine                            |
| Icons          | Tabler Icons                       |
| Styling        | CSS Modules                        |
| Routing        | TanStack Router, file-based routes |
| Server state   | TanStack Query                     |
| Tables         | TanStack Table v9                  |
| Forms          | TanStack Form + Zod                |
| Client state   | Zustand                            |
| API client     | openapi-typescript + openapi-fetch |
| Maps           | MapLibre GL JS + `react-map-gl`    |
| Tests          | Vitest + Testing Library           |
| Authentication | See ADR 0012                       |
| Tooling        | Vite+ and Bun                      |

### Styling

- Styles are plain, modern CSS in CSS Modules (`*.module.css`). Mantine's components already use CSS Modules.
- Tailwind is not used. Design tokens are not used.

### Routing

- Routes are file-based: each route is a file in `web/src/routes/`, and the router builds the route list from that folder.
- A route that needs custom setup can still be written in code; TanStack Router supports both in one app.

### Tables

- TanStack Table holds the table logic: sorting, filtering, and selection.
- Tables render as a plain HTML `<table>` styled with CSS Modules, in one shared `DataTable` component.
- Tables do not use Mantine's `Table` component, so replacing Mantine never touches a table.

### Server and Client State

- Data owned by the API is fetched and cached through TanStack Query.
- Zustand holds shared browser-only state, such as the map view or the layers switched on, and is added only when something needs it. Zustand stores can also be read from MapLibre's map events, which run outside React.

### API Types

- `openapi-typescript` generates the API types from the running API's OpenAPI schema. The API must be running (`just api-dev`) to regenerate them.
- No schema file is committed.

### Forms

- TanStack Form holds form state. Zod schemas validate fields directly.
- Zod validation in forms improves the user experience. The API remains the authoritative validator.

## Tentative

These are expected but decided when first needed.

### Charts: TanStack Charts

- **Why:** the same TanStack family and types as the rest of the stack, with a React package.
- **Used for:** Atlas dashboards, for example projects by production status, open and claimed tasks, and deliverables released per month.
- **Decided:** with the first chart.

### Markdown: TanStack Markdown

- **Why:** the same TanStack family. It renders Markdown, including images and tables, in React without a full publishing system.
- **Used for:** SOPs and How-To guides for TBC, Civil 3D, and QGIS, and possibly project notes.
- **Decided:** when SOPs are built, along with whether they live inside Atlas or in a separate documentation site such as Starlight.

## Alternatives Considered

### Keep Vue

Vue works for Atlas, and MapLibre and Potree can be used from Vue directly. It was not kept because the map, component, and TanStack ecosystems are larger in React, and switching now costs almost nothing.

## Consequences

- `web/` is replaced with a React and TypeScript starter.
- Map work uses `react-map-gl` and can add deck.gl for large data layers (ADR 0011).
- Potree is wrapped in a React component (ADR 0005).
- The authentication hook moves to `web/src/hooks/useAuth.ts` (ADR 0012).
- Tables do not depend on the component library.
- API contract changes surface as TypeScript errors once types are regenerated.
