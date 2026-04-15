# Architecture Decision Records (ADR) Index

This directory captures significant design decisions for system-tests.
Each ADR records the context, decision, consequences, and evolution of an
architectural choice. See [ADR-001](./001-adr-process-adoption.md) for why and
how this process was adopted.

## Knowledge Map

### Process

- **[ADR-001](./001-adr-process-adoption.md)**: Why system-tests uses ADRs and
  what was adopted (and deferred) from the quickhouse model.

### Scenarios / Container lifecycle

- **[ADR-002](./002-skip-empty-scenario-containers.md)**: Skip container startup
  entirely when no tests are selected, using image labels for version info.

---

## Master Index

| ADR | Title | Status | Tags |
|-----|-------|--------|------|
| [000](./000-template.md) | Template | - | `meta` |
| [001](./001-adr-process-adoption.md) | ADR Process Adoption | **Accepted** | `process`, `documentation` |
| [002](./002-skip-empty-scenario-containers.md) | Skip Container Startup for Empty Scenarios | **Accepted** | `scenarios`, `containers`, `ci`, `framework` |

## Creating a New ADR

1. Copy [000-template.md](./000-template.md) to `NNN-slug.md` where `NNN` is
   the next available number.
2. Fill in the metadata, context, decision, and consequences sections.
3. Set status to **Proposed**.
4. Open a PR for review. Once approved, change status to **Accepted**.
5. Add an entry to the Master Index table above.

## Status Definitions

- **Proposed**: Under discussion, awaiting review.
- **Accepted**: Approved plan of record. Implementation should follow this.
- **Deprecated**: No longer applies. Kept for historical context.
- **Superseded**: Replaced by a newer ADR (link to the replacement).

## See Also

- [Documentation index](../README.md)
- Internal design docs: [docs/internals/](../internals/README.md)
