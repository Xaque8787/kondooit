# ADR-0001: Live TV is a first-class content type

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should IPTV live TV and VOD fit into the unified content model?"

## Context

The vision states the catalog should be unified and that IPTV must fit into it. A live TV channel is structurally different from a movie or episode: a movie has identity → source → playable asset, while a live channel has channel identity → current schedule → current stream. An EPG program has metadata and identity but is not equivalent to an episode. Forcing live TV into the movie/series/episode model would create an artificial data model.

## Decision

Live TV is a first-class domain type with its own model. The catalog is unified at the catalog/navigation layer, not at the underlying data-model layer.

The content hierarchy:

```
Content
├── OnDemand
│   ├── Movie
│   └── Series
│       └── Episode
│
└── Live
    ├── Channel
    └── Program/Event
```

The core supports a common concept (Media Item / Catalog Item) with specialized types underneath. Live TV shares catalog, metadata, user, search, and playback infrastructure where appropriate, but has its own domain model.

## Rationale

A live channel (identity → schedule → stream) and a movie (identity → source → asset) have fundamentally different shapes. Unifying them at the data-model layer would distort both. Unifying them at the catalog/navigation layer gives the user one coherent interface (Home → Movies / TV Shows / Live TV / Search) without a fake data model.

## Alternatives considered

- **Force live TV into the title/episode model.** Rejected: an EPG program is not an episode, and a channel is not a series. This would leak IPTV-specific concepts into the VOD model and vice versa.
- **Separate live TV into its own top-level subsystem with no shared infrastructure.** Rejected: users, search, metadata, and playback overlap enough that sharing infrastructure is valuable.

## Consequences

- The content model has a common root with specialized subtypes; it is not a single flat type.
- Catalog navigation presents Live TV alongside Movies and TV Shows.
- Metadata, search, user, and playback infrastructure must be designed to serve both OnDemand and Live types.
- EPG/schedule modeling becomes a first-class concern, not an addon.
