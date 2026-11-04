# 0006. Modular Architecture and Replaceable Components

**Status:** Accepted
**Date:** 2026-11-04

## Context

Project Atlas is expected to evolve as the Geomatics group's operational requirements become better defined.

The initial implementation uses FastAPI and Vue, but future requirements may justify replacing either technology.

The architecture should support these changes without requiring the entire application to be rewritten.

The development team is small, so unnecessary distributed services and infrastructure complexity should be avoided.

## Decision

Adopt a modular architecture with explicit boundaries between:

- The frontend application.
- The core backend API.
- Background processing workers.
- Database and persistence.
- External services and integrations.

Use a modular monolith for the initial core backend rather than developing separate microservices for each business domain.

Organize backend code by business capability, including projects, tasks, users, datasets, and standards.

Business rules should be kept separate from HTTP routing and framework-specific integration code wherever practical.

The frontend will communicate with the backend through versioned, documented API contracts.

Background workers will use defined job contracts and controlled access to application data.

The database schema will be managed through migrations with clear ownership of structural changes.

## Alternatives Considered

### Tightly Coupled Full-Stack Application

Would simplify some development tasks, but make independent frontend and backend replacement more difficult.

### Microservices

Would allow strong deployment isolation but introduce additional network communication, distributed state management, and operational complexity.

### Modular Monolith with Independent Workers

Provides clear component boundaries while keeping the initial system manageable for a small development team.

This is the selected approach.

## Consequences

- The frontend and backend can be deployed independently.
- API implementation details remain hidden from frontend consumers.
- Internal business modules can share transactions where appropriate.
- Workers can evolve without being tied to the HTTP request lifecycle.
- API contract compatibility must be maintained.
- Replacing a major component will still require implementation and integration work.

## Architectural Principle

Replaceability is achieved through stable boundaries and explicit contracts, not simply by using separate containers.

A deployment boundary does not automatically provide an application boundary.
