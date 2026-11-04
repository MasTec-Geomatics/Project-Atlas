# 0002. Python and FastAPI for the Core Backend

**Status:** Accepted
**Date:** 2026-11-02
**Revised:** 2026-11-04

## Context

Project Atlas requires an application backend to manage projects, tasks, user permissions, datasets, integrations, and deliverable workflows.

The development team is small. Python is the language shared by its available developers and is already used for geospatial scripting and processing.

Go was considered for the core application because of its performance, concurrency model, and deployment characteristics.

However, introducing Go would require the team to maintain two backend languages from the beginning.

The application's initial workload does not establish a performance requirement that justifies this additional complexity.

## Decision

Use Python and FastAPI for the core application backend.

FastAPI will handle HTTP requests, authentication integration, authorization, application services, and business logic.

Long-running processing and scheduled operations will execute in separate Python workers rather than inside the API request lifecycle.

The API will maintain clear boundaries between transport concerns, application logic, and persistence.

The backend will expose documented API contracts that do not require consumers to know which language or framework implements them.

The API and frontend will remain independently deployable.

## Alternatives Considered

- **Go:** A strong candidate for future backend implementation, but adds another language to the initial system.
- **Django:** Not selected because its integrated application framework is not required for Atlas.
- **Single-process FastAPI:** Simpler initially, but inappropriate for potentially expensive GIS processing and long-running integrations.

## Consequences

- The initial team can maintain the core application and workers in Python.
- FastAPI provides OpenAPI documentation and request validation.
- Background processing can be isolated from HTTP workloads.
- API and worker components can be deployed and scaled separately.
- Additional work is required to establish well-defined internal interfaces.
- Replacing FastAPI later will still require porting application logic, authentication, and integrations.

## Future Considerations

Go may replace FastAPI if operational requirements, performance characteristics, or team capabilities justify it.

Any replacement must preserve the agreed API contracts and relevant business behavior.

The goal is replaceability, not a commitment to replace FastAPI.
