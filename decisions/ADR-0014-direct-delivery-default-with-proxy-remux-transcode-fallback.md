# ADR-0014: Direct delivery is the default; server proxy with remux/transcode is the fallback chain

- **Status:** Accepted
- **Date:** 2026-09-07
- **Supersedes:** ADR-0006
- **Superseded by:** —
- **Resolves:** "Should the server always proxy stream bytes?", "How should direct vs. proxied playback be decided?", "Where does remuxing and transcoding fit in the delivery chain?"

## Context

ADR-0006 established that playback orchestration and stream transport are core server responsibilities, with "direct playback" and "server proxy" as two modes of the playback engine. It did not establish which mode is preferred or how the server should decide between them.

In practice, the self-hosted household deployment model (ADR-0005) creates a strong constraint: residential internet connections typically have 20–50 Mbps upload bandwidth. A single proxied 4K remux stream consumes 50–80 Mbps sustained, which would saturate or exceed the server's upload capacity. Two concurrent proxied streams would be impossible. Proxying every stream doubles the bandwidth cost (provider-to-server, then server-to-client) for no benefit when the client can reach the provider directly.

Meanwhile, source providers like Easynews and TorBox resolve to CDN-hosted download URLs designed for high-bandwidth direct delivery. The server adds latency and a bandwidth bottleneck by sitting in the middle.

The iroh transport (ADR-0007) does not change this analysis. iroh provides the secure control-plane connection between client and server (catalog browsing, source resolution, authentication). Media byte delivery does not need to flow through iroh — the client can fetch resolved URLs directly from provider CDNs over the regular internet, the same way a Stremio client fetches resolved addon URLs independently of the addon protocol channel.

However, some streams require server-side processing before a client can play them:

- **Container incompatibility:** MKV, AVI, or MPEG-TS containers cannot be played natively by browser-based clients. These need remuxing to fragmented MP4.
- **Codec incompatibility:** HEVC/H.265 or other codecs unsupported by the client's decoder. These need transcoding to H.264 or another compatible codec.

Remuxing (repackaging the same compressed data into a different container) is nearly free in CPU terms. Transcoding (re-encoding the video) is CPU-expensive but sometimes necessary.

## Decision

The playback delivery strategy follows a **direct-first fallback chain**:

```
1. Direct delivery (default)
   Client receives the resolved provider URL and fetches bytes directly.
   Server bandwidth cost: zero for stream data.

2. Server proxy with remux (first fallback)
   When the stream container or muxing is incompatible with the client,
   the server proxies the stream through FFmpeg with codec copy (-c copy)
   and outputs a compatible container (fragmented MP4).
   Server bandwidth cost: full stream bandwidth.
   Server CPU cost: near zero.

3. Server proxy with transcode (last resort)
   When the stream codec itself is incompatible with the client and
   remuxing alone would not produce a playable result, the server
   proxies through FFmpeg with video/audio re-encoding.
   Server bandwidth cost: full stream bandwidth.
   Server CPU cost: high (one or more CPU cores per stream).
```

### How the mode is selected

The playback engine determines the delivery mode based on:

1. **Stream metadata** — container format, video codec, audio codec (from the source provider's resolution result or from probing the stream headers).
2. **Client capabilities** — what the requesting client can natively decode (reported by the client or inferred from client type: browser, native app, TV app).
3. **Account/profile settings** — the admin may force proxy mode server-wide, or a profile may prefer specific quality/codec constraints that require server-side processing.

Decision logic:

- If the stream format is natively playable by the client: **direct delivery**.
- If the container is incompatible but the codecs are compatible: **proxy + remux**.
- If the codec is incompatible: **proxy + transcode**.
- If stream metadata is unknown or cannot be determined before delivery begins: **proxy + remux** (safe default — remux can pass through compatible streams with minimal overhead, and the server can detect and escalate to transcode if needed).

### What stays the same from ADR-0006

- **Source resolution remains a provider responsibility.** Providers resolve playable resources; they do not implement transport.
- **Playback orchestration remains a core responsibility.** The core decides the delivery mode, manages sessions, and coordinates fallbacks.
- **Transcoding remains an invokable capability**, not hardcoded into the playback engine. FFmpeg is the initial implementation; the interface allows future alternatives (hardware encoding, etc.).
- **Stream transport infrastructure** (range handling, buffering, bandwidth controls) remains in the core playback subsystem and is used when proxy mode is active.

### What changes from ADR-0006

- **Direct delivery is the explicit default**, not just one of two unnamed modes.
- **The fallback chain is ordered**: direct → remux → transcode. This is a defined progression, not an unordered choice.
- **The server is not always in the data path.** In direct mode, stream bytes flow from the provider CDN directly to the client. The server's role ends after resolving the source and communicating the URL.
- **Client capability reporting** is introduced as an input to the delivery decision.

## Rationale

- **Bandwidth reality.** Self-hosted servers on residential connections cannot sustain proxying multiple HD/4K streams. Direct delivery is the only viable default for the target deployment model.
- **Provider CDNs are purpose-built for delivery.** Easynews, TorBox, and similar services operate high-bandwidth CDN infrastructure. Routing bytes through a home server adds latency and a bottleneck without adding value.
- **Remux before transcode.** Most container incompatibilities (MKV in browsers) can be solved by remuxing, which has negligible CPU cost. Transcoding is expensive and should only be used when the codec itself is the problem. This ordering minimizes server resource consumption.
- **Server-centric does not mean server-in-the-middle.** The server is the intelligence and orchestration point — it discovers sources, resolves URLs, applies quality preferences, manages credentials, and decides what the client should play. It does not need to relay every byte to fulfill that role.
- **Credential exposure is acceptable in the household model.** Provider URLs may contain authentication tokens (Easynews passwords, TorBox API keys). In the single-household model (ADR-0005), all profiles are family members sharing the same provider subscriptions. Exposure of these tokens to household members is not a meaningful security risk. The tokens are often short-lived or scoped to specific downloads.

## Alternatives considered

- **Always proxy (server always in the data path).** This was the implicit assumption in ADR-0006. Rejected because it makes 4K playback impossible on typical residential connections and doubles bandwidth costs for every stream. It provides credential isolation that is unnecessary in the household model.

- **Always direct (no proxy/remux/transcode capability).** Simpler but too limiting. Browser clients cannot play MKV natively. Some provider streams use codecs that specific clients cannot decode. Without a server-side processing fallback, these streams would simply be unplayable.

- **Client-side remuxing/transcoding (e.g., WASM FFmpeg in the browser).** Theoretically possible but impractical: browser WASM FFmpeg is slow, memory-constrained, and cannot handle real-time 4K remuxing. Native clients could do it, but pushing this to every client platform fragments the implementation. Server-side processing is simpler and more reliable.

- **Let the profile choose direct vs. proxy as a toggle.** This was considered in early design discussions. Rejected as a profile-level setting because the correct delivery mode depends on the specific stream's format and the client's capabilities, not a blanket preference. However, an admin-level "force proxy" override is retained for environments where direct delivery is undesirable (e.g., a server with very fast upload that wants to centralize all traffic).

## Consequences

- The playback engine must implement the three-tier fallback chain: direct → remux → transcode.
- Source resolution results must include stream metadata (container, video codec, audio codec) when available, to enable the delivery decision without probing.
- Clients must report their playback capabilities (supported containers and codecs) or the server must maintain a capability map per client type.
- FFmpeg must be available in the server's runtime environment (Docker image) for remux and transcode modes.
- Direct delivery mode means the client receives provider URLs. The stream handle mechanism (ADR-0013/superseding ADR) must support returning direct URLs in addition to proxy handles.
- An admin-level setting ("force proxy") allows overriding direct delivery for all streams, for deployments where the server has sufficient bandwidth and credential isolation is desired.
- The proxy infrastructure from ADR-0006 (range handling, buffering, sessions, bandwidth controls) remains relevant but is only active when proxy mode is selected.

## Relationship to other ADRs

- **Supersedes ADR-0006.** Preserves the core-owns-playback-orchestration principle but establishes direct delivery as the default and defines the ordered fallback chain.
- **ADR-0005** (Household model): The credential exposure analysis depends on the single-household trust model.
- **ADR-0007** (iroh transport): iroh handles the control plane; direct delivery means media bytes bypass iroh entirely, which is the correct separation of concerns.
- **ADR-0013** (Stream handles): Must be revised to support returning direct URLs alongside proxy handles. See ADR-0015.
