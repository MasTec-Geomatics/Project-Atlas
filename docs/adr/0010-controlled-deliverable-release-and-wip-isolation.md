# 0010. Controlled Deliverable Release and WIP Isolation

**Status:** Accepted
**Date:** 2026-11-04

## Context

The Geomatics group produces working datasets and documents that may be incomplete, unverified, or subject to revision.

Other project participants have previously accessed WIP information and used it for downstream engineering or field operations.

This can cause avoidable rework and creates uncertainty about which information was officially released.

Atlas must distinguish internal production information from approved deliverables.

## Decision

Establish a controlled deliverable lifecycle with explicit review, approval, and publication steps.

WIP files and datasets will remain in storage locations restricted to authorized Geomatics personnel.

Atlas will track deliverable revisions and their lifecycle status.

Only authorized users or services may initiate publication of an approved revision.

Publication will transfer or register an approved, identifiable revision in the designated Procore location.

A published revision must remain traceable to its approval record and original released content.

## Proposed Lifecycle

1. **WIP:** Internal production.
2. **Internal Review:** Submitted for QA/QC.
3. **Approved:** A specific revision is authorized for release.
4. **Published:** The approved revision has been successfully published to the designated destination.
5. **Superseded/Archived:** A later revision replaces the current release or the deliverable is archived.

Review rejection and return-to-WIP behavior will be defined during workflow implementation.

Approval and publication are separate events. A failed upload does not make a deliverable published.

## Publication Records

Each release should retain:

- Atlas project and deliverable identifiers.
- Deliverable type and revision.
- Approving user and approval timestamp.
- Publishing identity and publication timestamp.
- Content checksum.
- Destination system and document identifier.
- Publication result and error details.
- Relationship to preceding or superseding revisions.

## Access Control

Access restrictions must be enforced by underlying storage and database permissions, not solely by Atlas interface controls.

The publishing integration should use least-privilege credentials.

Users without release permissions must not be able to bypass approval through the application.

Released content should be an immutable snapshot or independently versioned copy, rather than a reference to a mutable working file.

## Alternatives Considered

### Manual File Publication

Requires less development but offers inconsistent auditability and greater opportunity for accidental WIP distribution.

### Automated Publication Without Approval

Reduces manual steps but does not provide adequate release control.

### Approved and Audited Publication

Establishes a traceable release process with authorization and revision records.

This is the selected approach.

## Consequences

- Geomatics gains control over its internal production information.
- Official releases become traceable and auditable.
- Other departments can distinguish approved deliverables from working information.
- Additional review and publication steps must be maintained.
- Storage permissions and Procore publication rights must be coordinated with IT.
- Publication records can help investigate the origin of downstream errors.

The system provides technical controls and supporting evidence. It does not independently determine contractual responsibility or liability for rework.

## Future Considerations

Specific approval roles, deliverable classifications, automated QA checks, retention policies, and publication APIs will be finalized with departmental management and IT.
