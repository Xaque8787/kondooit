# ADR-0021: EPG and channel domain model

- **Status:** Proposed
- **Date:** 2026-10-08
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How are live channels, EPG programs, and schedules modeled concretely, and how do they relate to metadata identity?" (OPEN_QUESTIONS.md, Content model); "Should channel numbers be auto-assigned or manually set on first import?" (OPEN_QUESTIONS.md, IPTV / Live TV; research: [livetv_research.md](../research/livetv_research.md) §5.3, §7.5)

## Context

ADR-0001 makes Live TV a first-class content type (Channel and Program/Event) but does not define the concrete model. Research into Dispatcharr (livetv_research.md §2.2–§2.4) found a proven three-level guide model: guide source, guide channel, then programme. It also found a separate override record that keeps user customisations from being overwritten when the provider is refreshed.

## Decision

### Channel domain

- **ChannelGroup:** a named group, either supplied by a provider (category or `group-title`) or created by the user.
- **Channel:** provider-supplied data only. Fields: name, channel number, group, logo, `tvg_id`, stream URL, optional provider-supplied user agent (for example from `#EXTVLCOPT:http-user-agent`), catch-up flags, matched guide channel, and status. Status is one of `enabled`, `disabled`, or `hidden`. A hidden channel is kept and still updated by refreshes, but is not shown to clients.
- **ChannelOverride:** one-to-one with Channel, all fields nullable. Covers name, channel number, group, logo, guide channel, and user agent. Provider refresh writes only to Channel; user edits write only to ChannelOverride. The effective value of each field is the override if set, otherwise the channel value.
- **Stable identity:** a channel keeps its identity across refreshes through a deterministic key derived from provider-scoped data. For Xtream Codes the key uses `stream_id`, so changing credentials or the URL does not break it. A live channel has exactly one stream URL; multi-stream failover is out of scope.
- **Numbering:** on first import, use the provider's number (`tvg-chno` from M3U, `num` from Xtream Codes). Channels without one get the next available number. Numbers are decimal so sub-channels such as 2.1 work. Users change numbers through ChannelOverride.

### Guide (EPG) domain

- **EPGSource:** an XMLTV source given as a URL or a file path. It has a refresh interval in hours, a priority (higher wins when several sources match the same channel), active flag, and status. `source_type` is a string; only `xmltv` is implemented.
- **EPGChannel:** an XMLTV `<channel>` entry (`tvg_id`, display name, icon), unique per source.
- **Program:** an XMLTV `<programme>` entry: start, end, title, subtitle, description, and optional season and episode numbers.

### Matching channels to guide channels

There are two tiers. First an exact match on `tvg_id`, then a fuzzy name match on normalised names using rapidfuzz (livetv_research.md §7.2). Normalisation removes bracketed and parenthesised text (keeping upper-case call signs), non-word characters, and filler words such as hd, tv, and channel. Bulk matching auto-accepts at a score of 85 or more. Single-channel matching, triggered by the user, accepts at 80. Lower scores down to a floor are kept as candidates without being accepted. A guide channel assigned by hand through ChannelOverride always wins over an automatic match.

## Rationale

- Separating provider data from user overrides is the only way to keep refreshes from undoing user edits; Dispatcharr's experience confirms this.
- The three-level guide model reflects the XMLTV format directly and is sufficient for the guide grid.
- Exact matching then fuzzy matching covers most channels without the dependency and model download that machine-learning matching needs.

## Alternatives considered

- **Store user edits directly on Channel.** Rejected: provider refresh would overwrite them.
- **Model channels as a series and programmes as episodes.** Rejected by ADR-0001.
- **Machine-learning validation tier (Dispatcharr's sentence-transformers).** Rejected for now: a heavy dependency for marginal gain.
- **Purely manual or purely sequential numbering.** Rejected: provider numbers are usually meaningful, and filling gaps with next-available numbers is predictable.

## Consequences

- New tables: channel groups, channels (including cached stream probe fields, see ADR-0023), channel overrides, EPG sources, EPG channels, programmes. All are created from models per ADR-0019.
- Every API that lists channels must return effective (override-resolved) values.
- The XMLTV parser must stream large files and handle HTML named entities.
- A new dependency on rapidfuzz.

## Relationship to other ADRs

- **ADR-0001:** concrete model for the Live branch of the content hierarchy.
- **ADR-0020:** channels and groups are produced by IPTV provider ingestion.
- **ADR-0023:** playback uses the effective channel values and the cached probe fields.
