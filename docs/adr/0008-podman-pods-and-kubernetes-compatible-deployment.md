# 0008. Podman Pods and Kubernetes-Compatible Deployment

**Status:** Accepted
**Date:** 2026-11-04

## Context

Project Atlas consists of multiple cooperating components, including the frontend, API, background workers, and external data services.

These components require predictable networking, process isolation, and reproducible deployment environments.

Podman supports running related containers within Pods that share a network namespace.

Kubernetes provides a similar multi-container Pod model and adds orchestration capabilities for distributed deployments.

The production hosting platform and cluster architecture have not yet been selected.

## Decision

Use Podman for container-based development and initial deployment workflows.

Design container images and service interfaces so they can be deployed through Kubernetes if and when required.

Related containers may be placed in a shared Pod when they benefit from shared networking and coordinated lifecycle management.

Components that require independent scaling, scheduling, or failure isolation may be placed in separate Pods.

Do not require the database to run in the same Pod as application containers.

Prefer external managed PostgreSQL/PostGIS infrastructure unless operational requirements justify self-hosting.

## Pod Networking

Containers within a Podman or Kubernetes Pod share a network namespace.

This allows them to communicate using localhost and distinct listening ports.

For example, an HTTP-serving container may proxy requests to an API container over `localhost` when both belong to the same Pod.

Browser networking remains separate from container networking.

Same-origin browser requests can be supported through an appropriate reverse proxy or ingress configuration.

Shared Pod networking does not inherently remove cross-origin restrictions between different browser-visible origins.

## Deployment Boundaries

The following components must remain logically independent:

- Frontend.
- Core API.
- GIS processing workers.
- Enterprise integration workers.

Physical Pod placement will be determined by lifecycle, resource, networking, and scaling requirements.

Containers within one Kubernetes Pod are scheduled together and scale as a unit.

## Alternatives Considered

### Single Application Container

Simplifies deployment but combines unrelated process lifecycles and responsibilities.

### Traditional Multi-Container Deployment Without Pods

Viable, but does not provide the shared network namespace model preferred for related Atlas components.

### Kubernetes from the Beginning

Provides orchestration capabilities but introduces additional infrastructure and administrative responsibilities.

## Consequences

- Podman can provide a development environment resembling Kubernetes Pod networking.
- Application components retain separate container images and processes.
- Localhost communication is available between containers sharing a Pod.
- Individual containers can use specialized dependencies.
- Independently scaled components will require separate deployments or Pods.
- Kubernetes remains an available deployment path without being an immediate infrastructure requirement.

## Future Considerations

Production orchestration, service ingress, resource limits, persistent storage, network policy, and high availability will be addressed when the deployment environment is selected.
