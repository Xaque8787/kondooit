# ADR-0015: Stream handles carry delivery mode — direct URL or proxy handle

- **Status:** Accepted
- **Date:** 2026-09-07
- **Supersedes:** ADR-0013
- **Superseded by:** —
- **Resolves:** "How do stream handles work when the default delivery mode is direct rather than always-proxy?"

## Context

ADR-0013 introduced opaque stream handles to replace client-constructed URLs. The design assumed the server always proxies stream bytes: the client receives only an opaque `stream_id` and fetches bytes from `GET /api/streams/{stream_id}`, with all upstream details kept server-side.

ADR-0014 changes the default delivery mode to direct, where the client fetches bytes directly from the provider's CDN URL. This means the stream handle must sometimes carry a playable URL rather than just an opaque proxy identifier. The handle mechanism from ADR-0013 remains valuable for proxy/remux/transcode cases, but it must be extended to support direct delivery.

Additionally, ADR-0013 rejected direct URLs primarily on security grounds ("any client compromise leaks paid-service credentials"). ADR-0014 re-evaluates this in the context of the household model (ADR-0005) and concludes that credential exposure to household members is not a meaningful threat.

## Decision

Stream handles become a **polymorphic delivery instruction** with two modes:

### Direct mode

The server resolves the source, determines that direct delivery is appropriate (per ADR-0014's fallback chain), and returns the provider URL to the client:

```json
{
  "stream_id": "kd_s_7f3a2b1c",
  "mode": "direct",
  "url": "https://cdn.provider.example/download/abc123?token=xyz",
  "content_type": "video/mp4",
  "filename": "Movie.2024.2160p.WEB-DL.mp4"
}
```

The client plays the URL directly. The `stream_id` is still issued for lifecycle tracking (logging, concurrent stream counting, playback state) but the server is not in the byte-delivery path.

### Proxy mode

The server determines that server-side processing is needed (remux or transcode per ADR-0014), and returns an opaque handle exactly as ADR-0013 described:

```json
{
  "stream_id": "kd_s_9e4d5f2a",
  "mode": "proxy",
  "content_type": "video/mp4",
  "filename": "Movie.2024.2160p.WEB-DL.mp4"
}
```

The client fetches bytes from the server using the handle:
- HTTP client: `GET /api/streams/{stream_id}`
- iroh client: stream-request message containing the `stream_id`

The server proxies upstream, applies remux or transcode as needed, and delivers the processed bytes.

### What the client does

The client inspects the `mode` field:
- `"direct"`: play the `url` field directly (video element src, ExoPlayer data source, etc.)
- `"proxy"`: fetch bytes from the server's stream endpoint using the `stream_id`

This is a simple branch, not a complex abstraction. Every client platform implements both paths.

### What stays the same from ADR-0013

- **Stream handles are user-scoped.** A handle is bound to the user/profile session that created it.
- **Handles have a lifetime.** They expire after a configurable TTL. Active streams are not terminated by expiration.
- **Server-side state exists for all handles.** Even direct-mode handles have server-side records for lifecycle tracking, logging, and concurrent stream management.
- **Upstream provider details are stored server-side.** The server always knows the full upstream context. In direct mode, it chooses to share the URL with the client; the server-side record still holds all details.
- **Handles are transport-agnostic identifiers.** The `stream_id` string works across HTTP, iroh, or any future transport. In direct mode, the accompanying `url` is an HTTP(S) URL because that is what provider CDNs serve — this is inherent to the providers, not a transport assumption in the protocol.

### What changes from ADR-0013

- **Handles can carry a direct URL.** ADR-0013 kept all upstream details server-side without exception. Now, when direct delivery is selected, the resolved URL is included in the handle response.
- **The client has a mode-dependent code path.** ADR-0013's client was simpler (always fetch from server). Now the client must handle two modes. This is a small increase in client complexity, justified by the bandwidth and scalability benefits (ADR-0014).
- **"Copy URL" behavior changes.** For direct-mode handles, the copyable URL is the provider URL (valid for its own lifetime, typically hours). For proxy-mode handles, the copyable URL is the server's stream endpoint (valid for the handle's TTL).

### Server-side stream session state (revised)

```
stream_id → {
    user_id,
    profile_id,
    mode,                // "direct" | "proxy"
    provider_key,
    upstream_url,
    upstream_headers,
    processing,          // null | "remux" | "transcode"
    transcode_profile,   // codec targets when processing is "transcode"
    created_at,
    expires_at,
    content_metadata     // filename, size, content_type
}
```

As with ADR-0013, this is ephemeral in-memory state, not persisted to the database.

## Rationale

- **Preserves the handle abstraction.** The `stream_id` remains the canonical reference for a resolved stream across the system. Lifecycle tracking, logging, and concurrent stream management work uniformly regardless of delivery mode.
- **Supports the direct-first strategy.** ADR-0014 establishes direct delivery as the default. The handle mechanism must accommodate this without forcing everything through the proxy path.
- **Minimal client complexity increase.** A single `if (mode === "direct")` branch is all that is needed. The handle abstraction still shields the client from provider-specific details, resolution logic, and the fallback decision.
- **Server retains full control.** Even in direct mode, the server decided to make it direct. The server can change the mode per-stream based on format analysis, admin settings, or client capabilities. The client does not choose — it follows the server's instruction.

## Alternatives considered

- **Keep ADR-0013 unchanged (always opaque, always proxy).** This was the ADR-0013 design. Rejected because ADR-0014 establishes that always-proxying is not viable for the household deployment model. The handle mechanism must adapt.

- **Two separate mechanisms (handles for proxy, raw URLs for direct).** Would fragment the API surface and make lifecycle tracking inconsistent. Rejected in favor of a unified handle that carries mode information.

- **Client decides the mode based on its own capabilities.** The client would inspect stream metadata and decide whether to use the proxy or fetch directly. Rejected because delivery mode selection involves server-side knowledge (admin settings, bandwidth policy, whether FFmpeg is available) that the client does not have. The server decides; the client follows.

## Consequences

- The stream handle API response includes a `mode` field and conditionally a `url` field.
- Every client platform implements both `direct` and `proxy` playback paths.
- The server's stream-handle store gains `mode` and `processing` fields.
- The proxy stream endpoint (`GET /api/streams/{stream_id}`) only serves proxy-mode handles; direct-mode handles return an error if a client mistakenly tries to proxy-fetch them.
- Direct-mode URLs may contain provider authentication tokens. This is acceptable per ADR-0005's household trust model.
- The "force proxy" admin setting (from ADR-0014) is implemented by the handle creation logic: when enabled, all handles are issued in proxy mode regardless of stream compatibility.

## Relationship to other ADRs

- **Supersedes ADR-0013.** Extends the stream handle concept to support direct delivery alongside proxy delivery.
- **ADR-0014** (Direct delivery default): This ADR is the handle-layer implementation of ADR-0014's delivery strategy.
- **ADR-0005** (Household model): Direct-mode credential exposure is acceptable because all profiles are household members.
- **ADR-0007** (iroh transport): In direct mode, media bytes bypass iroh entirely — the client reaches the provider CDN over the regular internet. In proxy mode, iroh-connected clients receive bytes through the iroh channel. Both work with the same handle.
