# System Vision — Server-Centric Media Platform

> North Star document. This describes the intended end state. It is deliberately implementation-agnostic. Specific technology, protocols, and interfaces are decided in `architecture/` and recorded as ADRs in `decisions/`.

## What the product is

A self-hosted, server-centric media platform. Conceptually: **server-centric Kodi.**

A single self-hosted server acts as the central source of truth and orchestration point for a unified media catalog. Clients — Android, Apple, Web, TV, and others — are intentionally thin. They connect to the server, authenticate, browse the server's unified catalog, request playback, and receive media.

## What problem it solves

Today's self-hosted media ecosystem is fragmented across many specialized applications (Sonarr, Radarr, Prowlarr, Jellyfin, AIOStreams, Torrentio, Comet, MediaFusion, Decypharr, NZBDAV, AltMount, Dispatcharr, Threadfin, and others). Each app owns part of the pipeline — metadata, acquisition, indexing, playback, transcoding — and they communicate through brittle, indirect workarounds: spoofed download clients, adapter chains, reverse-engineered integrations, and duplicated logic.

The result is that media intelligence is scattered, clients are thick, and the ecosystem's boundaries are historical accidents rather than clean abstractions.

This project consolidates the **capabilities** that make the ecosystem useful behind one clean, unified, server-centric architecture — without recreating the existing ecosystem inside a single application.

> The goal is not to recreate the existing ecosystem inside one application. The goal is to identify and implement the underlying capabilities that make the ecosystem useful.

## What the user experience should feel like

A user opens a client (phone, tablet, TV, web). They sign in. They immediately see real content — trending movies, popular TV shows, new releases, genres — populated dynamically from configured metadata providers. They have not imported anything. They have not downloaded anything. The content is there because the providers know about it.

They browse, search, and select a title. The server resolves the best available source — local, Debrid, IPTV VOD, Usenet, or another streaming source — and playback begins. The client stays thin. The server does the thinking.

A title appears in the discovery interface because a metadata provider knows about it. The primary question is "Can this content be played?", not "Has this content been downloaded?" and not "Has this content been imported into a local database?"

## Server / client philosophy

- The **server** owns metadata discovery, content identity, source discovery, resolution, ranking, acquisition orchestration, playback routing, users, profiles, permissions, configuration, job management, and event/state.
- The **client** authenticates, browses, requests playback, and renders media. It is intentionally thin.
- Media intelligence lives on the server. Clients do not run their own source discovery, indexer integration, or metadata scraping.

## Provider-driven content discovery

Kondooit is not a traditional local media library. The primary user experience is **discovery** — browsing content that metadata providers know about — not browsing a locally persisted catalog.

When a user opens Kondooit, the server queries configured metadata providers (TMDB, TVDB, and future providers) and presents a unified discovery interface: trending movies, popular TV, now playing, upcoming, genres, search results. The user has not imported anything. The content is there because the providers know about it.

The intended flow is:

```
User opens Kondooit
        ↓
Server queries configured metadata providers
        ↓
Provider APIs return content (trending, popular, search, etc.)
        ↓
Server aggregates, deduplicates, and applies provider priority
        ↓
User sees unified content discovery interface
        ↓
User browses / searches / selects content
        ↓
Eventually: server resolves that content to playable sources
```

This is fundamentally different from:

```
Provider → Search → Import → Local database → Browse
```

The "import" workflow is not the intended product behavior. A user should never have to import content into a local database merely for it to appear in the UI.

## Four distinct concepts

The architecture must distinguish four concepts that are often conflated:

### 1. Provider metadata

Information obtained dynamically from external metadata providers (TMDB, TVDB, etc.). This includes titles, overviews, artwork, genres, release dates, ratings, cast, seasons, and episodes. Provider metadata is **not** owned by Kondooit — it is evidence about content that providers supply on demand.

### 2. Kondooit content identity

The provider-independent representation necessary to reason about the same content across providers. If TMDB and TVDB both describe "The Matrix," Kondooit should be able to recognize that they are the same conceptual movie.

Content identity is **lightweight**. It does not require persisting a full copy of provider metadata. Initially, a provider/content-type/external-ID reference may be sufficient. A provider-independent identity (such as a Kondooit UUID) should be introduced only where the architecture actually requires it — not prematurely for every discovered item.

### 3. User state

Things that belong to the user, not to the content catalog:

- favorites
- watch state / progress
- watch history
- preferences
- playlists (potentially)
- other user-specific information

A user favoriting a movie does not mean Kondooit has imported that movie into a media library. User state references content identity, not a local catalog entry.

### 4. Playable sources

Actual ways of playing/accessing the content, which are a separate future capability:

- local media files
- IPTV/VOD
- Debrid services
- Usenet
- other source/acquisition systems

Source discovery operates on content identity — the same identity established during metadata discovery. The flow is:

```
Content Discovery (metadata providers)
         ↓
  Kondooit Content Identity
         ↓
Source Resolution (source providers — future)
         ↓
  Playable Source
         ↓
     Playback
```

These four concepts must not be conflated. Metadata discovery, content identity, user state, and source resolution are separate architectural concerns.

## What should remain local

Kondooit retains information locally when it is **application state**, not merely because provider metadata exists:

- administrator/user accounts
- provider configuration (API keys, enable/disable)
- provider priority configuration
- user preferences
- favorites and watch state (future)
- provider identity mappings where architecturally useful
- source configuration (future)
- playback/session state (future)

Caching provider responses may be useful for performance, rate limiting, or resilience, but **cache ≠ canonical media library**. The architecture should not assume that every piece of provider metadata needs to become a permanent local database record.

## Unified content model

Content is represented independently of where it comes from. A single movie may simultaneously have:

- local media availability
- Debrid availability
- IPTV VOD availability
- Usenet availability
- other streaming availability
- downloadable availability

These are different **sources/providers** for the same underlying **content**. Metadata and content identity are separated from content acquisition and playback. TMDB, TVDB, or similar metadata providers supply evidence about content; Kondooit establishes identity and presents a unified discovery interface.

The discovery interface presents:

- movies
- TV shows
- seasons
- episodes
- collections
- genres
- trending / popular
- now playing / upcoming
- search
- (future: continue watching, recommendations, history)

Content does **not** need to exist locally to appear in the discovery interface. A title is visible because a metadata provider knows about it.

## Provider / capability philosophy

The core server is intentionally capability-agnostic. The core provides foundational services; capabilities are delivered through well-defined provider/plugin interfaces.

Different capabilities have appropriate abstractions. There is no universal "Provider" superclass:

- **MetadataProvider** — discovers content and supplies metadata evidence (TMDB, TVDB, etc.)
- **SourceProvider** (future) — discovers playable sources for content (local files, IPTV VOD, Debrid, Usenet, etc.)
- **PlaybackProvider / SourceResolver** (future) — resolves and serves playable streams

These abstractions are introduced only when the corresponding capability is actually being implemented. Do not create future abstractions merely for theoretical completeness.

Metadata providers are **not special**. TMDB and TVDB are ordinary implementations of the MetadataProvider capability. The application depends on the abstraction, not on `TmdbService` or `TvdbService` embedded throughout.

Providers declare which capabilities they support. If TMDB supports a discovery operation that TVDB does not, the architecture must be capable of expressing that difference — not forcing TVDB to implement a fake equivalent or weakening the abstraction to the lowest common denominator.

Provider priority is a **configuration decision**, not an architectural principle. TMDB may be the initial default priority because it currently provides richer discovery APIs, but that is configurable, not hardcoded.

Potential capability categories (examples, not final decisions):

- Metadata providers
- Source discovery providers
- Playback providers
- Acquisition providers
- Local media providers
- IPTV providers
- Usenet providers
- Debrid providers
- Indexer providers
- Storage providers
- Network / connectivity providers
- Transcoding providers
- EPG providers

Playback is not necessarily hard-coded into the core. The architecture remains open to discovering better abstractions during research.

## Deduplication

If TMDB and TVDB both return "The Matrix," the user should not see two unrelated movies. Kondooit should present one conceptual item with multiple provider identities.

Deduplication is handled at the **aggregation/discovery layer**, not by making one provider a special case. Potential identity signals include:

- provider IDs
- media type
- release year
- original title
- other provider metadata
- external cross-references where available

The exact identity-resolution mechanism should be designed carefully. Do not solve this by simply assuming that matching titles are identical. Do not build a sophisticated identity-resolution system prematurely — start with provider IDs as the primary deduplication key and evolve as needed.

## Streaming-first behavior

The system is streaming-first. The default flow is:

```
content selection
→ source discovery
→ candidate sources
→ availability / resolution
→ source selection
→ stream
```

A title can be played as soon as a source is resolved. Downloading is not required to play. Content does not need to be imported into a local database to be discovered or selected.

## Optional acquisition / download behavior

Downloading and persisting content locally is a **secondary** capability. It exists for users who want offline access, archival, or local-library management. It is never the gating condition for a title appearing in the catalog or being playable.

## Local media

Local media is one provider among many. A locally stored file is a source for content the same way a Debrid stream or IPTV VOD entry is a source. The unified content model treats them uniformly.

## IPTV

IPTV contributes two distinct capabilities:

- **Live TV / channels** — a linear/EPG-oriented view.
- **VOD** — IPTV-provided video-on-demand entries that behave as sources for catalog content.

Both must fit cleanly into the unified content model. How live linear content and VOD map onto the same content identity is an open architectural question.

## Debrid

Debrid services act as source discovery providers (resolving cached torrent availability) and as playback providers (serving cached streams). They are treated as providers behind clean interfaces, not as special cases in the core.

## Usenet

Usenet indexers act as source discovery providers; Usenet downloaders act as acquisition providers. As with Debrid, these are providers behind clean interfaces.

## Source discovery

Source discovery is a first-class architectural concept. The existing ecosystem uses many overlapping applications (Prowlarr, Sonarr, Radarr, AIOStreams, Torrentio, Comet, MediaFusion, Decypharr, NZBDAV, AltMount, etc.) that solve overlapping problems in different ways.

The new system does **not** assume those applications' current boundaries are the correct boundaries. For example, Sonarr/Radarr are traditionally acquisition/automation apps, but portions of their functionality are used indirectly by other apps as scaffolding or spoofed download-client workflows to facilitate remote/Debrid media. The new architecture identifies the underlying capability rather than reproducing the workaround.

The conceptual flow:

```
content request
→ source discovery
→ candidate sources
→ availability / resolution
→ source selection
→ stream OR download
```

Source discovery may use torrent/indexer providers, Debrid providers, Usenet indexers, IPTV VOD providers, or other discovery mechanisms. To the core, these all appear as clean provider interfaces. The exact interfaces are not finalized — they must be investigated against actual source code of relevant projects.

## Playback routing

Two playback routing modes are envisioned:

1. **Server resolves, client retrieves.** The client asks the server what source should be played. The server resolves the source. The client retrieves the stream directly from the provider.

2. **Server resolves and proxies.** The client asks the server to play content. The server resolves the source, retrieves the stream, and proxies it to the client.

The second mode is important: it lets the server act as a media gateway, keeping upstream provider connectivity centralized, and lets multiple geographically separated clients use the same upstream provider connection originating from the server (subject to the provider's terms and stream/session limits).

This is an architectural concept, not an implementation requirement yet.

## Remote connectivity

Remote client connectivity should ideally not require users to manually configure port forwarding. `iroh` is being considered as a built-in connectivity mechanism:

- the server has an iroh node identity
- clients connect to the server through iroh
- iroh attempts direct peer-to-peer connectivity
- relay infrastructure is used when direct connectivity is unavailable

A conventional domain / reverse-proxy option may also be supported (Caddy, Traefik, or future networking providers). Networking should ultimately be abstracted so the media application is not tightly coupled to one connectivity mechanism.

Do not implement networking yet.

## Multi-user behavior

The server supports multiple users, profiles, and permissions. Continue-watching, recommendations, and history are user-specific. Permissions govern who can browse, play, download, administer, etc.

## Distinction from combining existing applications

This project is **not** a bundle or merge of existing applications. It does not preserve their internal architectures, their application boundaries, or their ecosystem workarounds.

It studies them to extract **capabilities**, identifies the **abstractions** behind those capabilities, and implements those capabilities behind a clean unified architecture. Existing implementations may inform or supply reusable code, but the architecture is designed top-down from the product vision — not assembled bottom-up from existing apps.

## Deployment model

Kondooit is designed for self-hosted, containerized deployment. Docker is the preferred and officially supported deployment mechanism. A user should be able to run the server from a clean checkout using Docker Compose without manually installing runtime dependencies on the host.

This is a deployment preference, not a domain concept. The application architecture must not depend on Docker-specific assumptions.

## Implementation technologies are subordinate to the domain

Implementation technologies — the API framework, database, client framework, networking layer, media processor, and deployment mechanism — are replaceable. The Kondooit domain model and capability abstractions are the core of the system. Any implementation that creates unnecessary coupling between a specific technology and the domain is an architectural smell.

Specific technology choices are recorded as ADRs in `decisions/`, not in this vision document.

## Open questions

Specific technology, protocols, plugin interface shapes, and the precise core/provider boundary are **not** decided in this document. They live as open questions in `architecture/` and will be resolved through research and recorded as ADRs in `decisions/`.
