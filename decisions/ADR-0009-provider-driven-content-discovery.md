# ADR-0009: Provider-driven content discovery

- **Status:** Accepted
- **Date:** 2026-08-18
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "Should the primary browsing experience be backed by a locally persisted catalog or by metadata provider APIs?"

## Context

The current implementation treats the Kondooit catalog as a locally persisted mirror of provider data. The flow is: configure a provider → search the provider → "import" a result into the local database → browse the local database. If nothing has been imported, the catalog is empty and the landing page shows no content.

The System Vision states that a user should open Kondooit and immediately see real content from configured metadata providers — without importing anything. The "import" workflow is an implementation artifact, not the intended product behavior.

ADR-0003 establishes that the core owns canonical content identity. This has been interpreted in the implementation as "the core persists a full local copy of provider metadata." ADR-0003 does not actually require that — it requires identity, not a local catalog. This ADR clarifies the distinction.

## Decision

The primary content browsing experience is **provider-driven**. The landing page, search, trending, popular, genres, and discovery all query configured metadata providers and aggregate results in real time. A user does not need to "import" content into a local database for it to appear in the UI.

Local persistence is reserved for:
- **Application state** — users, provider configuration, provider priority, (future) favorites, watch state, preferences
- **Optional caching** — provider responses may be cached for performance, rate limiting, or resilience, but cache is not the primary data source
- **Identity mapping** — lightweight records that allow the same content to be recognized across providers

The "import" workflow (provider → search → import → local database → browse) is not the intended product flow. Existing import endpoints may be retained as an implementation/testing mechanism but are not the primary user experience.

## Rationale

The existing ecosystem (Jellyfin, Sonarr, Radarr, etc.) treats the local catalog as the primary surface. Kondooit's vision is different: it is a discovery-first platform where metadata providers drive the browsing experience. Forcing users to import content before they can browse reproduces the limitations of traditional media library applications.

Provider metadata is evidence supplied on demand. It does not need to become a permanent local record to be visible in the UI. The architecture should reflect this.

## Alternatives considered

- **Keep the local catalog as the primary surface, add provider browsing as a secondary feature.** Rejected: this preserves the import-then-browse paradigm that the vision explicitly rejects. It also creates two parallel browsing experiences with different data sources, which is confusing.

- **Remove all local persistence of content metadata.** Rejected: some local persistence is useful for identity mapping, optional caching, and future user state. The distinction is not "no local data" but "local data is application state and cache, not the primary catalog."

- **Treat local catalog and provider discovery as equivalent peers.** Rejected: this conflates two fundamentally different concepts. Provider metadata is dynamic evidence; local application state is owned by Kondooit. They serve different purposes.

## Consequences

- The landing page, search, and discovery endpoints query metadata providers, not a local database.
- A DiscoveryService (or evolved CatalogService) aggregates provider results, applies provider priority, and deduplicates.
- The existing local catalog tables (movies, series, seasons, episodes, genres, collections) are not the primary data source for browsing. Their eventual role should be determined deliberately — they may become a cache, an identity-mapping layer, or be phased out.
- Provider-specific IDs (tmdb_id, tvdb_id) should not be embedded as first-class fields in canonical domain entities. They belong in a provider-identity mapping.
- The "import" endpoints may be retained but are not the primary user flow.
- This ADR refines the interpretation of ADR-0003 but does not supersede it. ADR-0003 remains authoritative for identity ownership; this ADR clarifies that identity is lightweight and does not require a full local catalog.

## Relationship to other ADRs

- **ADR-0003** (Core owns canonical identity): Refined, not superseded. "Canonical identity" means a lightweight stable representation, not a full local database record.
- **ADR-0002** (Provider vs. source): Supported. Metadata providers supply evidence for discovery; source providers (future) supply playable sources. This ADR clarifies the metadata-provider side.
- **ADR-0006** (Playback orchestration): Compatible. Source resolution operates on content identity established during discovery.
