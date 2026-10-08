# ADR-0020: IPTV providers are a distinct capability, not a SourceProvider

- **Status:** Proposed
- **Date:** 2026-10-08
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "Should IPTV providers be a new provider type or extend the existing SourceProvider abstraction?" (OPEN_QUESTIONS.md, IPTV / Live TV; research: [livetv_research.md](../research/livetv_research.md) §7.1)

## Context

v0.0.2 introduced `SourceProvider` for services such as TorBox and Easynews. These services answer a question about one title: given a movie or episode, which sources exist? IPTV providers work differently. An M3U playlist or an Xtream Codes account delivers a whole catalog: live channels, categories, VOD movies, and series. That catalog is fetched in bulk on a schedule and stored locally. It is not queried per title.

Research into Dispatcharr and Vodstrm (livetv_research.md §2–§3) confirmed two ingestion protocols with different data shapes: M3U playlists (`#EXTINF` lines) and the Xtream Codes Player API (separate live, VOD, and series endpoints).

Principle 5 of the project guidance warns against a universal "Provider" abstraction. Different provider types are different capabilities.

## Decision

IPTV is a separate provider capability with its own application-layer port, `IPTVProviderPort`:

- `fetch_channels()`: live channels and channel groups for one refresh batch.
- `fetch_vod_content()`: VOD movies, series episodes, air-date content, and unsorted entries for one refresh batch.
- `test_connection()`: verify that the configured credentials and URL work.

M3U and Xtream Codes are the two infrastructure implementations of this port. Each configured IPTV provider instance stores its own settings: type, URL or credentials, refresh interval, priority, optional user agent, optional connection limit, and `force_vod` for M3U.

The application layer owns orchestration: fetch, classify, persist with a batch id, then clean up stale data. A scheduler in the infrastructure layer runs this at each provider's refresh interval and never runs two refreshes of the same provider at once. Per livetv_research.md §7.3, the scheduler is APScheduler started and stopped with the Litestar lifecycle.

IPTV VOD reaches source search through a thin adapter. The adapter queries the locally stored VOD library and returns `SourceResult` entries (see ADR-0022). This adapter is the only point where IPTV meets the source discovery pipeline.

## Rationale

- Bulk catalog ingestion and per-title source search are different capabilities with different lifecycles. A single interface would force one of them into an unnatural shape.
- Keeping M3U and Xtream Codes behind one port lets the application treat them uniformly. Each protocol's quirks stay in its own adapter.
- A local library makes VOD source lookups fast and offline-safe, and avoids per-search calls to IPTV providers.

## Alternatives considered

- **Extend `SourceProvider` with IPTV methods.** Rejected: every source provider would gain channel and catalog methods that only IPTV uses, and search-by-title does not fit how IPTV providers expose content.
- **Query the IPTV provider live during source search.** Rejected: Xtream Codes has no reliable title search, M3U has none at all, and this would add provider load and latency to every source search.
- **Generic "Provider" base class shared by metadata, source, and IPTV providers.** Rejected per principle 5 (no universal provider abstraction).

## Consequences

- New port, two adapters (M3U parser, Xtream client), an ingestion service, and a scheduler.
- New persisted tables for IPTV provider configuration and ingested data (ADR-0021, ADR-0022), created from models per ADR-0019.
- A new background dependency (APScheduler) in the server.
- Provider priority for IPTV follows ADR-0011.
- Error messages from IPTV adapters must never expose credentials.

## Relationship to other ADRs

- **ADR-0001:** Live TV is a first-class content type; this ADR defines where its data comes from.
- **ADR-0002:** IPTV providers are providers; the channels and VOD streams they supply are sources.
- **ADR-0011:** Priority and fallback apply to IPTV providers.
- **ADR-0021, ADR-0022, ADR-0023:** channel/EPG model, VOD handling, and live playback build on this port.
