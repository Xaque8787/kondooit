# ADR-0023: Live TV playback, failure-driven fallback, and stream handle headers

- **Status:** Proposed
- **Date:** 2026-10-08
- **Supersedes:** ADR-0015 (on acceptance)
- **Superseded by:** —
- **Resolves:** "How are live channels delivered to devices that cannot play the provider's format, and how do clients learn a channel's required User-Agent?" (research: [livetv_research.md](../research/livetv_research.md) §5.11, §8 item 4)

## Context

ADR-0014 sets direct delivery as the default, with remux and transcode as fallbacks. ADR-0015 defines stream handles with `direct` and `proxy` modes. ADR-0016 defines HLS remux for web playback. The on-demand HLS path built under them already probes the source and chooses between remuxing, remuxing video while converting audio to AAC, or fully transcoding video to H.264.

Live IPTV adds four problems:

- Streams are usually MPEG-TS, sometimes with MPEG-2, HEVC, AC-3, or MP2 codecs that browsers cannot play.
- Most providers send no CORS headers, and many serve plain HTTP.
- Some providers serve only requests that identify as an approved player through the User-Agent.
- Subscriptions limit how many streams can run at once.

ADR-0015's direct-mode handle has no field for request headers, so a native client cannot be told the User-Agent a channel requires.

## Decision

### Delivery tiers

ADR-0014's order is applied per viewer, with the transcode tier split so only the incompatible stream is converted:

1. **Direct:** the client plays the provider URL.
2. **Remux:** FFmpeg copies audio and video into HLS (ADR-0016).
3. **Audio convert:** video is copied and audio is converted to AAC.
4. **Full transcode:** video is converted to H.264 and audio to AAC.

Tiers 2–4 are proxy-mode handles, with `processing` set to `remux` or `transcode` and a `transcode_profile` describing what is converted. This reuses the existing HLS session path; live adds the upstream User-Agent, reconnect on dropped HTTP input, and a sliding-window playlist that deletes old segments.

### Choosing the starting tier

- If force proxy is on, start at tier 2 or higher.
- If a User-Agent applies and the client cannot send custom headers (all browsers), start at tier 2 or higher.
- Otherwise choose the lowest tier that the cached probe info and the client's reported capabilities say should work.
- If no probe info is cached, probe with a short timeout and cache the result on the channel. If probing fails, start at tier 2.
- Probe info is refreshed when older than 24 hours, when the stream URL changes, or after a format failure.

### Escalation

- A **format failure** reported by the client moves playback up one tier. This covers decoder errors, "source not supported" errors, and no new frames within 15 seconds.
- A **network failure** is retried once on the same tier and never escalates, because converting cannot fix an unreachable provider.
- The server also escalates by itself when FFmpeg exits with a codec or container error.
- Each tier is tried at most once per playback attempt.
- The tier that worked is remembered in memory per channel and client type. This memory is cleared when probe info is refreshed or the stream URL changes.
- The user can override the choice for the current playback only: Automatic, Original (tier 1), Compatible (tier 2), or Converted (tier 4).

### Live sessions

- A live handle never finishes.
- Direct sessions end on stop or channel change, or after 90 seconds without a heartbeat (clients send one every 30 seconds).
- Proxy sessions end through the existing staleness cleanup. Live content has no resume position and reports no watch progress.

### Connection limits

- Each IPTV provider has an optional, user-set `max_connections`.
- Every active session counts against it: live and VOD, every tier, every device and profile.
- It is enforced before playback. If the requesting device is switching channel or retrying, its own previous session is released first.
- At the limit, playback is refused with a list of what is using the connections and an option to stop one. Nothing is preempted automatically.
- Counts are held in memory. Sharing one provider connection between several viewers is explicitly rejected.

### User-Agent precedence

From most to least specific:

1. Channel, either a user override or supplied by the provider.
2. IPTV provider.
3. Profile.
4. Household.
5. Built-in default, used for server-side requests only.

Profile settings apply only to playback. User-Agent settings apply only to IPTV, never to TorBox, Easynews, or module sources.

### Stream handle `headers` field (revision of ADR-0015)

Direct-mode handles gain an optional `headers` object, for example `{"User-Agent": "VLC/3.0.20"}`, which the client must send when fetching `url`. Proxy-mode handles never carry it, because the server applies the headers upstream. Clients that cannot send custom headers must not be issued a direct handle that requires them. Everything else in ADR-0015 remains as decided.

## Rationale

- Reuses the delivery chain and HLS machinery that already exist rather than adding a new one.
- Converting only the incompatible audio is far cheaper than a full transcode, and covers the most common IPTV incompatibility.
- Escalating on failure and remembering what worked avoids converting everything by default and avoids repeating failures.
- Enforcing limits before playback means the provider never sees an over-limit attempt.
- A `headers` field is the smallest change that lets native clients keep direct delivery for channels that need a User-Agent.

## Alternatives considered

- **Always proxy channels that need a User-Agent.** Rejected: it forces server load for native clients that can send the header themselves.
- **Always transcode live TV.** Rejected: high CPU cost and quality loss for streams that would play directly or with a remux.
- **Escalate on network failures too.** Rejected: conversion cannot fix connectivity.
- **Shared upstream per channel (restreaming).** Rejected: it exceeds subscription terms and adds substantial complexity.
- **Automatic preemption at the connection limit.** Rejected: it stops someone's stream without their consent.

## Consequences

- On acceptance, ADR-0015's status becomes Superseded, with Superseded by set to ADR-0023. Until then ADR-0015 remains authoritative.
- New nullable probe columns on channels (new table, ADR-0021). A nullable `iptv_user_agent` on profiles, an existing table, needs a model change plus a guarded Alembic revision per ADR-0019. A household-level IPTV User-Agent setting is added.
- New play endpoint with failure reporting, a heartbeat and stop path for direct sessions, and in-memory session counting per provider.
- The web client gains a live player mode: overlay, channel up/down, mini-guide, stall watchdog, and a playback mode menu.

## Relationship to other ADRs

- **ADR-0014:** delivery order unchanged; the transcode tier is split into audio-only and full.
- **ADR-0015:** superseded on acceptance; the only change is the optional `headers` field on direct handles.
- **ADR-0016:** HLS remux path reused for live with sliding-window playlists.
- **ADR-0005:** household trust model makes direct URLs and headers acceptable to share with clients.
- **ADR-0018:** native Android / Fire TV clients are the main users of direct delivery with headers.
- **ADR-0020, ADR-0021:** provider connection limits and effective channel values feed playback.
