# 0009. Enterprise Integrations and Data Ownership

**Status:** Accepted
**Date:** 2026-11-04

## Context

MasTec uses existing enterprise platforms for project management, collaboration, and reporting.

These include Procore and Power BI.

Project Atlas is intended to provide operational autonomy for the Geomatics group without replacing these systems.

Maintaining independent copies of corporate project information could create duplicated data entry, synchronization problems, and conflicting records.

The available Procore data, API permissions, and underlying Power BI data sources are still being investigated.

## Decision

Atlas will integrate with approved corporate systems while maintaining ownership of Geomatics-specific operational data.

### Procore

Procore will remain the authoritative corporate project-management and collaboration platform.

Atlas will maintain references to corporate project identifiers and synchronize relevant project metadata when permitted.

Atlas will manage Geomatics-specific tasks, assignments, production status, and internal workflows.

Approved Geomatics deliverables may be published to Procore through authorized API integrations.

### Power BI

Power BI will remain a corporate reporting and analytics platform.

Atlas may provide approved operational data to Power BI and may display existing authorized reports.

Where practical, Atlas will retrieve shared information from the underlying approved corporate data source rather than treating a Power BI report as the authoritative source.

The integration strategy will be finalized after the existing reporting infrastructure and permissions are identified.

### Other Integrations

Autodesk Docs, external GIS providers, and other services will be integrated through supported interfaces.

External integration code should remain isolated from core application business rules.

## Data Ownership Principles

- Corporate project records belong to their designated authoritative system.
- Atlas owns Geomatics tasks, assignments, and operational workflows.
- Geospatial reference data retains its external source attribution and lineage.
- Approved deliverable publication is recorded in Atlas and associated with its corporate destination.
- Synced data must have an identified authoritative source and refresh policy.
- Integrations must not create competing authoritative records without an explicit business requirement.

## Consequences

- Atlas can reuse enterprise information and reduce manual entry.
- The application remains operationally independent from Procore's internal project-management workflows.
- External API access and synchronization failures must be handled.
- Reporting data may not be current enough for transactional workflows.
- Integration capabilities depend on corporate permissions, licensing, and security policies.

## Open Questions

1. Which Procore products and APIs are available to the Geomatics group?
2. What project and document metadata can the integration access?
3. Does MasTec use Procore Analytics 2.0?
4. What systems supply the existing Power BI semantic models?
5. Can Atlas access an approved shared enterprise data source?
6. What authentication and application permissions will IT permit?
7. Which document publication operations are available through the organization's Procore configuration?

These questions are unresolved implementation dependencies, not accepted assumptions.
