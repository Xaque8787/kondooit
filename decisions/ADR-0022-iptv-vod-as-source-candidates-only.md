# ADR-0022: IPTV VOD is source candidates only

- **Status:** Proposed
- **Date:** 2026-10-08
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "Should VOD content from IPTV providers appear in the main discovery catalog or only as source results?" (OPEN_QUESTIONS.md, IPTV / Live TV; research: [livetv_research.md](../research/livetv_research.md) §5.3, §5.8, §5.10, §7.4)

## Context

IPTV providers commonly offer large VOD libraries of movies and series alongside live channels. Vodstrm (livetv_research.md §3) ingests these, classifies each entry, and writes `.strm` files for external media servers. Kondooit is itself the media server and has a single unified source search pipeline (v0.0.2). The project needs to decide whether IPTV VOD becomes its own browsable catalog or another contributor of sources.

## Decision

### Source-only

IPTV VOD content appears only as source results on existing movie and episode pages, alongside debrid, Usenet, and module results. There is no separate IPTV VOD browse section. Entries that cannot be classified (`unsorted`) are kept for diagnostics only: they cannot be browsed and are never returned in source search.

### Model

- **VODEntry:** what the content is. Fields: type (`movie`, `series`, `tv_vod`, `unsorted`), `cleaned_title`, year, season, episode, air date, cover art, and `content_hash`. The hash is SHA-256 of type, lower-cased `cleaned_title`, season, episode, year, and air date. It deduplicates the same content across providers.
- **VODStream:** where a VODEntry comes from. Fields: provider, stream URL, raw provider attributes, raw title, quality label, `batch_id`, and last seen.
- Stream URLs are stored in the database and served through Kondooit's API. No `.strm` files are generated.

### Title derivation

`cleaned_title` comes from a default parser that mimics Vodstrm's (livetv_research.md §5.10.4). The parser classifies each name in this order: live, then series (SxxExx or NxN), then air date, then year (last occurrence), then unsorted. It derives the title by cutting the name off at the token that classified it, then trimming trailing separators. Trailing quality, codec, and release-group text is dropped by the cut; there is no token-stripping pass. For Xtream Codes, the endpoint determines the type: series titles come from the series catalog name, and movie titles are cut at the year.

Optional per-provider remove or replace terms set by the user are a separate, later feature that runs after parsing. They affect display and matching only and never change `content_hash`.

### Lifecycle and ranking

- Each refresh tags streams with a new `batch_id`. Afterwards, streams from that provider carrying an older batch id are deleted, then entries with no remaining streams are deleted.
- Deleting a provider removes its streams, then any orphaned entries. Deactivating a provider keeps its streams but excludes them from search.
- Every matching stream from every active provider is returned. Results are sorted by provider priority (ADR-0011), then quality label, then most recently seen. No single winner is selected.

## Rationale

- One search pipeline gives users one consistent way to find and play content; a separate IPTV catalog would fragment discovery.
- Separating what content is (entry) from where it comes from (stream) matches ADR-0002 and makes deduplication across providers straightforward.
- Vodstrm's cut-at-token parser produces clean titles for most provider naming without configuration, and its output alone is stable enough to key identity on.
- `.strm` files exist to feed external media servers; Kondooit does not need them.

## Alternatives considered

- **Dedicated IPTV VOD browse section.** Rejected: fragments discovery. This supersedes the earlier v0.0.2 roadmap wording.
- **Single winner per entry (Vodstrm's `.strm` approach).** Rejected: Kondooit can present every option ranked.
- **Regex token-stripping before classification.** Rejected: an earlier draft proposed this, but it misread Vodstrm. Cutting at the classifying token already removes trailing noise, and stripping first risks altering titles and destabilising identity.
- **Grace period before deleting stale content.** Rejected: refresh intervals are short, and content that reappears is ingested again.

## Consequences

- New tables for VOD entries and VOD streams, created from models per ADR-0019. A filters table is added only if and when user title filters are implemented.
- The source discovery pipeline gains an IPTV VOD adapter that returns `SourceResult` entries with source type `IPTV_STREAM`.
- Matching `cleaned_title` to catalog content applies normalisation at comparison time; the stored title is not changed.

## Relationship to other ADRs

- **ADR-0002:** VODEntry and VODStream follow the provider/source distinction.
- **ADR-0003:** VODEntry is IPTV evidence, not canonical identity; canonical movies and episodes remain owned by the core and are matched by title.
- **ADR-0011:** provider priority orders results.
- **ADR-0020:** VOD content is produced by IPTV provider ingestion.
