# ADR-0002: Provider vs. Source distinction

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "What constitutes a 'source'?", "What constitutes a 'provider'?"

## Context

The terms "provider" and "source" are used throughout the vision but were not sharply distinguished. Without a precise definition, research and interface design will conflate integrations (e.g., a Real-Debrid account) with the concrete availability they return (e.g., a 1080p WEB-DL of The Matrix).

## Decision

A **Provider** is an integration capable of performing one or more operations. A **Source** is a concrete piece of media availability returned by a provider for a particular piece of content.

Provider capability is separate from provider instance. There is a three-level hierarchy:

```
Provider Type        (e.g., Debrid)
     ↓
Provider Instance   (e.g., My Real-Debrid account)
     ↓
Source              (e.g., 1080p WEB-DL of The Matrix)
```

Examples:

- Content: The Matrix (1999) → Provider Instance: My Real-Debrid account → Sources: 1080p WEB-DL, 2160p REMUX, 1080p BluRay.
- Content: The Matrix → Provider Instance: Local Storage → Source: `/media/movies/The Matrix (1999)/The Matrix.mkv`.
- Content: ESPN → Provider Instance: My IPTV Subscription → Source: Channel ID 104.

## Rationale

Separating type from instance supports multiple accounts of the same kind (two Debrid accounts, two IPTV subscriptions). Separating provider from source keeps the integration boundary clean: a provider is plugged in once and can return many sources over time.

## Alternatives considered

- **Use "provider" and "source" interchangeably.** Rejected: loses the integration-vs-availability distinction and makes multi-account support awkward.
- **Model only provider instances, no provider type.** Rejected: loses the useful abstraction for capability grouping and multi-account scenarios.

## Consequences

- Three distinct concepts in the model: Provider Type, Provider Instance, Source.
- The catalog/content layer references Sources; it does not couple directly to Provider Instances.
- Multi-account configurations are representable without special cases.
- Provider interface design must separate "what operations this kind of provider performs" (type) from "this configured account" (instance).
