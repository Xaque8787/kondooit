# Mydia Research — iroh Implementation Analysis

**Date:** 2026-10-05
**Source:** https://github.com/getmydia/mydia
**Inspection method:** AGENTS.md (read in full), repo directory structure, web search. Source code in `native/mydia_p2p_core/src/` was NOT inspected — findings below are based on documentation and structure only.

---

## 1. How Mydia Uses iroh

### Architecture: Shared Core Crate + Platform FFI

Mydia's defining architectural choice is a **single shared Rust crate** (`native/mydia_p2p_core`) that both the server and the client compile against:

```
native/mydia_p2p_core/    ← Pure Rust: iroh endpoint, connection, protocol
native/mydia_p2p/         ← Rustler NIF: exposes core to Elixir (server)
                          ← flutter_rust_bridge: exposes core to Dart (client)
```

**Server side:** The Phoenix (Elixir) backend wraps `mydia_p2p_core` using **Rustler** — a library for writing Erlang NIFs in Rust. The NIF module `Mydia.P2p` runs inside the BEAM VM. The server is a permanent iroh node: always online, always connected to a relay, accepting incoming connections.

**Client side:** The Flutter player wraps the same `mydia_p2p_core` using **`flutter_rust_bridge`** — a code generator that creates Dart bindings for Rust functions. The client connects to the server's iroh endpoint for discovery and control.

**Protocol parity:** Because both sides share the same Rust crate, the connection logic, protocol constants, and stream handling are guaranteed to match. There is no risk of the server and client drifting on protocol details.

### Connectivity Details

| Aspect | Mydia | Kondooit |
|---|---|---|
| iroh integration model | In-process NIF (Rustler) + shared crate | Sidecar subprocess + WASM runtime |
| Server language | Elixir / Phoenix | Python / Litestar |
| Client framework | Flutter (native) | React (browser) + WASM |
| Client iroh binding | `flutter_rust_bridge` (native Rust) | wasm-bindgen (browser WASM) |
| Shared core crate | Yes (`mydia_p2p_core`) | No (separate implementations) |
| Wire protocol | Not confirmed (possibly HTTP or custom) | HTTP/1.1 tunneled over iroh bidi streams |
| Media over iroh | Yes — HLS via local proxy in client | Yes — HTTP tunnel for HLS; direct CDN delivery when possible |
| Relay | Self-hosted relay, n0 public as fallback | n0 public relay (self-hosted planned) |
| Identity | Ed25519 keypair, persisted | Ed25519 keypair, persisted |
| Discovery | iroh DNS-based discovery | iroh default discovery (N0 preset) |

### Media Delivery

Mydia's AGENTS.md states: "Media streams (HLS) are served over the p2p connection (via a local proxy in the client)."

This means:
1. The server provides HLS manifest and segment URLs
2. The Flutter client's local proxy fetches these over the iroh connection
3. The Flutter media player points to `localhost:<port>/...` which the local proxy serves

This is functionally similar to Kondooit's approach (HTTP tunneled over iroh), but the local proxy pattern is notable — the client creates a local HTTP server that mediates between the media player and the iroh connection.

**Open question:** Does Mydia support direct CDN delivery (bypassing iroh for media bytes), or does all media flow through the p2p connection? The AGENTS.md does not mention direct delivery. This may be because Mydia's sources are different (local media library vs. Debrid CDN links).

---

## 2. Comparison with Kondooit's iroh Architecture

### Kondooit's Current Architecture (ADR-0017)

```
Browser (GitHub Pages)
  └── kondooit-runtime (WASM)
        └── iroh WASM endpoint
              └── iroh relay
                    └── Home server
                          ├── kondooit-iroh (Rust sidecar)
                          │     └── tunnels HTTP to localhost:8000
                          └── Litestar (Python HTTP API)
```

Key characteristics:
- **Sidecar model:** iroh runs as a separate Rust binary, managed as a subprocess by the Python server. Communication via Unix socket.
- **HTTP tunneling:** The sidecar receives iroh bidi streams and proxies them as HTTP to Litestar on localhost:8000.
- **Browser WASM:** The client uses a custom WASM module (`kondooit-runtime`) that wraps iroh for browser use.
- **Two separate Rust codebases:** `kondooit-iroh/` (server sidecar) and `kondooit-runtime/` (browser WASM) share protocol constants but are otherwise independent implementations.

### Key Differences

#### A. Shared Core Crate vs. Separate Implementations

**Mydia:** Both server and client compile against `mydia_p2p_core`. Connection logic, protocol handling, and stream dispatch are written once.

**Kondooit:** `kondooit-iroh/` (server) and `kondooit-runtime/` (client) are separate crates that share only protocol constants (ALPN, stream-type prefixes). The connection logic, HTTP parsing, and stream handling are independently implemented in each.

**Impact:** Kondooit's approach allows the server and client to drift. The server's `tunnel.rs` manually parses HTTP response headers (Content-Length, chunked encoding) — this logic is duplicated in the client's `wasm.rs` (`parse_http_response`, `decode_chunked`). If one side fixes a parsing bug, the other may not.

**Recommendation for Kondooit (future native clients):** When building native clients (Android, iOS, TV), strongly consider extracting a shared `kondooit-p2p-core` crate that both the server sidecar and native clients compile against. This is the single most valuable architectural pattern from Mydia. The browser WASM runtime can remain separate (browser constraints differ), but native clients and the server sidecar should share a core.

#### B. In-Process NIF vs. Sidecar Subprocess

**Mydia:** iroh runs inside the BEAM VM via a Rustler NIF. No subprocess management, no Unix socket IPC. The Elixir code calls directly into Rust functions.

**Kondooit:** iroh runs as a separate process (`kondooit-iroh`). The Python server manages the subprocess lifecycle and communicates via Unix socket JSON-line protocol.

**Trade-offs:**

| | Mydia (NIF) | Kondooit (Sidecar) |
|---|---|---|
| Latency | Direct function calls, no IPC | Unix socket round-trip per command |
| Crash isolation | NIF crash can crash BEAM | Sidecar crash does not affect Python |
| Async runtime bridging | Rustler handles Tokio↔BEAM | No bridging needed (separate processes) |
| Complexity | NIF setup, Rustler learning curve | Subprocess lifecycle, Unix socket protocol |
| Restart on failure | BEAM supervisor restarts NIF | Sidecar monitor restarts subprocess |

**Assessment:** Both approaches are valid. Kondooit's sidecar model is the right choice for Python (no mature iroh FFI, async runtime bridging would be painful). Mydia's NIF model works because Elixir has excellent Rust FFI via Rustler and the BEAM supervisor can restart crashed NIFs. **No change recommended for Kondooit's server side.**

#### C. Relay Infrastructure

**Mydia:** Operates their own relay with n0 public relays as fallback. This gives them control over relay bandwidth and availability.

**Kondooit:** Uses n0 public relays exclusively. Self-hosted relay is planned (ADR-0017 mentions it as a future option).

**Recommendation for Kondooit:** When relay bandwidth becomes a concern (more users, proxied media), self-hosting a relay is straightforward with iroh. The sidecar's relay configuration is already exposed through the control API. This remains a future operational concern, not an architectural one.

#### D. Client Connection Model

**Mydia:** Flutter client uses `flutter_rust_bridge` to call into the same Rust iroh code. The client is a full native application with native networking — it can participate in NAT hole-punching and potentially achieve direct P2P connections (bypassing the relay for media).

**Kondooit (browser):** The browser WASM runtime uses iroh's browser endpoint, which communicates exclusively through relays (browsers cannot open raw UDP/QUIC sockets). All traffic goes through the relay.

**Kondooit (future native clients):** When Kondooit builds native clients (Android, iOS, TV), they could use iroh's native SDKs with direct P2P connections. This is where Mydia's shared-core-crate pattern becomes directly relevant.

#### E. Media Delivery Strategy

**Mydia:** All media is served over the p2p connection via a local proxy in the client. There is no mention of direct CDN delivery. This makes sense if Mydia's primary use case is local media files (no CDN URLs to hand off).

**Kondooit:** Has a sophisticated delivery matrix (ADR-0014, ADR-0015, ADR-0017):
- Direct delivery (client fetches from provider CDN) — default for CDN-backed sources
- Server proxy through iroh — for remux/transcode or local files
- Profile-level toggle to force proxy for remote playback

**Assessment:** Kondooit's delivery strategy is more advanced for the Debrid/CDN use case. Mydia's approach is simpler but appropriate for local media libraries. **No change recommended.**

#### F. Local Proxy Pattern

**Mydia:** The Flutter client runs a local HTTP proxy that mediates between the media player and the iroh connection. The media player points to `localhost:port/...`.

**Kondooit (browser):** The WASM runtime intercepts `fetch()` calls in JavaScript and routes them through iroh. There is no local HTTP server — the interception happens at the JavaScript level.

**For future native clients:** A local proxy (like Mydia's) would be the natural approach. The native client would start a local HTTP server, and the media player would point to it. The local proxy would route requests through the iroh connection. This is a well-understood pattern that works with any media player.

---

## 3. Potential Improvements for Kondooit

### 3.1. Shared Core Crate for Native Clients (High Value, Future)

When Kondooit builds native clients, extract a shared `kondooit-p2p-core` crate:

```
kondooit-p2p-core/        ← Shared: connection logic, protocol, stream handling
kondooit-iroh/            ← Server sidecar: depends on kondooit-p2p-core
kondooit-runtime/         ← Browser WASM: separate (browser constraints differ)
kondooit-android/         ← Future: depends on kondooit-p2p-core via JNI/uniffi
kondooit-ios/             ← Future: depends on kondooit-p2p-core via Swift FFI
```

This ensures protocol parity, eliminates duplicated HTTP parsing logic, and makes it easier to add new native clients.

**Priority:** High, but only when native client development begins. The browser WASM runtime should remain separate because browser iroh constraints (relay-only, no UDP) are fundamentally different.

### 3.2. Persistent Connection Reuse (Already Implemented)

Kondooit's WASM runtime already implements persistent connection reuse (`get_or_reconnect` in `wasm.rs`). The connection is established once and reused for all subsequent `http_fetch` calls. This is good — it avoids the overhead of establishing a new iroh connection per request.

**Status:** No change needed.

### 3.3. Binary Data Corruption in Tunnel Mode — Confirmed Bug and Fix

**Status: FIXED (2026-10-05)**

#### When video segments go through the tunnel

The question of when binary video data actually flows through the iroh tunnel is important — Kondooit's architecture (ADR-0014, ADR-0017) defaults to direct CDN delivery for Debrid sources, which bypasses the tunnel entirely.

The delivery decision happens in `PlayerPage.tsx` during stream initialization:

1. The player calls `GET /api/hls/{streamId}/info` to get stream metadata.
2. If `info.direct_url` is present AND `info.needs_processing` is false, the player sets `video.src = info.direct_url`. The browser fetches video directly from the provider CDN — no tunnel involvement, no bug.
3. If `info.needs_processing` is true (or `direct_url` is absent), the player falls through to the HLS path: it loads `/api/hls/{streamId}/master.m3u8` via hls.js, and when `isConnected()` is true, hls.js uses `TunnelHlsLoader` to fetch both the manifest and the video segments through the iroh tunnel.

**The bug is encountered when:**
- A remote client (connected over iroh) plays content that needs **remuxing** (e.g., MKV/HEVC content that needs to be repackaged as HLS/fMP4 for the browser) or **transcoding** (e.g., HEVC video or AC3 audio that the browser cannot play natively).
- The server generates HLS segments (MPEG-TS `.ts` or fMP4 `.m4s` files) and serves them through the `/api/hls/{streamId}/` endpoints.
- The `TunnelHlsLoader` fetches these binary segments through `http_fetch`, where they are corrupted by the UTF-8 string conversion.

**The bug is NOT encountered when:**
- Direct playback works: the source codec is browser-compatible, the server returns a `direct_url`, and the browser fetches from the CDN directly. The tunnel carries only the control traffic (API calls, metadata, stream info).
- The client is on the local network (not in tunnel mode). Local clients use normal `fetch()` and are unaffected.

**Typical scenario:** A remote user tries to watch an HEVC-encoded movie from a Debrid provider. The browser cannot play HEVC natively, so the server must transcode to H.264/HLS. The HLS manifest (`.m3u8`) loads fine through the tunnel (it's text), but when hls.js requests the video segments (`.ts` or `.m4s`), the binary segment bytes are corrupted by `String::from_utf8_lossy`, and playback fails or produces garbled video.

#### Root cause

In `kondooit-runtime/src/wasm.rs`, the `http_fetch` function:
1. Read the raw HTTP response into `Vec<u8>` (correct)
2. Converted to `String` via `String::from_utf8_lossy()` — **this replaces invalid UTF-8 byte sequences with U+FFFD (0xEF 0xBF 0xBD), irreversibly destroying binary data**
3. Parsed headers and body as strings
4. Returned a JSON string with `"body": "..."` 

On the TypeScript side (`tunnel.ts`), `tunnelFetch` parsed the JSON and passed `parsed.body` (a string) to `new Response()`. For binary data, this produced corrupted bytes.

#### Fix applied

**WASM side (`kondooit-runtime/src/wasm.rs`):**
- Replaced `parse_http_response(&str)` with `parse_http_response_bytes(&[u8])` that operates on raw bytes throughout.
- The new function splits headers from body using byte-level search (`find_subslice`), parses headers as UTF-8 (headers are always text), and decodes chunked transfer encoding at the byte level (`decode_chunked_bytes`).
- After extracting the body bytes, it checks whether the body is valid UTF-8:
  - **Valid UTF-8 (text responses — JSON, HLS manifests):** returns `{"body": "...", "is_binary": false}` — no encoding overhead, same as before.
  - **Invalid UTF-8 (binary responses — video segments):** returns `{"body_b64": "...", "is_binary": true}` — base64-encodes the body. This preserves binary data perfectly with ~33% size overhead, which is acceptable for the rare case of binary content through the tunnel.

**TypeScript side (`web/src/tunnel.ts`):**
- `tunnelFetch` now checks `is_binary` in the response:
  - If `true`, decodes `body_b64` via `atob()` into a `Uint8Array` and passes it to `new Response()`.
  - If `false`, uses `body` as a string (unchanged behavior).

**Dependency:** Added `base64 = "0.22"` to `kondooit-runtime/Cargo.toml`.

**What was NOT changed:**
- The server sidecar (`kondooit-iroh/src/tunnel.rs`) was not modified. It already tunnels raw bytes bidirectionally between the iroh stream and the TCP connection to Litestar. The corruption was purely on the client-side WASM response parsing, not the server-side tunnel.
- The `TunnelHlsLoader` was not modified. It already calls `res.arrayBuffer()` for binary responses and `res.text()` for text responses — the fix is transparent to it because `new Response(Uint8Array)` produces a valid Response that `arrayBuffer()` can read correctly.

**Trade-offs of the base64 approach:**
- Base64 encoding adds ~33% size overhead to binary responses. This is acceptable because binary content through the tunnel (remuxed/transcoded HLS segments) is not the common case — direct CDN delivery is the default.
- An alternative approach would be to return the body as a `Uint8Array` directly from WASM via `wasm_bindgen` (avoiding base64 entirely). This would be more efficient but requires restructuring the return type to be a `JsValue` object rather than a JSON string. The base64 approach was chosen because it is a minimal, low-risk change that fits the existing JSON-string return contract.

#### Previous known limitations (remaining)

- The server's `proxy_to_tcp` reads the entire request body via `tokio::io::copy` before reading the response — this buffers the full request in memory. For large POST bodies (e.g., file uploads), this could be memory-intensive.
- Chunked transfer decoding is duplicated in both the server and client. If a shared core crate is created (3.1), consolidate the HTTP parsing into one implementation.

### 3.4. Connection Health and Reconnection (Medium Value)

Kondooit's WASM runtime has basic reconnection logic (`get_or_reconnect` checks `close_reason()` and reconnects if the connection is closed). However, there is no:
- Proactive health checking (pinging the server periodically)
- Connection quality monitoring (tracking latency, packet loss)
- Graceful degradation when the relay is slow

Mydia's shared core crate likely handles these concerns in one place for both server and client. Without seeing the source, we cannot confirm what specific health-check patterns they use.

**Recommendation:** Add a periodic ping/health check to the WASM runtime. If the connection is degraded, surface this to the UI. This is especially important for media playback — a stalled iroh connection mid-stream is a poor user experience.

### 3.5. Self-Hosted Relay (Operational, Future)

Mydia operates their own relay. Kondooit uses n0 public relays. As Kondooit grows:
- Self-hosting a relay gives control over bandwidth and latency
- The sidecar's relay configuration is already exposed through the control API
- This is an operational change, not an architectural one

**Priority:** Low, operational concern. Not needed until relay bandwidth becomes a bottleneck.

### 3.6. Protocol Versioning (Low Value, Future)

Kondooit's ALPN is `kondooit/tunnel/0`. The `/0` suffix allows future protocol versions (`kondooit/tunnel/1`, etc.). This is good practice.

Mydia's AGENTS.md does not mention protocol versioning explicitly, but the shared crate approach means version negotiation happens at the crate level — both sides compile against the same version.

**Recommendation:** When native clients are built with a shared core crate, consider adding a protocol version handshake (beyond just the ALPN) so that mismatched client/server versions can detect incompatibility early and provide a helpful error message.

---

## 4. What Kondooit Should NOT Copy from Mydia

### 4.1. NIF Instead of Sidecar

Mydia's Rustler NIF approach works for Elixir but is not appropriate for Kondooit's Python server. Python has no equivalent to Rustler, and bridging Tokio (iroh's async runtime) with asyncio (Litestar's) would add significant complexity. The sidecar model is the right choice for Kondooit.

### 4.2. All-Media-Through-P2P

Mydia serves all media through the p2p connection. This makes sense for local media files but is wasteful for Kondooit's Debrid use case, where the client can fetch directly from the provider CDN. Kondooit's direct-delivery strategy (ADR-0014) is the better approach for this use case.

### 4.3. Flutter Client Architecture

Mydia uses Flutter for its client. Kondooit's web client is React + TypeScript, which is the right choice for the browser. When native clients are built, Flutter is one option, but the choice should be made independently based on Kondooit's requirements (Android TV support, platform coverage, team expertise).

---

## 5. Summary

Mydia's most valuable pattern for Kondooit is the **shared core crate** — writing the iroh connection logic, protocol handling, and stream dispatch once in pure Rust, then wrapping it for different platforms (server NIF, client FFI). This becomes directly applicable when Kondooit builds native clients.

The second most valuable pattern is the **local proxy in the client** — a local HTTP server that mediates between the media player and the iroh connection. This is the standard approach for native clients and will likely be needed for Kondooit's Android/TV clients.

Kondooit's current architecture (sidecar + WASM + HTTP tunnel + direct CDN delivery) is well-suited for the browser use case and the Debrid media model. The main gap is the lack of a shared core crate, which should be addressed when native client development begins.

---

## Open Questions (Would Require Source Code Inspection)

1. What is the exact wire protocol Mydia uses over iroh? (HTTP? Custom binary? iroh blobs?)
2. How does the Flutter local proxy work in detail? (Local HTTP server? Direct stream piping?)
3. Does Mydia support direct CDN delivery, or is all media tunneled through p2p?
4. What connection ticket format does Mydia use?
5. How does Mydia handle connection health and reconnection?
6. What iroh version does Mydia use?
7. Does Mydia's plugin system interact with iroh networking, or is it purely for content/metadata?

These questions can be answered by inspecting `native/mydia_p2p_core/src/` if the repository is cloned locally.
