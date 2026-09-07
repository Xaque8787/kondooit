# ADR-0016: HLS remux via FFmpeg for web client playback

- **Status:** Accepted
- **Date:** 2026-09-07
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How does the web client play streams that browsers cannot natively decode?"

## Context

ADR-0014 established a direct-first fallback chain: direct delivery, then server proxy with remux, then transcode. For the web client specifically, most source streams arrive in containers (MKV, AVI) or via URLs that cannot be set as a `<video>` src directly. Browsers natively support only a narrow set of container/codec combinations (MP4/H.264, WebM/VP9).

The web client is the first and currently only client. Native clients with broader codec support will come later. In the interim, the web client needs a server-side processing path that converts source streams into a browser-playable format.

Two approaches were considered for the web client:

1. **Companion desktop app** — a local helper process running FFmpeg, communicating with the browser via localhost WebSocket. The browser would receive stream handles, pass them to the companion, and the companion would handle remux/transcode locally before feeding a local URL back to the browser.

2. **Server-side HLS remux via hls.js** — the server runs FFmpeg to remux source streams into HLS (fragmented MP4 segments with M3U8 playlist), served over HTTP. The browser uses hls.js to play the HLS stream.

## Decision

Use **server-side HLS remux with hls.js** for web client playback.

The server provides an HLS endpoint (`/hls/{stream_id}/master.m3u8`) that:

1. Looks up the stream handle to get the upstream provider URL.
2. Spawns FFmpeg with `-c copy` to remux the upstream into live-style HLS with fMP4 segments.
3. Serves the M3U8 playlist and segments to the browser.

The browser uses hls.js to consume the HLS stream. On Safari (which supports HLS natively), the `<video>` element can consume the M3U8 URL directly.

### HLS style: live (not VOD)

Segments are generated on-the-fly as FFmpeg reads the upstream. The playlist is a sliding-window live playlist (`#EXT-X-ENDLIST` is appended only when FFmpeg finishes). This starts playback faster than probing the full file first. Seeking is limited to the buffered/generated portion until the full file is processed.

### FFmpeg in the Docker image

FFmpeg is added to the server's Docker image (`apt-get install ffmpeg`). This is required for remux and transcode modes per ADR-0014.

## Rationale

- **Simplicity.** HLS remux is a single server-side process per stream. No companion app to install, no localhost WebSocket protocol, no desktop-only limitation.
- **Works everywhere.** hls.js runs in any modern browser. No platform restrictions, no installation step for users.
- **Near-zero CPU cost.** Remux with `-c copy` repackages compressed data without re-encoding. The server cost is the bandwidth, not compute.
- **Aligned with ADR-0014.** This is exactly the "proxy + remux" tier described there. The HLS format is the specific output container chosen for the remux.
- **Future clients bypass this.** Native clients (Android, iOS, TV) will use direct delivery or their own codec-capable players. The HLS remux path is web-client-specific. When a native client is built, it reports its capabilities to the server, and the server issues direct-mode handles per ADR-0015.

## Alternatives considered

- **Companion desktop app.** More complex to build and deploy: requires users to install a separate process, introduces localhost networking, limits to desktop platforms. Rejected for v0.0.1 in favor of the simpler server-side approach. May be revisited for power users who want local remux to save server bandwidth.

- **WASM FFmpeg in browser.** Too slow and memory-constrained for real-time remuxing of HD/4K content. Not viable.

- **Progressive MP4 download via server proxy.** The existing `GET /streams/{stream_id}` endpoint already does this. Works for MP4 sources but fails for MKV and other non-browser-native containers. HLS remux handles all container formats uniformly.

## Consequences

- FFmpeg must be available in the server Docker image.
- Each web playback session consumes server bandwidth (upstream to server, server to browser). On LAN this is negligible; over the internet, the ADR-0014 bandwidth constraints apply.
- The HLS session manager holds ephemeral state (FFmpeg processes, temp segment files). Sessions are cleaned up on stop or after a staleness timeout.
- Seeking within live-style HLS is limited to already-generated segments. This is acceptable for the initial implementation; VOD-style HLS with full seeking can be added later.
- The player page reports watch progress via the existing beacon endpoint, enabling continue-watching functionality.

## Relationship to other ADRs

- **ADR-0014** (Direct delivery default): HLS remux is the web-client implementation of the "proxy + remux" fallback tier.
- **ADR-0015** (Stream handles): The HLS endpoint consumes stream handles from the existing store. The handle's `mode` field is not yet used to auto-select direct vs. proxy — for now, the web player always uses the HLS path. This will be refined when client capability reporting is implemented.
- **ADR-0005** (Household model): Server-side remux is acceptable in the household LAN context where bandwidth between server and clients is effectively unlimited.
