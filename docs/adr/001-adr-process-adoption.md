# ADR-001: ADR Process Adoption

## Metadata

- **Status**: Accepted
- **Date**: 2026-02-12
- **Tags**: `process`, `documentation`
- **Affected areas**: all -- this ADR defines how architectural decisions are recorded
- **Authors**: system-tests maintainers

## Context

Design decisions in system-tests were recorded in two separate locations with
inconsistent formats:

- `docs/RFCs/` contained one RFC (manifest files) and a minimal README.
- `docs/internals/RFC/DEPRECATED/` contained a deprecated RFC (feature coverage).
- `docs/internals/revamp-asynchronous-model.md` was a design decision document
  that lived alongside operational docs.

This made it hard to discover past decisions, understand their status, or follow
a consistent process when proposing new ones.

[Architecture Decision Records](https://adr.github.io/) (ADRs) are a
well-established practice for capturing significant design decisions alongside
their context, consequences, and evolution over time. The
[quickhouse](https://github.com/DataDog/quickhouse) repository uses a mature ADR
model that includes numbered records, a template, a knowledge-map index, and
additional mechanisms for tracking gaps, deviations, supplements, and
architecture evolution.

## Decision

Adopt an ADR process for system-tests, modeled on quickhouse but **simplified**
to match the needs of a testing framework.

### What we adopt

| Element | Description |
|---------|-------------|
| Numbered ADRs | `docs/adr/NNN-slug.md`, one file per decision |
| Template | `docs/adr/000-template.md` with metadata, context, decision, consequences, decision log, implementation status, and references |
| README index | `docs/adr/README.md` with a knowledge map and master table |
| Status definitions | Proposed, Accepted, Deprecated, Superseded |

### What we skip (for now)

| Element | Why it is deferred |
|---------|--------------------|
| `gaps/` | Gaps track design limitations discovered in production. System-tests does not run a production service; gaps in test coverage are tracked differently (manifests, features dashboard). |
| `deviations/` | Deviations document intentional divergences from ADR intent during implementation. System-tests has fewer moving parts and shorter feedback loops, making deviations easier to capture in the decision log of each ADR. |
| `supplements/` | Supplements hold detailed implementation plans and load-test runbooks. System-tests design decisions are smaller in scope and do not require separate supplement documents. |
| `EVOLUTION.md` | The evolution document ties gaps, deviations, and characteristics together. Without those sub-directories, the evolution document has no content to link to. |

Any of these can be introduced later by creating a new ADR that extends this
process.

### Migration of existing documents

Existing RFCs and design decision documents are **copied** into ADR format.
The original files remain in place to preserve existing links and history.

| Original location | ADR |
|--------------------|-----|
| `docs/RFCs/manifest.md` | [ADR-002](002-manifest-files.md) |
| `docs/internals/revamp-asynchronous-model.md` | [ADR-003](003-setup-test-split.md) |
| `docs/internals/RFC/DEPRECATED/RFC-feature-coverage.md` | [ADR-004](004-feature-coverage.md) |

## Consequences

### Positive

- All design decisions are discoverable from a single index.
- New decisions follow a consistent template, making them easier to write and
  review.
- The decision log section in each ADR captures how decisions evolve without
  requiring a new document.

### Negative

- Existing RFCs are now duplicated (original files kept, ADR copies created).
  This may cause drift if someone edits only one copy.
- Contributors must learn the ADR format, adding a small step to the process.

### Risks

- If the ADR process is not adopted by contributors, the directory becomes
  stale. Mitigated by linking the ADR index from the main documentation README
  and the contributing section.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-12 | Adopted simplified ADR model | Full quickhouse model (gaps, deviations, supplements, EVOLUTION.md) is designed for a database engine under active architecture evolution. System-tests is a testing framework with fewer architectural pivots; the simplified model covers current needs without unnecessary overhead. |
| 2026-02-12 | Keep original RFC files in place | Preserves existing links and git history. ADR copies serve as the canonical format going forward. |

## Implementation Status

### Implemented

| Component | Location | Status |
|-----------|----------|--------|
| ADR template | `docs/adr/000-template.md` | Done |
| ADR-001 (this document) | `docs/adr/001-adr-process-adoption.md` | Done |
| ADR-002 (manifest files) | `docs/adr/002-manifest-files.md` | Done |
| ADR-003 (setup/test split) | `docs/adr/003-setup-test-split.md` | Done |
| ADR-004 (feature coverage) | `docs/adr/004-feature-coverage.md` | Done |
| ADR index | `docs/adr/README.md` | Done |

### Not Yet Implemented

| Component | Notes |
|-----------|-------|
| gaps/, deviations/, supplements/ | Deferred -- see decision above |
| EVOLUTION.md | Deferred -- see decision above |

## References

- [ADR homepage](https://adr.github.io/)
- [quickhouse ADR directory](https://github.com/DataDog/quickhouse/tree/main/docs/adr) -- the model this process is based on
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) -- Michael Nygard's original blog post
