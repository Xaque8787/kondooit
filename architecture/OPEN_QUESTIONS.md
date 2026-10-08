# Open Architectural Questions

Unresolved questions that must be answered before the corresponding parts of the system can be implemented. When a question is resolved, record the decision as an ADR in `../decisions/` and remove it from this list.

## Core / provider boundary

- What should the exact core/provider boundary be? (Resolved in part by ADR-0002, ADR-0003, ADR-0006; the precise interface shapes remain open.)
- What should be native functionality versus an adapter around existing libraries?
- Should the primary browsing experience be provider-driven or local-catalog-driven? → Resolved by [ADR-0009](../decisions/ADR-0009-provider-driven-content-discovery.md).
- How should providers declare which discovery capabilities they support? → Resolved by [ADR-0010](../decisions/ADR-0010-provider-capability-declaration.md).

## Content identity

- When does a discovered item require a persistent Kondooit-owned identity (e.g., a UUID) versus a lightweight provider/content-type/external-ID reference? The vision realignment clarifies that identity should be lightweight and lazy — a provider-independent identity should be introduced only where the architecture actually requires it (e.g., user state referencing content independently of which provider discovered it). This remains an open question for implementation; ADR-0003 is clarified but does not fully resolve the boundary.

## Technology baseline

- What technology stack should Kondooit use? → Resolved by [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md). Python/Litestar server, React/TypeScript client, PostgreSQL, SQLAlchemy, Pydantic, iroh, FFmpeg, Docker.

## Source discovery

- How should source discovery be represented in the provider interface?
- How should candidate sources be ranked and resolved?
- Which existing projects contain reusable implementation code versus architectural workarounds?

## Playback

- How should the two routing modes (direct vs. server-proxy) be modeled in the client-facing protocol and API?
- What is the session lifecycle for proxied playback?
- How is transcoding invoked by the playback engine, and what does the transcoding provider interface look like? → Partially resolved: [ADR-0014](../decisions/ADR-0014-direct-delivery-default-with-proxy-remux-transcode-fallback.md) makes transcoding an invokable step in the direct → remux → transcode chain, and [ADR-0016](../decisions/ADR-0016-hls-remux-for-web-playback.md) defines the HLS path that carries it. Basic FFmpeg remux, audio conversion, and H.264 transcoding are implemented. Still open: whether transcoding becomes a pluggable provider interface (e.g. for hardware acceleration).

## Content model

- How should seasons/episodes/collections map across providers that do not natively model them?
- How are live channels, EPG programs, and schedules modeled concretely, and how do they relate to metadata identity? → Resolved (Proposed) by [livetv_research.md](../research/livetv_research.md) §7.2. Recorded as [ADR-0021](../decisions/ADR-0021-epg-and-channel-domain-model.md) (Proposed): "EPG and channel domain model" — Channel, ChannelGroup, ChannelOverride, EPGSource, EPGChannel, Program as domain entities. ChannelOverride pattern for user customization preservation. Provider-first channel numbering with next-available fallback.

## IPTV / Live TV

- Should IPTV providers be a new provider type or extend the existing SourceProvider abstraction? → Resolved (Proposed) by [livetv_research.md](../research/livetv_research.md) §7.1. IPTV is a separate capability with its own interface (IPTVProviderPort), not an extension of SourceProvider. Recorded as [ADR-0020](../decisions/ADR-0020-iptv-provider-architecture.md) (Proposed).
- Should EPG matching use rapidfuzz or a simpler string similarity? → Resolved by [livetv_research.md](../research/livetv_research.md) §7.2. Use rapidfuzz.
- How should the scheduler be initialized and managed? → Resolved by [livetv_research.md](../research/livetv_research.md) §7.3. APScheduler integrated into Litestar startup/shutdown lifecycle. Follow-up: investigate whether cron-style or timezone-aware scheduling is needed beyond simple hour intervals.
- Should VOD content from IPTV providers appear in the main discovery catalog or only as source results? → Resolved by [livetv_research.md](../research/livetv_research.md) §7.4. IPTV VOD is source-only — no dedicated browse section. All content discovery goes through the single unified source search pipeline. The v0.0.2 roadmap statement about a dedicated IPTV section is superseded by this decision and should be updated. Recorded as [ADR-0022](../decisions/ADR-0022-iptv-vod-as-source-candidates-only.md) (Proposed).
- Should channel numbers be auto-assigned or manually set on first import? → Resolved by [livetv_research.md](../research/livetv_research.md) §7.5. Provider-first numbering with next-available fallback, overridable via ChannelOverride.

## Acquisition

- How should acquisition differ from playback in the provider interface?
- What is the lifecycle of an acquisition job, and how does it produce a local source?

## Security and multi-tenancy

- How should provider credentials be isolated and stored? (ADR-0005 establishes server-level credentials; storage mechanics remain open.)
- How are per-user permissions modeled and enforced concretely?

## Protocol and connectivity

- What does the Kondooit application protocol look like concretely? (ADR-0007 establishes transport-independence; the protocol shape remains open.)
- How should multiple networking providers be represented behind one interface?

## Native clients

- How should native Android/Fire TV clients be built, and how do they share the iroh connection logic with the browser runtime? → Resolved (Proposed) by [ADR-0018](../decisions/ADR-0018-android-fire-tv-client-architecture.md). Kotlin UI with shared Rust core via uniFFI. Not yet authorized for implementation.

## Ecosystem analysis

- Which existing projects contain reusable implementation code versus architectural workarounds?
- Which portions of existing projects should be rewritten because the new architecture eliminates their original constraints?

## Status

Questions resolved by ADRs to date:

- Live TV in the content model → [ADR-0001](../decisions/ADR-0001-live-tv-first-class-content-type.md)
- Provider vs. source definitions → [ADR-0002](../decisions/ADR-0002-provider-vs-source-distinction.md)
- Canonical content identity ownership → [ADR-0003](../decisions/ADR-0003-core-owns-canonical-identity.md)
- Downloads and local sources → [ADR-0004](../decisions/ADR-0004-downloads-create-local-sources.md)
- Tenancy model → [ADR-0005](../decisions/ADR-0005-single-server-household-model.md)
- Playback orchestration, proxy, transcoding → [ADR-0006](../decisions/ADR-0006-playback-orchestration-and-transport.md) (superseded by [ADR-0014](../decisions/ADR-0014-direct-delivery-default-with-proxy-remux-transcode-fallback.md))
- iroh default and transport independence → [ADR-0007](../decisions/ADR-0007-iroh-default-transport-independent-protocol.md)
- Technology baseline and implementation-layer boundaries → [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md)

- Provider-driven content discovery → [ADR-0009](../decisions/ADR-0009-provider-driven-content-discovery.md)
- Provider capability declaration → [ADR-0010](../decisions/ADR-0010-provider-capability-declaration.md)

The remaining questions above are **open**. Do not begin implementation that depends on any of them until the relevant question is resolved and recorded as an ADR.

Questions resolved by research (ADRs to be created as Proposed):

- IPTV provider architecture (separate capability, not SourceProvider) → [livetv_research.md](../research/livetv_research.md) §7.1
- EPG matching with rapidfuzz → [livetv_research.md](../research/livetv_research.md) §7.2
- Scheduler integrated into Litestar lifecycle → [livetv_research.md](../research/livetv_research.md) §7.3
- IPTV VOD as source-only, no dedicated browse section → [livetv_research.md](../research/livetv_research.md) §7.4
- Channel numbering: provider-first, next-available fallback → [livetv_research.md](../research/livetv_research.md) §7.5
