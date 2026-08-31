# ADR-0004: Downloads create local sources, not separate content entities

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "When does acquisition produce a local source, and how is that source then represented?"

## Context

Traditional media servers maintain a separate "library" of owned content distinct from streaming availability. This bifurcates the content universe into "library content" vs. "streaming content" and is a major limitation of the traditional model. The vision states downloading is a secondary capability, not a gating condition for catalog presence.

## Decision

A completed download becomes another source for the existing content item. It does not create a separate "owned library entity."

```
Movie: The Matrix
│
├── Debrid Source
│   └── 4K REMUX
│
├── Usenet Source
│   └── 1080p WEB-DL
│
└── Local Source
    └── /media/movies/...
```

"Library" is a view/state of the catalog, not a separate content universe. The internal model is:

```
Content
   ↓
Sources
   ↓
Availability
```

not `Library Content` vs. `Streaming Content`. UI views such as All Content, My Library, Available Now, Downloaded, and Watchlist are filters over the same unified catalog.

## Rationale

A local file is just another way to play the same content. Treating it as a source (per ADR-0002) keeps the content model uniform and eliminates the library/streaming bifurcation that limits traditional media servers. This is one of the places the new architecture can remove a structural limitation of the existing ecosystem.

## Alternatives considered

- **Separate owned-library entity per download.** Rejected: bifurcates the content universe, duplicates identity, and forces the UI to reconcile two models.
- **No download/local-source support initially.** Rejected: local media is a valid source and fits cleanly; excluding it would distort the source model.

## Consequences

- Local media is a provider type (per ADR-0002) that produces local sources.
- Acquisition produces a local source attached to the existing content item.
- "Library" is a presentation concept (a view/filter), not a data-model concept.
- The catalog does not distinguish "downloaded" vs. "streaming" at the content level — only at the source level.
