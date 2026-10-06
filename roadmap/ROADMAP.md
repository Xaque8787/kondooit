# Kondooit Roadmap

## Purpose

This document defines the planned development milestones for Kondooit.

The roadmap describes what functionality should exist at each version and
provides the implementation boundary for development.

The System Vision defines the ultimate product.

The Roadmap defines the current path toward that vision.

Architecture documents define how the current system is structured.

ADRs define why significant architectural decisions were made.

The roadmap is therefore a planning document, not an architectural authority.

---

## How to Use This Roadmap

Before beginning implementation work:

1. Read this document.
2. Identify the current milestone.
3. Read the milestone's explicit goals.
4. Read its explicit exclusions.
5. Implement only the capabilities required for the current milestone
   unless the user explicitly expands the scope.

The roadmap does not override the System Vision or accepted architectural
decisions. It constrains implementation scope, not architecture.

## Current State

| Milestone | Status |
|---|---|
| v0.0.1 — Server Foundation, Discovery & Connectivity | Complete |
| v0.0.2 — Source Providers, Discovery & Resolution | Complete except IPTV (moved to v0.0.3) |
| Delivered beyond the original plan | Playback, HLS remux/transcode, profiles, watch progress, remote access — see "Delivered Beyond the Original Milestone Plan" |
| v0.0.3 — Live TV & IPTV | **Next milestone. Planned, not yet authorized for implementation** |

The milestone sections below record what each milestone was scoped to
include and exclude at the time. Where later work delivered something a
milestone excluded, the exclusion is kept for history and annotated.

### The distinction

The roadmap defines **what** to build at each stage, not **how** to build it.

For example, v0.0.1 includes TMDB and TVDB as metadata providers. That does
not mean hard-coding `if provider == "tmdb"` branches. The architecture
already established (principle 4, ADR-0002) says capabilities are delivered
through provider interfaces. So even with only two providers in v0.0.1,
the implementation should reflect:

```
MetadataProvider
       │
       ├── TMDBProvider
       └── TVDBProvider
```

The roadmap says "build TMDB and TVDB." The architecture says "build them
as providers." Both are true. The roadmap does not excuse bypassing the
provider abstraction, and the provider abstraction does not excuse building
capabilities the roadmap hasn't called for yet.

### Hierarchy

```
System Vision
    ↓
Architecture Principles
    ↓
Accepted ADRs
    ↓
Development Roadmap
    ↓
Implementation
```

- The System Vision describes the ultimate product.
- Architecture defines how the system is structured.
- ADRs explain important architectural decisions.
- The Roadmap defines what should be implemented at the current stage.

---

## v0.0.1 — Server Foundation, Provider-Driven Discovery & Connectivity Validation

**Status: Complete**

All functional goals achieved: Docker Compose deployment, admin
authentication, TMDB + TVDB metadata providers, provider-driven content
discovery (trending, popular, genres, search, detail views), user state
(favorites, following), and a responsive React web client.

iroh connectivity validation was scoped as optional in this milestone
("A browser-based iroh client is desirable but is not required") and was
deferred. It was later delivered as full remote access (ADR-0017) — see
"Delivered Beyond the Original Milestone Plan".

### Goal

Produce the first usable Kondooit server.

A user should be able to start the Kondooit server via Docker Compose,
access it through a web browser, create/login as an administrator,
configure metadata providers, and immediately browse real content
from those providers — without importing anything.

This release intentionally has **no playback functionality**.

It proves two foundational ideas:

1. **Kondooit can discover and present content from metadata providers
   in a unified interface.** The discovery surface is populated
   dynamically from provider APIs — not from a locally persisted catalog
   that requires manual import.
2. **Kondooit can establish an iroh-based connection between a client and
   server.** The connectivity model works before the complete remote-access
   experience is built.

### Included

#### Server Foundation

- Startable self-hosted Python server (Litestar)
- Docker-based deployment
- Docker Compose development environment with local Dockerfile build
- PostgreSQL database
- Persistent database storage (volume)
- Basic server configuration
- Basic server API

#### Authentication

- Initial administrator creation on first startup
- Administrator login
- Session/authentication foundation

#### Metadata

- Provider capability architecture (per ADR-0002)
- TMDB provider
- TVDB provider
- API key configuration
- Enable/disable provider
- Test provider connection
- Metadata retrieval
- Provider capability declaration (per ADR-0010, Proposed — providers
  declare which discovery capabilities they support)
- Provider priority configuration (which provider is preferred when
  multiple return the same content)

The metadata provider architecture must be implemented as a provider
capability, not hard-coded into the discovery layer. TMDB and TVDB are
ordinary implementations of the MetadataProvider interface.

#### Content Discovery

- **Provider-driven landing page** — when a user opens Kondooit, the
  server queries configured metadata providers and presents real content
  immediately. No import step is required.
- **Trending / popular / now playing / upcoming** — discovery categories
  populated from provider APIs, aggregated across enabled providers
- **Search** — searches configured metadata providers, not a local
  database. Results are aggregated and deduplicated across providers.
- **Browse by genre** — genres sourced from provider APIs
- **Content detail view** — fetches full metadata from the provider on
  demand (title, overview, artwork, genres, seasons, episodes)
- **Aggregation and deduplication** — when multiple providers return the
  same content, the aggregation layer unifies them into one item using
  provider IDs as the primary deduplication key
- **Provider priority** — when multiple providers return the same content,
  the preferred provider's metadata is used for display

Content appears in the discovery interface because a metadata provider
knows about it — not because it has been imported into a local database,
downloaded, or has playable sources.

The "import" workflow (provider → search → import → local database →
browse) is **not** the intended product behavior for v0.0.1. The existing
import endpoints may be retained as an implementation/testing mechanism
but are not the primary user flow.

#### Content Detail View

A content detail page shows metadata (title, year, genres, synopsis, cast,
artwork) fetched from the provider on demand, and a "Sources" section that
reads:

> No playable sources currently configured.

This is intentional. The discovery brain is established before the media
delivery brain.

#### Web Client

- React + TypeScript
- Authentication UI
- Main media navigation interface
- Basic responsive design

#### iroh Connectivity Validation

iroh connectivity is an **optional transport** in v0.0.1, not a
prerequisite for server operation or web-client access. The server must
remain directly accessible through conventional HTTP during development
and testing.

The goal for v0.0.1 is **not** to implement the complete final remote
access architecture. The goal is to establish enough iroh functionality
to validate the basic server/client connectivity model independently of
conventional HTTP connectivity.

At minimum, the architecture should establish:

```
Kondooit Client
    ↓
Kondooit Networking Abstraction
    ↓
iroh
    ↓
Kondooit Server
```

The implementation should allow development/testing of:

- Server identity
- Client identity where required
- Local connectivity
- Remote connectivity
- Direct connection where possible
- Relay fallback where necessary

v0.0.1 must provide a means of validating iroh connectivity independently
of conventional HTTP connectivity. A browser-based iroh client is
desirable but is **not required** to establish the initial iroh
architectural proof.

The exact remote access UX can evolve later.

### NOT Included

- No media acquisition, source discovery, source resolution, or playback
  capabilities
- No Debrid provider integration
- No Usenet provider integration
- No IPTV provider integration
- No torrent/indexer provider integration
- No local file/media provider integration
- No playback sessions
- No transcoding
- No streaming or proxying
- No production-ready remote streaming
- No server-side stream proxying
- No multi-user profiles or permissions (single administrator only)
- No watchlist, history, or progress tracking
- No EPG or live TV
- No automated media acquisition
- No native mobile clients

The architecture may establish interfaces or boundaries needed for future
features, but actual implementation must remain within the v0.0.1 scope.

### Architecture at End of v0.0.1

```
                    Kondooit Server
                         │
              ┌──────────┴──────────┐
              │                     │
         Discovery              Users
              │                     │
     ┌────────┴────────┐          │
     │                 │          │
  Aggregation        Auth
  (priority,                                   
   dedup)           
     │                 
     │                 
  MetadataProvider
     │                 
  ┌──┴──┐               
  │     │               
 TMDB  TVDB             

         Networking
              │
         iroh (validation)
```

Not yet (at the end of v0.0.1; most of these have since been delivered —
see "Current State"):

```
Source discovery (local files, IPTV VOD, Debrid, Usenet, etc.)
Playback
Transcoding
Production remote access UX
User state (favorites, watch history, progress)
Multi-user profiles and permissions
```

### Success Criteria

A clean checkout should support:

```
docker compose up --build
         ↓
  Kondooit Server
         ↓
  Web Interface
         ↓
Create Administrator
         ↓
    Login
         ↓
Configure TMDB/TVDB
         ↓
  See Real Content Immediately
  (trending, popular, genres — from providers)
         ↓
  Search Across Providers
         ↓
  Select Content → View Details
```

And the networking foundation should allow validating iroh connectivity
**independently of conventional HTTP**:

```
Kondooit Client
      ↓
Networking Layer
      ↓
   iroh
      ↓
Kondooit Server
```

including testing direct connectivity and relay fallback. A browser-based
iroh client is desirable but not required for this proof.

There is still **no requirement to play media**.

### What This Milestone Proves

- The server can start and persist state.
- Docker Compose provides a clean-clone development experience.
- A user can authenticate.
- The provider abstraction works (metadata providers plug in behind a
  clean interface).
- Content discovery is provider-driven — the landing page populates from
  provider APIs without requiring import.
- Providers declare their capabilities — TMDB provides richer discovery
  than TVDB, and the abstraction expresses that honestly.
- Aggregation and deduplication work across providers.
- The core owns content identity (ADR-0003) — lightweight, not a full
  local catalog copy.
- Content appears in the discovery interface without being downloaded or
  imported.
- The iroh networking abstraction works (ADR-0007, ADR-0008).
- The application protocol is transport-independent.

---

## v0.0.2 — Source Providers, Source Discovery & Source Resolution

**Status: Complete except IPTV**

Delivered: source provider architecture with capability declaration,
release name parsing, TorBox (cloud search, cache check, resolve),
Easynews (direct search), the installable scraper module system
(ADR-0012) with a default module providing Torrentio and MediaFusion
scrapers, source discovery orchestration with provider priority, and
source resolution.

Not delivered: IPTV integration. It has been moved into v0.0.3 (Live TV &
IPTV), where it is planned together with channels, EPG, and IPTV VOD.

Implementation differences from the plan below:
- Modules live in `scraper_modules/` rather than `modules/`.
- Source API is `POST /source-providers/search` and
  `POST /source-providers/resolve` rather than the `GET /api/sources/...`
  routes listed below.
- Resolved URLs are passed to the player (playback was delivered later)
  rather than only displayed.

### Goal

Enable Kondooit to answer the question: **"Where can this content be
played from?"**

A user should be able to configure source providers (debrid services,
Usenet providers, IPTV services), navigate to a movie or TV episode
detail page, and see a list of playable sources discovered from their
configured providers. Selecting a source resolves it to a stream URL
that is ready for a future playback engine.

This release **does not include playback**. It proves the complete
source pipeline: discovery, cache verification, filtering, and
resolution — stopping at a resolved stream URL.

v0.0.1 answered "What content exists?" (metadata).
v0.0.2 answers "Where can I get it?" (sources).

### Two-Phase Approach: Source Providers vs. Source Resolvers

v0.0.2 draws a deliberate architectural line between two categories of
source integration, developed in two phases:

**Phase 1 — Source Providers (bundled)**

TorBox and Easynews are paid services with official, stable APIs. The
user has a subscription, enters their credentials, and uses the service
they pay for. These are analogous to metadata providers (TMDB, TVDB) —
a small, stable set of well-defined integrations that implement a clean
interface. The user's decision to configure credentials IS the conscious
choice to enable the capability.

Source providers are bundled with the core application, registered at
startup, and live in `infrastructure/providers/` alongside metadata
providers. No module loader is needed.

**Phase 2 — Source Resolvers (modular, per ADR-0012)**

Hash aggregators (Torrentio-protocol services, MediaFusion, TorrentsDB,
self-hosted hash databases) aggregate content availability information
from the broader internet. These are:

- Potentially numerous (many possible configurations and instances)
- More legally ambiguous (they index content availability, not provide
  paid service access)
- Likely community-contributed (anyone can host a Torrentio-protocol
  instance with different configurations)
- Subject to frequent change (services appear and disappear)

Source resolvers use the installable module system defined in ADR-0012.
They are developed as self-contained modules with manifests and loaded
by the core's module loader.

This distinction keeps the core focused: paid-service API clients are
bundled infrastructure (same as TMDB/TVDB), while gray-area hash
aggregation is cleanly separated into installable modules.

### Why These Source Provider Types

Source providers are not a single abstraction. The research
(umbrella.md, source_provider.md) identifies fundamentally different
source provider models that cover the majority of real-world media
access:

1. **Debrid services** (TorBox, Real-Debrid, etc.) cache torrents on
   remote servers and provide direct download links. They require a
   separate hash source (a source resolver) to find new content, then
   check which hashes are cached, then resolve cached hashes to playable
   URLs. This is a multi-step pipeline.

2. **Usenet providers** (Easynews) search their own indexes and return
   directly playable results in a single step. No cache check, no
   resolution step — the search result IS the playable source.

3. **IPTV services** provide live channels and video-on-demand via
   M3U playlists or Xtream Codes APIs. Content is organized as channels
   and categories rather than individual titles. Streams are directly
   playable URLs.

Each has different authentication, different capabilities, different
data shapes, and different orchestration requirements. They share
infrastructure (provider settings, credential storage, enable/disable,
priority) but have distinct interfaces.

### Included

#### Phase 1: Bundled Source Providers

##### Source Provider Architecture

- **SourceProvider interface** — a new abstract interface separate from
  MetadataProvider. Source providers declare their capabilities just as
  metadata providers do (per ADR-0010), but the capability set is
  different: direct search, cloud search, cache check, resolution.

- **Source capability declaration** — each source provider declares
  which operations it supports. The orchestration layer only calls
  capabilities a provider declares.

- **SourceResult domain entity** — the canonical representation of a
  discovered source, independent of which provider found it. Includes:
  release name, quality tier, file size, source type (direct, cached
  torrent, uncached torrent, cloud file, IPTV stream), codec/audio/HDR
  metadata, and either a stream URL (direct sources) or an info_hash
  (torrent sources).

- **Provider credential storage** — extends the existing
  provider_settings table to accommodate source providers. Some need a
  single API key (TorBox), some need username + password (Easynews),
  some need a URL (IPTV playlists).

- **Provider configuration UI** — the existing providers page is
  extended to show source providers alongside metadata providers, with
  appropriate credential fields for each type.

##### IMDB ID Pipeline (Prerequisite)

Source discovery uses IMDB IDs as the primary content lookup key. The
current system uses TMDB/TVDB external IDs internally and does not carry
IMDB IDs.

- Extend metadata evidence dataclasses to include `imdb_id`
- Update TMDB provider to extract `imdb_id` from movie detail responses
  (TMDB returns this directly) and from series detail responses (via
  `external_ids` append)
- Carry `imdb_id` through the discovery API to the frontend
- The frontend passes `imdb_id` when requesting source discovery

This is a prerequisite for the source pipeline, not a standalone
feature.

##### Release Name Parsing

Release names follow industry-standard conventions (e.g.,
`Movie.2022.1080p.WEB-DL.x264.DD5.1-GROUP`). Parsing them is genuine
domain logic — it classifies media releases into quality tiers and
extracts technical metadata.

- **Quality detection** — 4K/UHD, 1080p, 720p, SD from release names
- **Codec detection** — x264/AVC, x265/HEVC, AV1
- **Audio detection** — DTS, Dolby Digital, Atmos, TrueHD (display
  metadata, not filtering criteria)
- **Source tag detection** — WEB-DL, BluRay, HDTV, Remux
- **Title validation** — verify a discovered source actually matches the
  requested content by comparing normalized titles

This parsing is used by all source provider types to classify results
into a uniform quality model. It belongs in the domain layer as pure
functions with no infrastructure dependencies.

##### TorBox Integration (Debrid)

TorBox is the first debrid provider implementation. It is **bundled**
with the core — a paid service with an official API.

- **Authentication** — Bearer token (user provides API key)
- **Cloud search** — query the user's existing TorBox library for
  content matching the requested title/IMDB ID
- **Batch cache check** — send a list of discovered info_hashes to
  TorBox's cache check endpoint; returns which are instantly available
- **Source resolution** — for cached hashes, request a temporary direct
  download URL from TorBox
- **Capabilities: CLOUD_SEARCH, CACHE_CHECK, RESOLVE**

TorBox can search its own cloud storage independently. For cache
checking against broader content, it needs hashes from a source
resolver (Phase 2). In Phase 1, TorBox's cloud search is functional
on its own.

The implementation must be behind the SourceProvider interface so that
Real-Debrid, Premiumize, AllDebrid, or any future debrid service can be
added as additional implementations without changing the orchestration
layer.

##### Easynews Integration (Usenet)

Easynews is the first Usenet provider implementation. It is **bundled**
with the core — a paid service with an official API.

- **Authentication** — HTTP Basic Auth (username + password)
- **Search** — queries Easynews's Solr search API with title + year
  (movies) or title + S##E## (episodes), filtered to video file types
- **Direct results** — search results include a direct download URL
  constructed from the post hash, farm, and port. No cache check or
  resolution step is needed.
- **Capabilities: DIRECT_SEARCH**

Easynews is self-contained: it discovers AND serves content in one step.
Its results are marked as direct sources and skip the cache check
pipeline entirely.

##### IPTV Integration

> **Moved to v0.0.3.** Not implemented in v0.0.2. The full plan now lives
> in [livetv_research.md](../research/livetv_research.md). The text below
> is kept for history.

IPTV providers offer live TV channels and video-on-demand content via
standard playlist formats. They are **bundled** with the core — paid
subscriptions using standard protocols.

- **M3U playlist support** — parse standard M3U/M3U8 playlists to
  extract channels and VOD entries with stream URLs, group/category
  tags, channel names, and logo URLs
- **Xtream Codes API support** — query Xtream Codes-compatible servers
  for live channels, VOD categories, and VOD streams using
  username/password/server URL credentials
- **Authentication** — URL-based (playlist URL) or username + password +
  server URL (Xtream Codes)
- **Content mapping** — IPTV content is organized by categories and
  channels, not by IMDB ID. Matching IPTV content to metadata-provider
  content (so sources appear on detail pages) requires title-based
  fuzzy matching. IPTV VOD content is exclusively a source provider —
  it appears as source results on movie and episode detail pages through
  the unified source search pipeline. There is no dedicated IPTV VOD
  browse section. Unmatched VOD (content that cannot be parsed into
  movie/series/tv_vod) is retained as a diagnostic dump only and is not
  browseable or included in source search results.

  **Note:** This decision supersedes the earlier roadmap statement that
  "IPTV channels and unmatched VOD content are browsable through a
  dedicated IPTV section." See
  [livetv_research.md](../research/livetv_research.md) §7.4 for the
  resolution and rationale.
- **Capabilities: DIRECT_SEARCH, CHANNEL_LIST**
- **Playlist refresh** — playlists are fetched and cached with
  configurable refresh intervals, not re-fetched on every request

IPTV VOD sources that match a movie or episode appear alongside debrid
and Usenet sources on detail pages through the unified source search
pipeline. There is no dedicated IPTV VOD browse section — all content
discovery goes through a single search mechanism with results from all
configured providers. Live TV channels (not VOD) are browseable through
the Live TV page, which is part of the EPG/live TV milestone, not v0.0.2.

**Note:** EPG (electronic program guide) and live TV scheduling are NOT
in scope for v0.0.2. IPTV in this milestone means "access to streams" —
knowing what is currently airing on a live channel requires EPG data,
which is a separate capability.

#### Phase 2: Modular Source Resolvers (ADR-0012)

##### Source Resolver Module System

Source resolvers use the installable module architecture defined in
ADR-0012. The core provides:

- **SourceResolver interface** — abstract contract for modules that
  discover content hashes or availability information
- **Module loader** — discovers modules from configured directories,
  validates manifests, loads and registers resolver implementations
- **Module manifest schema** — identity, version, capabilities,
  configuration schema, compatibility declaration
- **Module lifecycle** — install, configure, enable/disable, test
  connection, uninstall

##### Hash Aggregator Module (Torrentio-Protocol)

The first source resolver module. Pre-indexed hash aggregation services
provide the highest value-to-effort ratio for source discovery. A single
HTTP GET returns dozens of info_hashes from 15+ torrent indexers.

- **Torrentio-protocol client** — queries services that implement the
  Stremio stream protocol:
  `GET {base_url}/stream/{type}/{imdb_id}.json`
- **Configurable base URL** — the user points at whichever service they
  prefer (Torrentio, TorrentsDB, MediaFusion, or a self-hosted
  instance)
- **Response parsing** — extracts info_hash, release name, file size,
  and seeder count from the JSON response (metadata is embedded in
  title strings using emoji delimiters)
- **No authentication required** — these are public APIs (some support
  optional tokens)
- **Capability: HASH_DISCOVERY** — this module type only finds hashes;
  it cannot check cache status or resolve to playable URLs

The hash aggregator is the source of hashes that debrid providers then
cache-check. Without it, debrid providers can only search their own
cloud storage. Phase 2 completes the full debrid pipeline.

This module is developed in-repo under a `scraper_modules/` directory but is
loaded through the module system, not hardcoded into the core.

#### Source Discovery Orchestration (spans both phases)

The source discovery service coordinates the full pipeline:

1. Receive content identity (IMDB ID, title, year, content type,
   optional season/episode)
2. Query all enabled source providers and source resolvers concurrently,
   dispatched by capability:
   - Source resolvers → info_hashes (Phase 2)
   - Easynews → direct sources
   - TorBox cloud → cloud files
   - IPTV → matched VOD/channel streams
3. Collect discovered hashes from step 2
4. Send hashes to all enabled debrid providers for cache check
   (concurrent, per provider)
5. Normalize all results into SourceResult entities
6. Apply filtering pipeline:
   a. Title validation (does the result match the request?)
   b. Quality detection (classify into quality tiers)
   c. Language filtering (optional)
   d. Undesirable release filtering (configurable keyword list)
7. Sort results:
   - Source type: direct > cached > cloud > uncached
   - Quality: 4K > 1080p > 720p > SD
   - Size (user preference)
   - Provider priority
8. Return sorted source list

The orchestration must not contain provider-specific branching. It
dispatches by declared capability, not by provider identity. The
orchestration layer treats bundled source providers and loaded source
resolver modules identically — both participate through their declared
capabilities.

In Phase 1 (before source resolvers exist), the orchestration works
with only bundled providers. TorBox's cloud search and Easynews's
direct search function independently. The hash aggregator slot is
simply empty — no hashes arrive for cache checking, so TorBox only
finds content already in the user's cloud library.

In Phase 2, the hash aggregator module feeds hashes into the debrid
cache-check pipeline, completing the full source discovery flow.

#### Source Resolution

Resolution converts a discovered source into a stream URL:

- **Direct sources** (Easynews, IPTV) — the stream URL is already
  present on the SourceResult. Resolution is a no-op.
- **Cached torrent sources** (TorBox) — call the debrid provider's
  resolve endpoint with the info_hash. The provider returns a temporary
  direct download URL.
- **Uncached torrent sources** — NOT resolvable in v0.0.2. These are
  displayed with an "uncached" label but cannot be selected. Uncached
  acquisition (submitting a magnet and waiting for download) is a future
  capability.

Resolution is triggered when a user selects a source from the list. The
resolved URL is displayed or stored — it is NOT passed to a player
because playback is not in scope.

Resolution is the bridge between source discovery and playback. Once
resolution works, the playback milestone has a clean handoff point: it
receives a stream URL and plays it.

#### Source Discovery API

New API endpoints for the source pipeline:

- `GET /api/sources/movie/{imdb_id}` — discover sources for a movie
- `GET /api/sources/series/{imdb_id}/{season}/{episode}` — discover
  sources for a TV episode
- `POST /api/sources/resolve` — resolve a specific source to a stream
  URL (takes provider_key + info_hash or source reference)
- IPTV-specific browsing endpoints (channels, categories) — scoped as
  needed during implementation

All endpoints require authentication.

#### Source Discovery UI

The content detail pages (movie, episode) gain a "Sources" section:

- A button or automatic trigger to discover sources
- Loading state while providers are queried
- Results displayed in a categorized list:
  - Direct sources (Easynews, IPTV) — marked as immediately playable
  - Cached sources (TorBox) — marked as available, resolvable
  - Cloud sources (TorBox) — marked as in user's library
  - Uncached sources — shown grayed out with "not cached" label
- Each result displays: release name, quality badge (4K/1080p/720p/SD),
  file size, provider name, source type indicator
- Selecting a cached or direct source triggers resolution and displays
  the resolved stream URL (proof the pipeline works)
- Provider settings page extended with source provider configuration
  and source resolver module management

The IPTV integration appears in the source search results on content
detail pages, not as a separate navigation section. Live TV channel
browsing is part of the EPG/live TV milestone, not v0.0.2.

### NOT Included

As scoped at the time. Playback, streaming/proxying, transcoding, remote
access, profiles, and progress tracking were later delivered — see
"Delivered Beyond the Original Milestone Plan". Submitting an uncached
torrent to TorBox is also implemented; monitoring downloads is not.

- No media playback (no video player, no audio player)
- No streaming or proxying of resolved URLs
- No transcoding
- No uncached torrent acquisition (submitting magnets, waiting for
  downloads)
- No EPG or live TV scheduling data
- No production remote access (iroh remains deferred)
- No multi-user profiles or permissions
- No watchlist, watch history, or progress tracking
- No automated media acquisition or monitoring
- No local file/media provider
- No additional debrid providers beyond TorBox (Real-Debrid, Premiumize,
  etc. follow the same interface later)
- No HTML scraping of torrent indexer sites (hash aggregators provide
  this data through stable APIs)
- No Cloudflare bypass infrastructure
- No source result caching (re-query on each request; add caching when
  performance requires it)

### Architecture at End of v0.0.2

```
                    Kondooit Server
                         │
              ┌──────────┴──────────┐
              │                     │
         Discovery              Users
              │                     │
     ┌────────┴────────┐          │
     │                 │          │
  Metadata          Sources       Auth
  Aggregation       Orchestration
  (priority,        (concurrent
   dedup)            discovery,
     │               cache check,
     │               filter, sort)
     │                 │
  MetadataProvider   SourceProvider          SourceResolver
     │               (bundled)               (modular, ADR-0012)
  ┌──┴──┐         ┌────┴──────┬───────┐          │
  │     │         │           │       │          │
 TMDB  TVDB    TorBox    Easynews   IPTV    HashAggregator
               (debrid)  (usenet)  (m3u/    (torrentio-
                                  xtream)    protocol)
```

Source providers live in `infrastructure/providers/` (bundled).
Source resolver modules live in `scraper_modules/` (loaded by module system).

Domain additions:

```
domain/
  content.py       (existing — content entities)
  source.py        (NEW — SourceResult, SourceQuality, SourceType)
  release_parser.py (NEW — release name classification)
```

### Success Criteria

A clean checkout should support everything from v0.0.1, plus:

**Phase 1 (source providers):**

```
Configure Source Providers
  ↓
  ├─ Add TorBox API key
  ├─ Add Easynews username + password
  └─ Add IPTV playlist URL or Xtream Codes credentials
      ↓
Navigate to Movie Detail Page
      ↓
Click "Find Sources"
      ↓
See Source Results:
  ├─ Easynews: "Movie.2022.1080p.WEB-DL.mkv" — Direct — 4.2 GB
  ├─ TorBox (cloud): "Movie.2022.2160p.BluRay.REMUX" — Cloud — 45 GB
  ├─ IPTV (VOD): "Movie Title" — Direct — Stream
      ↓
Select a Direct or Cloud Source
      ↓
Source Resolves to Stream URL
  (displayed — not played)
```

**Phase 2 (source resolvers):**

```
Install Hash Aggregator Module
  ↓
Configure base URL (Torrentio, MediaFusion, etc.)
      ↓
Navigate to Movie Detail Page
      ↓
Click "Find Sources"
      ↓
See Source Results (now includes cache-checked results):
  ├─ Easynews: "Movie.2022.1080p.WEB-DL.mkv" — Direct — 4.2 GB
  ├─ TorBox (cached): "Movie.2022.2160p.BluRay.REMUX" — Cached — 45 GB
  ├─ TorBox (uncached): "Movie.2022.720p.HDTV" — Not Cached — 1.1 GB
  ├─ IPTV (VOD): "Movie Title" — Direct — Stream
      ↓
Select a Cached Source
      ↓
Source Resolves to Stream URL
  (displayed — not played)
```

IPTV success criteria moved to v0.0.3. (The original "Navigate to IPTV
Section" flow is superseded: there is no IPTV section; live channels are
on the Live TV page and IPTV VOD appears only as source results.)

### What This Milestone Proves

- **Phase 1:** Bundled source providers work behind clean, capability-
  declared interfaces — the same pattern proven by metadata providers.
  Direct source providers (Easynews, IPTV) work end-to-end. TorBox
  cloud search functions independently.
- **Phase 2:** The module system (ADR-0012) works — source resolver
  modules are loaded from directories, registered through manifests,
  and participate in the orchestration pipeline alongside bundled
  providers. The full debrid pipeline works: hash discovery (resolver
  module) → cache check (bundled provider) → resolution.
- Release name parsing correctly classifies sources by quality.
- The source pipeline terminates at a resolved stream URL — a clean
  handoff point for the playback milestone.
- IPTV content is accessible alongside traditional media sources.
- The bundled-vs-modular distinction is architecturally clean — paid
  service API clients are bundled, gray-area hash aggregation is
  modular.

---

## Delivered Beyond the Original Milestone Plan

The following capabilities were implemented after v0.0.2 without a
dedicated milestone section. They are recorded here so the roadmap
matches the codebase.

- **Playback engine** — stream handles with direct and proxy modes
  (ADR-0014, ADR-0015); a web player page.
- **HLS remux and transcoding** (ADR-0016) — the server probes each
  source and chooses remux, remux with audio conversion to AAC, or full
  video transcode to H.264, based on what the browser supports. Seeking
  beyond the processed point restarts processing at the new position.
  Profiles can disallow transcoding.
- **Auto-play** — automatic source selection and next-episode playback.
- **Profiles** — multiple household profiles with a profile picker and
  per-profile playback preferences (direct play, remux, transcode,
  auto-play). Permissions and parental controls are not implemented.
- **Watch progress** — progress reporting, continue watching, and
  watched/unwatched state per profile.
- **Remote access** (ADR-0017) — iroh sidecar on the server, browser
  runtime, connection link, and tunnel connection page.
- **Debrid add** — submitting an uncached torrent to TorBox. Monitoring
  and completion handling are not implemented.

---

## v0.0.3 — Live TV & IPTV

**Status: Planned — not yet authorized for implementation**

The full plan is in [livetv_research.md](../research/livetv_research.md)
(§5 and the implementation sequence in §6). Supporting ADRs listed in
its §8 must be written as Proposed before implementation begins.

### Included

- IPTV providers: M3U playlists and Xtream Codes accounts, with
  scheduled refresh and removal of channels a provider drops
- Channels and channel groups, with user overrides (name, number,
  group, guide assignment) and provider-first channel numbering
- EPG: XMLTV sources, automatic channel matching (exact and fuzzy),
  manual assignment
- Live TV page with a time-based guide grid (default) and a channel
  grid; selecting a channel or airing programme starts playback
- Live playback in the existing player: info overlay, channel up/down,
  mini-guide; direct delivery when the device can play the stream,
  otherwise the existing remux/transcode path, with automatic
  escalation when a stream fails to play
- User-set per-provider connection limits, enforced before playback
- User-Agent settings: household, profile, provider, and channel
- IPTV VOD as source results on movie and episode pages, with stale
  cleanup, provider priority, quality detection, and title filters

### NOT Included

- Sharing one provider connection among several viewers
- Automatic preemption of active streams
- DVR/recording, timeshift, catch-up, reminders
- A dedicated IPTV VOD browse section
- HDHomeRun / Xtream output, .strm files
- Hardware-accelerated transcoding
- Native clients (ADR-0018 remains Proposed)

---

## Subsequent Milestones

Later milestones will be defined as the project progresses. Anticipated
areas (not yet scoped or prioritized):

- **Android / Fire TV client** — per ADR-0018 (Proposed)
- **Acquisition** — monitoring debrid download progress after an
  uncached torrent is submitted, completed downloads becoming cached
  sources (per ADR-0004)
- **Additional debrid providers** — Real-Debrid, Premiumize, AllDebrid,
  OffCloud following the SourceProvider interface established in v0.0.2
- **Local media provider** — local files as sources (per ADR-0004)
- **Permissions and parental controls** — restrictions per profile
  (profiles themselves are delivered)
- **Additional hash sources** — self-hosted hash databases (Bitmagnet,
  Zilean), additional Torrentio-protocol services

These will be scoped into specific versions as the project advances. Do
not begin implementing any of these until the roadmap assigns them to a
milestone and the user instructs implementation to begin.

---

## Rules

1. **Implement only the current milestone** unless the user explicitly
   expands scope.
2. **Respect the architecture.** The roadmap constrains what to build,
   not how. Existing principles and ADRs govern the how.
3. **Do not pre-build future milestones.** Architectural preparations
   (clean interfaces, extensible abstractions) are acceptable where the
   architecture demands them. Implementing future functionality early is
   not.
4. **Each milestone should be usable.** A milestone should produce
   something a user can run and interact with, not just scaffolding.
5. **Update this document when milestones are defined or completed.**
   When a milestone is reached, mark it complete and ensure the next
   milestone is scoped.
