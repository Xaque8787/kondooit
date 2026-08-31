# Decisions — Architectural Decision Records (ADRs)

This directory holds ADRs: records of significant architectural decisions.

## Format

Filename: `ADR-NNNN-short-title.md` (zero-padded number, kebab-case title).

Each ADR contains:

- **Title** and ADR number
- **Status** — one of the statuses defined in "Decision Status" below
- **Date**
- **Context** — why this decision is being made, including relevant open questions and research
- **Decision** — what was decided
- **Rationale** — why
- **Alternatives considered** — and why they were rejected
- **Consequences** — positive and negative
- **Supersedes** / **Superseded by** — when applicable

## Decision Status

Every ADR has a `Status` field restricted to these four values:

- **Proposed** — drafted but not yet accepted. Not authoritative; do not build on it as if it were decided.
- **Accepted** — adopted and currently authoritative. Future work must respect it until it is superseded or deprecated.
- **Superseded** — replaced by a later ADR. The `Superseded by` field names the replacing ADR. The original decision text is preserved unchanged for history; only the `Status` and `Superseded by` fields are updated.
- **Deprecated** — withdrawn without a direct replacement. The decision is no longer followed, but the record is kept for history. The `Date deprecated` and a short note explaining why may be added; the original decision text is preserved.

Status transitions:

- `Proposed` → `Accepted` (or rejected and removed/deprecated).
- `Accepted` → `Superseded` by a new ADR, or → `Deprecated`.
- `Superseded` and `Deprecated` are terminal — an ADR does not return to `Accepted`.

## Rules

- **Never edit a past ADR to change a substantive decision.** To change a decision, write a new ADR that supersedes it and references the prior one, then update only the prior ADR's `Status` and `Superseded by` fields. The original decision, rationale, and alternatives must remain intact so the architectural history is preserved.
- Only metadata fields (`Status`, `Superseded by`, `Date deprecated`, and similar status annotations) may be edited on an accepted ADR. The `Decision`, `Rationale`, `Alternatives considered`, and `Consequences` sections are immutable once the ADR is `Accepted`.
- If a superseding ADR is itself later superseded, chain the references: each ADR points to the next, and the newest is the authoritative one.
- An ADR must reference the open question(s) it resolves (from `../architecture/OPEN_QUESTIONS.md`).
- This preservation discipline is especially important for an AI-assisted, long-running project: future sessions must be able to reconstruct why a decision was made, what alternatives were rejected, and when/how it changed.

## Index

- [ADR-0001: Live TV is a first-class content type](ADR-0001-live-tv-first-class-content-type.md)
- [ADR-0002: Provider vs. Source distinction](ADR-0002-provider-vs-source-distinction.md)
- [ADR-0003: Core owns canonical content identity](ADR-0003-core-owns-canonical-identity.md)
- [ADR-0004: Downloads create local sources, not separate content entities](ADR-0004-downloads-create-local-sources.md)
- [ADR-0005: Single-server, multi-user household model](ADR-0005-single-server-household-model.md)
- [ADR-0006: Playback orchestration is core; stream transport is a core subsystem](ADR-0006-playback-orchestration-and-transport.md)
- [ADR-0007: iroh is the default remote transport; the application protocol is transport-independent](ADR-0007-iroh-default-transport-independent-protocol.md)
- [ADR-0008: Technology baseline and implementation-layer boundaries](ADR-0008-technology-baseline-and-implementation-layer-boundaries.md)
- [ADR-0009: Provider-driven content discovery](ADR-0009-provider-driven-content-discovery.md)
- [ADR-0010: Provider capability declaration](ADR-0010-provider-capability-declaration.md)
- [ADR-0011: Provider priority and fallback behavior](ADR-0011-provider-priority-and-fallback.md) (Proposed)
