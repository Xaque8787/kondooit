# ADR-0003: Core owns canonical content identity

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should metadata identity be represented (TMDB/TVDB IDs, custom IDs, cross-provider matching)?"

## Context

Providers are heterogeneous. TMDB/TVDB supply canonical IDs for movies/TV, but a torrent indexer result may only carry a filename like `Movie.Name.2025.2160p.WEB-DL...` with no external ID. If providers owned content identity, the core would be at the mercy of whichever IDs each provider chose to supply, and cross-provider matching would be inconsistent.

## Decision

Server-side content identity is authoritative. Providers supply identifiers when available and metadata otherwise; the core maps provider results to canonical identity.

**"Canonical identity" means a stable representation that allows the same content to be recognized across providers — it does not mean a full local copy of provider metadata.** Identity is lightweight. Initially, a provider/content-type/external-ID reference may be sufficient. A provider-independent identity (such as a Kondooit UUID) should be introduced only where the architecture actually requires it — for example, when user state (favorites, watch progress) must reference content independently of which provider discovered it. Not every discovered item needs a persistent Kondooit UUID.

Resolution hierarchy:

```
Provider result
       │
       ├── Known external ID?
       │       ↓
       │    Map to canonical identity
       │
       └── No ID
               ↓
        Server-side matching
               ↓
        Canonical identity
```

For movies/TV, TMDB/TVDB can provide canonical identity. For results lacking clean IDs, the server performs matching (e.g., parsing `Movie.Name.2025.2160p.WEB-DL...` to determine "this is TMDB movie X").

**Principle:** Providers provide evidence about content; the core establishes canonical content identity. Providers do not own content identity. Provider-specific IDs (TMDB IDs, TVDB IDs) are evidence — they belong at the identity-mapping boundary, not embedded as first-class fields in canonical domain entities.

## Rationale

Identity is the spine of the unified catalog — every source, every metadata field, every playback action hangs off it. If identity is inconsistent across providers, the catalog cannot be unified. Centralizing identity in the core, while letting providers contribute evidence, keeps the spine stable and the providers pluggable.

## Alternatives considered

- **Require providers to supply canonical IDs.** Rejected: many providers (torrent indexers, some IPTV VOD, Usenet) do not carry TMDB/TVDB IDs. This would exclude large parts of the ecosystem.
- **Let each provider own its own identity namespace.** Rejected: makes cross-provider source aggregation for the same content impossible.

## Consequences

- The core has an identity-resolution subsystem that accepts provider evidence (IDs, filenames, metadata) and maps to canonical identity.
- Providers are simpler: they report what they see, not what the canonical identity is.
- Server-side matching (filename parsing, fuzzy matching) is a first-class core capability.
- Canonical identity is the join key across sources, metadata, playback, and user state.
- **Canonical identity is lightweight.** It does not require persisting a full copy of provider metadata. The primary browsing experience is provider-driven; local persistence is for application state and optional caching, not for reproducing the provider catalog.
- **Provider-specific IDs are evidence, not canonical fields.** TMDB IDs and TVDB IDs belong in a provider-identity mapping, not as first-class fields (`tmdb_id`, `tvdb_id`) on canonical domain entities.
