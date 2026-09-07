# ADR-0013: Transport-agnostic stream handles replace client-constructed URLs

- **Status:** Superseded
- **Date:** 2026-09-03
- **Supersedes:** —
- **Superseded by:** ADR-0015
- **Resolves:** "How should stream references be communicated between server and clients across different transports?"

## Context

When a source provider (Easynews, TorBox, etc.) resolves a playable resource, the server currently returns a relative HTTP path (e.g., `/source-providers/easynews/stream?post_hash=...&filename=...`). The web client prepends `window.location.origin + "/api"` to construct a full URL for clipboard copy or playback.

This approach has several problems:

1. **Transport coupling.** The stream reference is an HTTP URL fragment. It assumes the client reaches the server over HTTP and can construct a valid URL by prepending its own origin. This fails for clients connected over iroh or any non-HTTP transport.

2. **Client responsibility for URL construction.** Each client platform (web, Android, Apple, TV) must independently know how to turn a relative path into a reachable address. The logic differs per environment (`window.location.origin` for browsers, a configured server address for native apps, nothing meaningful for iroh). This scatters transport knowledge across every client.

3. **Upstream details leak to clients.** The query parameters expose provider-specific implementation details (post_hash, dl_farm, dl_port, down_url) to the client. The client has no use for these — they are upstream Easynews concepts that only the server needs. Exposing them enlarges the client-server contract unnecessarily and creates a coupling between the client-facing API shape and upstream provider APIs.

4. **No session or lifecycle management.** The relative path is stateless — anyone who has the URL (with the right query parameters) can hit the proxy endpoint. There is no expiration, no binding to a user session, and no server-side control over active streams.

ADR-0006 establishes that playback orchestration and stream transport are core server responsibilities. ADR-0007 establishes that the application protocol is transport-independent. The current implementation violates both: it makes stream references HTTP-specific and pushes transport construction to the client.

## Decision

The server issues **opaque stream handles** (short-lived tokens or identifiers) instead of URL paths when a source is resolved or discovered.

### How it works

1. **Source resolution produces a handle.** When the server resolves a playable source (whether Easynews, TorBox, a cached torrent, or any future provider), it stores the upstream details server-side and returns an opaque identifier to the client: `{ "stream_id": "abc123" }`.

2. **Upstream details stay server-side.** The post_hash, credentials, download URL, and all other provider-specific parameters are stored in a server-side stream session keyed by the handle. The client never sees them.

3. **Clients request playback using the handle over their current transport.**
   - An HTTP client calls `GET /api/streams/{stream_id}`. The server looks up the upstream details, proxies the bytes, and streams the response.
   - An iroh client sends a stream-request message containing the stream_id over its iroh connection. The server proxies upstream and pushes bytes back over the iroh channel.
   - A future transport works identically — the handle is the same; only the byte-delivery mechanism changes.

4. **Handles have a lifetime.** Stream handles expire after a configurable TTL (default: a few hours) or when the associated user session ends. Active streams (bytes currently flowing) are not terminated by expiration — only unused handles are cleaned up. This prevents unbounded server-side state growth.

5. **Handles are user-scoped.** A handle is bound to the user session that created it. A different user (or an unauthenticated request) cannot use another user's handle.

### What the client receives

Before (current):
```json
{
  "stream_url": "/source-providers/easynews/stream?post_hash=abc&filename=Movie.mkv&down_url=https://..."
}
```

After:
```json
{
  "stream_id": "kd_s_7f3a2b1c"
}
```

The client's only job is to pass that stream_id to whatever transport it is connected through.

### Server-side stream session state

The server maintains a lightweight in-memory (or short-TTL cache) mapping:

```
stream_id → {
    user_id,
    provider_key,
    upstream_url,        // fully constructed, ready to fetch
    upstream_headers,    // auth headers, etc.
    created_at,
    expires_at,
    content_metadata     // filename, size, content-type for response headers
}
```

This is not persisted to the database — it is ephemeral session state. Server restart invalidates all handles, which is acceptable because clients can re-resolve sources.

## Rationale

- **Transport independence.** The handle is a string. It works identically over HTTP, iroh, WebSocket, or any future transport. No client needs URL-construction logic.
- **Security improvement.** Upstream provider details, credentials, and internal URL structures are never exposed to clients. The handle is opaque and user-scoped.
- **Simpler client contract.** Every client on every platform does the same thing: "play stream_id X." The transport layer handles delivery. Client implementations shrink.
- **Consistent with ADR-0006 and ADR-0007.** Playback orchestration is a core server responsibility. The application protocol is transport-independent. Opaque handles honor both.
- **Foundation for future capabilities.** Stream handles provide a natural attachment point for bandwidth controls, concurrent stream limits, playback position tracking, and transcoding — all server-side, without changing the client contract.

## Alternatives considered

- **Keep relative URL paths, let each client prepend its server address.** This is the current approach. It works for a single HTTP web client but breaks for iroh, leaks upstream details, and forces every future client to implement URL construction differently. Rejected because it contradicts ADR-0006 and ADR-0007.

- **Server returns absolute URLs (server constructs its own full address).** This requires the server to know its own externally reachable address, which is unreliable behind NAT, reverse proxies, and iroh tunnels. It also remains HTTP-specific. Rejected.

- **Embed credentials in upstream URLs (direct Easynews/TorBox URLs to clients).** Eliminates the proxy but exposes provider credentials directly to clients. Any client compromise leaks paid-service credentials. Also HTTP-specific. Rejected for both security and transport reasons.

- **Full playback session management (detailed session state with pause/resume/seek tracking).** More capable but significantly more complex. Stream handles are a necessary stepping stone — session management can be layered on top of handles later. Rejected as premature for the current phase.

## Consequences

- The server gains a stream-handle store (in-memory or short-TTL cache) and a stream-delivery endpoint.
- The `build_proxy_stream_url` pattern (constructing relative HTTP paths with upstream query parameters) is replaced by handle creation.
- Source providers return upstream details to the application layer, not URL fragments. The application layer creates handles.
- The web client's URL-construction logic (`window.location.origin + "/api" + path`) is replaced by a simple `GET /api/streams/{stream_id}` call.
- Clipboard "Copy URL" still works — it copies the full HTTP stream URL (`{origin}/api/streams/{stream_id}`), which is valid for the handle's lifetime.
- Server restart invalidates all outstanding handles. Clients must re-resolve, which is a normal flow (search results are already ephemeral).
- Adds server-side state that must be managed (TTL expiration, cleanup). This is bounded and predictable.

## Relationship to other ADRs

- **ADR-0006** (Playback orchestration is core): Directly implements. Stream delivery becomes a server responsibility end-to-end, not a URL the client constructs.
- **ADR-0007** (Transport-independent protocol): Directly implements. The stream handle is the transport-independent reference; each transport delivers bytes its own way.
- **ADR-0002** (Provider vs. source): Compatible. Providers still resolve sources. The change is in how resolved sources are communicated to clients — handles instead of URL fragments.
- **ADR-0012** (Resolution providers as installable modules): Compatible. Resolver modules still produce source results. The handle layer sits above them in the application/API layer.
