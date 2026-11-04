# 0007. Independent Python Background Workers

**Status:** Accepted
**Date:** 2026-11-04

## Context

Project Atlas will perform operations that should not execute within normal HTTP request handling.

Examples include:

- GIS data ingestion.
- Large dataset transformations.
- Spatial validation.
- Raster and LiDAR processing.
- Procore synchronization.
- Deliverable publication.
- Scheduled maintenance and external data refreshes.

These operations may be long-running, resource-intensive, or dependent on external systems.

Running them directly within FastAPI request handlers could affect application responsiveness and complicate error recovery.

## Decision

Use independently running Python workers for background processing.

Workers will execute outside the FastAPI application process and may be deployed in separate containers.

Initial worker responsibilities will be divided logically between geospatial processing and enterprise integrations.

Workers may share internal Python libraries with the core backend, provided the shared code does not require the FastAPI application process.

Jobs will be described using explicit, versioned payload contracts.

Workers will report processing status and results through defined persistence or messaging interfaces.

The specific queue implementation is deferred until workload and deployment requirements are established.

## Reliability Requirements

The processing system should support:

- Persistent job state.
- Explicit job identifiers.
- Processing and failure status.
- Retries for recoverable errors.
- Idempotent operations where possible.
- Visibility into worker failures.
- Prevention of conflicting job execution.
- Recovery after worker or container restarts.

Long-running jobs must not depend on the continued existence of the HTTP request that initiated them.

Workers must not independently change database schemas.

## Alternatives Considered

### FastAPI BackgroundTasks

Suitable for lightweight, in-process operations, but not sufficient as the primary mechanism for durable, resource-intensive processing.

### Separate Python Workers

Provides independent lifecycles, resource allocation, and failure isolation.

### Dedicated Message Broker

May be appropriate as processing volume increases, but is not required as an initial architectural commitment.

## Consequences

- API responsiveness is isolated from expensive processing.
- GIS workers can use specialized libraries and container images.
- Integration workers can be maintained separately from GIS processing.
- Worker deployments can have independent resource requirements.
- Additional coordination, monitoring, and recovery logic will be necessary.
- Shared database access requires clear ownership and transaction rules.

## Future Considerations

The initial implementation may use PostgreSQL-backed jobs.

Redis, RabbitMQ, or another queue service may be introduced if demonstrated requirements justify it.

Workers should remain independent of the chosen queue technology through a consistent application-level job interface.
