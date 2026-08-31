# Source Provider Architecture — Capability Analysis

**Date:** 2026-08-22
**Status:** Research / planning — no implementation decisions finalized
**Prerequisite reading:** ADR-0002, ADR-0010, ADR-0011, umbrella.md sections 15-16

---

## 1. What Is a "Source Provider" in Kondooit?

A **source provider** answers the question: "Given a piece of identified content, where can it be played from?"

This is fundamentally different from a **metadata provider** (TMDB, TVDB), which answers: "What does this content look like? What are its details?"

The existing `MetadataProvider` interface in `provider_ports.py` is explicitly scoped to metadata only. Source providers require a completely separate interface hierarchy because they have different capabilities, different authentication models, different data contracts, and different orchestration patterns.

---

## 2. The Three Distinct Capabilities

Research (umbrella.md sections 5, 7, 9, 15) reveals three capabilities that are conceptually separate even when a single service provides more than one:

### Capability A: Source Discovery (Hash/Link Discovery)

**Question answered:** "What sources exist for this content?"

**Input:** Content identity (IMDB ID, title, year, season/episode)
**Output:** A list of potential sources (info_hashes, direct URLs, cloud file references)

**Who provides this:**
- Pre-indexed hash aggregators (Torrentio-protocol services)
- Self-hosted hash databases (Bitmagnet, Zilean)
- Direct search providers (Easynews)
- Debrid cloud search (TorBox cloud, RealDebrid cloud)

### Capability B: Cache Verification

**Question answered:** "Which of these hashes are instantly available (cached) on this debrid service?"

**Input:** A list of info_hashes
**Output:** Which hashes are cached (instantly resolvable) on the service

**Who provides this:**
- TorBox (`POST /torrents/checkcached`)
- Real-Debrid (`GET /torrents/instantAvailability/{hashes}`)
- Premiumize, AllDebrid, OffCloud (similar endpoints)

### Capability C: Source Resolution

**Question answered:** "Give me a playable URL for this cached source."

**Input:** An info_hash or file reference that is known to be cached/available
**Output:** A direct HTTP URL that can be streamed

**Who provides this:**
- TorBox (`resolve_magnet` → direct download URL)
- Real-Debrid (`unrestrict_link` → direct download URL)
- Easynews (search results ARE playable URLs — no resolution step needed)

---

## 3. How TorBox and Easynews Map to These Capabilities

### TorBox

TorBox is a **debrid service** — it caches torrents and provides direct download links.

| Capability | TorBox Support | How |
|-----------|---------------|-----|
| Source Discovery (cloud) | Yes | Search user's existing TorBox cloud for content |
| Source Discovery (hash) | No | TorBox does NOT search for new hashes — it needs them FROM somewhere else |
| Cache Verification | Yes | Batch check if hashes are cached on TorBox's servers |
| Source Resolution | Yes | Convert a cached hash into a playable direct URL |
| Source Acquisition | Yes (future) | Submit uncached magnets and wait for download |

**Authentication:** Bearer token (API key provided by user)

**Critical insight:** TorBox alone cannot find NEW sources. It can only:
1. Check if hashes (discovered elsewhere) are in its cache
2. Search what the user already has in their TorBox cloud
3. Resolve cached hashes to playable URLs

To get the full pipeline working with TorBox, you also need a **hash source** (Capability A).

### Easynews

Easynews is a **direct source provider** — it searches its own Usenet index and returns immediately playable results.

| Capability | Easynews Support | How |
|-----------|-----------------|-----|
| Source Discovery | Yes | Keyword search against Easynews's Solr index |
| Cache Verification | N/A | Results are always available (it's a paid index, not a cache) |
| Source Resolution | N/A | Search results include the playable URL directly |
| Direct Stream | Yes | URLs are HTTP Basic Auth-protected direct downloads |

**Authentication:** HTTP Basic Auth (username + password)

**Critical insight:** Easynews is self-contained. It discovers AND serves content in a single step. No cache check needed, no resolution step needed. Results come back with a direct download URL embedded.

---

## 4. The Minimum Viable Source Pipeline

For a user to click a movie/episode and see "playable sources," the minimum components are:

### Option A: Easynews Only (simplest)

```
User clicks movie/episode
  → Search Easynews with title + year (or title + S##E##)
  → Filter/validate results (title match, quality detection)
  → Display directly playable sources
```

This works end-to-end with a single provider. No hash aggregator needed.

### Option B: TorBox Only (limited)

```
User clicks movie/episode
  → Search TorBox cloud for matching content
  → Display cloud files as playable sources (if any exist)
```

This only shows content the user ALREADY has in their TorBox cloud. It doesn't discover new sources. Useful but limited.

### Option C: TorBox + Hash Aggregator (full pipeline)

```
User clicks movie/episode
  → Query hash aggregator (Torrentio-protocol) for info_hashes
  → Send hashes to TorBox cache check
  → Mark cached vs. uncached
  → Also search TorBox cloud for existing files
  → Display:
    - TorBox cloud files (instantly playable)
    - Cached torrents (resolvable to playable URL)
    - (Optional) Uncached torrents (would need download time)
```

This is the full experience but requires a hash source.

### Option D: TorBox + Easynews + Hash Aggregator (complete)

Combines B and C — the user sees both Easynews direct results AND TorBox-cached torrent results.

---

## 5. The Hash Aggregator Question

TorBox needs hashes from somewhere. The three options:

### 5a. Built-in Torrentio-protocol client

A simple HTTP client that calls `GET https://torrentio.strem.fun/stream/movie/{imdb_id}.json` and parses the response. This is:
- Trivial to implement (one GET request, JSON parse)
- Stable (the protocol is standardized across 3+ services)
- High value (returns results from 15+ indexers)
- No authentication required (public endpoints)
- Configurable (user could point at Torrentio, TorrentsDB, MediaFusion, or a self-hosted instance)

### 5b. User-hosted hash database (Bitmagnet, Zilean)

Similar API pattern but user provides the URL of their self-hosted instance. Results have less metadata (may lack seeder counts).

### 5c. Direct scraping of torrent indexer sites

High complexity, fragile, Cloudflare issues. NOT recommended for initial implementation.

**Recommendation:** Start with 5a (Torrentio-protocol). It's the highest value-to-effort ratio by far. One HTTP GET replaces dozens of fragile HTML scrapers.

---

## 6. Where Source Providers Fit in the Existing Architecture

The existing architecture has:
- `MetadataProvider` (ABC in `application/provider_ports.py`) — for TMDB/TVDB
- `ProviderConfig` — settings with api_key, status, priority
- `ProviderRegistry` — maps provider keys to implementations
- `DiscoveryService` — orchestrates metadata discovery with priority fallback

Source providers need **parallel but separate** infrastructure:

```
Existing:
  MetadataProvider (interface)
    → TMDB, TVDB (implementations)
    → DiscoveryService (orchestrator)

New (source):
  SourceProvider (interface) — different capability declarations
    → EasynewsProvider (discovery + direct stream)
    → TorBoxProvider (cloud search + cache check + resolution)
    → HashAggregatorProvider (hash discovery only)
    → SourceDiscoveryService (orchestrator for the source pipeline)
```

They share the same `provider_settings` table for credentials and enable/disable, but the interfaces and orchestration are distinct.

---

## 7. Capability Declaration for Source Providers

Following ADR-0010's pattern, source providers should declare capabilities:

```
SourceCapability enum:
  HASH_DISCOVERY     — Can search for info_hashes given content identity
  DIRECT_SEARCH      — Can search and return directly playable results
  CLOUD_SEARCH       — Can search user's existing cloud/library
  CACHE_CHECK        — Can batch-check hash availability
  RESOLVE            — Can convert cached hash to playable URL
  ACQUIRE            — Can initiate download of uncached content (future)
```

Provider capability profiles:

| Provider | HASH_DISCOVERY | DIRECT_SEARCH | CLOUD_SEARCH | CACHE_CHECK | RESOLVE | ACQUIRE |
|----------|---------------|---------------|-------------|-------------|---------|---------|
| Torrentio-protocol | Yes | - | - | - | - | - |
| Easynews | - | Yes | - | - | - | - |
| TorBox | - | - | Yes | Yes | Yes | (future) |

---

## 8. Authentication Models

| Provider | Auth Type | Credentials Needed | Notes |
|----------|----------|-------------------|-------|
| Torrentio-protocol | None | None (or optional addon token) | Public API |
| Easynews | HTTP Basic | username + password | Sent on every request |
| TorBox | Bearer token | API key | Sent as Authorization header |

The existing `provider_settings.api_key` field works for TorBox's API key but doesn't cleanly accommodate Easynews's username+password pair. Options:
- Store as JSON in api_key field: `{"username": "...", "password": "..."}`
- Add a `credentials` JSONB column
- Add separate `username` / `password` columns

The JSONB approach is most flexible without schema proliferation.

---

## 9. The Source Result Entity

All source providers return results that must be normalized into a single canonical format for the UI:

```
SourceResult:
  id: str                    — unique identifier for this result
  provider_key: str          — which provider found this (torbox, easynews, torrentio)
  content_type: str          — movie, episode
  title: str                 — release/file name
  quality: str               — 4K, 1080p, 720p, SD
  size_bytes: int | None     — file size
  source_type: str           — direct, cached_torrent, uncached_torrent, cloud
  
  # For direct sources (Easynews)
  stream_url: str | None     — directly playable URL
  
  # For torrent sources (TorBox)
  info_hash: str | None      — torrent info_hash
  seeders: int | None        — seed count (if known)
  
  # Display metadata
  codec: str | None          — x264, x265, etc.
  audio: str | None          — DD5.1, DTS, etc.
  hdr: str | None            — HDR10, DV, etc.
  source_tag: str | None     — WEB-DL, BluRay, etc.
```

This is a domain entity — it represents a playable source independently of where it came from.

---

## 10. What "Resolution" Means (Pre-Playback)

When the user eventually clicks a source to play:

- **Direct sources** (Easynews): `stream_url` is already present — pass it to the player
- **Cached torrent sources** (TorBox): call TorBox's resolve API to get a temporary direct URL, then pass to player
- **Uncached torrent sources** (future): submit to TorBox, poll until cached, then resolve

Resolution is the step between "source selected" and "player receives URL." It's the gateway to playback but doesn't itself involve playback. Implementing resolution without playback is possible and useful — it proves the pipeline works end-to-end.

---

## 11. Relationship to Existing Provider Infrastructure

The existing system already has:
- Provider settings storage (database table with key, api_key, status, priority)
- Provider enable/disable and priority (ADR-0011)
- Provider capability declaration pattern (ADR-0010)
- Provider registry pattern (maps keys to implementations)
- Provider configuration API endpoints

Source providers should reuse this infrastructure rather than creating parallel systems. The key extension points are:
1. New capability enum values (source-specific capabilities)
2. New provider implementations (TorBox, Easynews, hash aggregator)
3. New orchestration service (SourceDiscoveryService)
4. New API endpoints (source discovery on content detail pages)
5. New UI components (source list on movie/episode pages)

---

## 12. Open Questions

1. **Should hash aggregator configuration be per-user or system-wide?** TorBox/Easynews are per-user (personal credentials). Torrentio is a public API — is it system config or user choice?

2. **Should source results be cached?** Umbrella caches for 6 hours. If a user checks the same movie twice in an hour, should we re-query or serve cached results?

3. **How does content identity flow from metadata to source?** The user is on a movie detail page (from TMDB metadata). The source pipeline needs the IMDB ID. TMDB provides IMDB IDs — but does our current detail page carry that information?

4. **Should resolution happen eagerly or lazily?** Show the source list with cache status immediately, resolve to playable URL only when user selects a source? (Yes — this is what Umbrella does and it's correct.)

5. **How are provider errors surfaced?** If TorBox is misconfigured, does the source list show "TorBox: authentication failed" or just silently omit its results?
