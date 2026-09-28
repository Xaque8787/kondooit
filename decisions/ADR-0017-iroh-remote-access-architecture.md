# ADR-0017: iroh remote access architecture — sidecar endpoint, browser runtime, and delivery modes

- **Status:** Accepted
- **Date:** 2026-09-28
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "What does the Kondooit application protocol look like concretely?" (partially), "How should multiple networking providers be represented behind one interface?" (partially), iroh connectivity validation deferred from v0.0.1

## Context

ADR-0007 established that iroh is the default remote transport and the application protocol is transport-independent. ADR-0014 established that direct delivery (client fetches from provider CDN) is the default playback mode, with server proxy as a fallback for remux/transcode. ADR-0015 defined polymorphic stream handles that carry either a direct URL or a proxy identifier.

None of these ADRs specified how iroh is concretely integrated into the Kondooit server, how remote browser clients connect, or how the delivery mode decision changes when the client is connected over iroh rather than on the local network.

The v0.0.1 roadmap deferred iroh connectivity validation. This ADR defines the concrete architecture for iroh-based remote access so that implementation can proceed.

### The product goal

A Kondooit administrator enables remote access in settings. Kondooit generates a connection link. The administrator copies that link and sends it to a household member (or uses it themselves from outside the home). The recipient opens the link in a browser. The browser connects to the Kondooit server through an iroh relay — no port forwarding, no domain name, no VPN, no networking knowledge required.

### Key constraints

1. **Browser networking limitations.** Browsers cannot open raw UDP/QUIC sockets. Browser-based iroh endpoints communicate exclusively through relays using WebSocket/WebTransport. Native clients (Android, iOS, TV apps — future) can potentially establish direct iroh connections via NAT hole-punching, bypassing the relay for media delivery.

2. **Relay bandwidth.** When media bytes flow through the relay, the relay carries the full stream bitrate (4–80+ Mbps depending on quality). This is acceptable for control traffic but becomes expensive at scale for media. Direct delivery to CDN-capable sources (Debrid, Easynews) avoids this entirely.

3. **Residential upload bandwidth.** Even when the relay is not involved (native clients with direct iroh connections), the home server's upload bandwidth is a bottleneck for proxied streams. ADR-0014 already addresses this — direct delivery bypasses the server's upload link.

4. **The server must remain accessible over plain HTTP.** iroh is an additional transport, not a replacement. LAN clients continue using HTTP directly. The iroh connection tunnels the same HTTP API — it does not introduce a separate protocol.

## Decision

### 1. Architecture overview

```
                         INTERNET
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
     GitHub Pages                    iroh relay
     (static files)                  (n0 public)
     ─────────────                   ──────────
     kondooit-runtime                     │
     index.html                           │
     app.js                               │
     iroh.wasm                            │
             │                             │
             │     iroh (encrypted)        │
             └──────────────┬──────────────┘
                            │
                    ┌───────▼───────┐
                    │  HOME SERVER  │
                    │               │
                    │  Kondooit     │
                    │  ├── Litestar │  ← HTTP API (port 8000)
                    │  └── iroh     │  ← sidecar (tunnels to 8000)
                    │      sidecar  │
                    └───────────────┘
```

Three components:

- **Kondooit server** — runs the iroh sidecar alongside the Litestar HTTP server within the same Docker container. The sidecar manages the iroh identity, connects to the relay, accepts incoming iroh connections, and tunnels them as HTTP requests to Litestar on localhost.

- **Browser runtime** — a static page hosted on GitHub Pages (initially at a GitHub Pages URL, eventually at `connect.kondooit.com`). It loads iroh WASM, parses the connection ticket from the URL fragment, establishes an iroh connection to the Kondooit server through the relay, and tunnels HTTP requests over that connection. It is not a Kondooit client — it is a connection bootstrapper. Once connected, it loads the actual Kondooit web UI from the server.

- **iroh relay** — initially the n0 project's public relay infrastructure. The relay facilitates connections between browser endpoints and the Kondooit server. All traffic through the relay is end-to-end encrypted between the browser and the server; the relay cannot read it.

### 2. iroh sidecar (Rust binary)

The iroh endpoint runs as a small Rust binary (`kondooit-iroh`) within the Kondooit Docker container, managed as a subprocess by the Python server or the container entrypoint.

**Responsibilities:**

- Generate and persist the iroh node identity (secret key) on first startup
- Connect to the configured relay (default: n0 public relay)
- Accept incoming iroh connections from browser and native clients
- For each incoming iroh bidirectional stream: open a TCP connection to localhost:8000 (Litestar) and pipe bytes bidirectionally — functioning as an HTTP-over-iroh tunnel
- Expose a local Unix socket control API for the Python server to:
  - Query endpoint status (online/offline, relay connected, endpoint ID)
  - Generate connection tickets (NodeTicket containing endpoint ID and relay info)
  - Read/update relay configuration

**Why a Rust sidecar rather than Python iroh bindings:**

- iroh is a Rust library natively. Using it from Rust provides the most mature, reliable, and performant integration.
- The Python server does not need to know iroh exists. It receives standard HTTP requests on port 8000 regardless of whether they arrived over TCP (LAN) or were tunneled from iroh. This preserves the transport-independence principle (ADR-0007).
- No need to bridge async runtimes (Tokio in iroh vs asyncio in Python) or maintain iroh-ffi Python binding compatibility.
- The sidecar binary is small (a few MB) and compiled once in a Docker multi-stage build. No Rust toolchain in the runtime image.
- The control API over Unix socket is a narrow, stable interface — a few JSON messages for status, ticket generation, and configuration.

**Identity persistence:**

The iroh secret key is persisted at a path within the Kondooit data volume:

```
/data/iroh/secret-key
```

The identity survives container restarts. If the identity is lost (volume deleted), a new identity is generated and all previously shared connection links become invalid. This is acceptable — it is equivalent to losing a TLS private key.

The identity file must never be exposed through the API, logged, or included in backups that leave the server operator's control.

### 3. Browser runtime (static page)

The browser runtime is a small static page hosted on GitHub Pages. It is NOT a Kondooit client application. It is a connection bootstrapper.

**What it contains:**

- `index.html` — minimal HTML with a connection status UI
- `app.js` — JavaScript/TypeScript that: parses the URL fragment, initializes the iroh WASM endpoint, connects to the Kondooit server through the relay, and once connected, either loads the Kondooit web UI into the page or redirects the browser to interact through the tunnel
- `iroh.wasm` — the iroh browser endpoint WASM module (from the iroh project's published browser builds)

**What it does NOT contain:**

- Any Kondooit application code (no React, no UI components, no API client)
- Any server-specific configuration
- Any authentication logic (authentication happens over the iroh connection, handled by the Kondooit server)

**The connection flow:**

```
1. User opens: https://connect.kondooit.com/#<bootstrap-payload>
2. Runtime loads, parses fragment (never sent to GitHub's server)
3. iroh WASM initializes a browser endpoint
4. Browser endpoint connects to the Kondooit server via the relay
   using the ticket from the bootstrap payload
5. Connection established — encrypted tunnel to Kondooit
6. Runtime loads the Kondooit web UI through the tunnel
7. User interacts with Kondooit normally (auth, browse, play)
```

**The bootstrap payload:**

The URL fragment contains a versioned, base64url-encoded JSON payload:

```json
{"v": 1, "ticket": "<iroh-node-ticket>"}
```

- `v` — payload format version. Allows future changes without breaking old links.
- `ticket` — the iroh NodeTicket string, which encodes the server's endpoint ID and relay information. This is everything the browser needs to establish the iroh connection.

The payload intentionally does NOT contain:

- Expiration timestamps (the server controls authorization, not the URL)
- Authentication credentials (auth happens after connection)
- Server names or metadata (learned after connection via the server handshake)

The fragment (`#`) is used rather than query parameters (`?`) because the fragment is never sent to the hosting server (GitHub Pages). GitHub has no visibility into which Kondooit servers exist or who is connecting.

**Deployment:**

The runtime lives in `kondooit-runtime/` within this repository. It has zero import dependencies on `server/` or `web/`. It is a self-contained directory of static files (or a minimal build step if TypeScript is used).

Deployment to GitHub Pages is a separate CI job from the server Docker image build. The runtime is versioned alongside the main project but deployed independently.

### 4. Connection ticket generation and the two-layer credential model

**Layer 1: Transport reachability (iroh ticket)**

The iroh ticket tells a client how to reach the Kondooit server's iroh endpoint. It contains the endpoint ID and relay information. It is analogous to knowing a server's IP address and port — it enables connection, not access.

A ticket is NOT an authentication credential. A client that connects using a ticket has established an encrypted transport channel. They have not authenticated to Kondooit.

**Layer 2: Application authentication (Kondooit login)**

After the iroh connection is established, the client must authenticate to Kondooit using the standard authentication mechanism (currently: admin username + password). This happens over the encrypted iroh tunnel, exactly as it happens over HTTPS on the LAN.

**Why two layers:**

- Revoking application access (disabling an account, changing a password) does not require regenerating the iroh identity or invalidating all connection links.
- Multiple household members can use the same connection link but authenticate with different Kondooit accounts.
- A leaked connection link allows someone to reach the server (like knowing its IP address) but not to use it. The iroh connection itself is encrypted and authenticated at the transport level (the server's iroh identity is verified by the client), so a MITM cannot intercept the subsequent login.
- Connection links remain stable for the lifetime of the iroh identity. They do not need rotation or expiration — application-level auth provides the access control.

**Ticket generation UI:**

```
Settings → Remote Access

[✓] Enable remote access

Relay:
  (•) Automatic (n0 public relay)
  ( ) Custom relay

Status: ● Connected to relay

Browser Connection:
  https://connect.kondooit.com/#eyJ2IjoxLCJ0aWNr...
  [Copy Link]  [Regenerate]
```

"Regenerate" creates a new iroh identity, invalidating all previous links. This is a destructive action (equivalent to changing the server's address) and should require confirmation.

### 5. Delivery mode for remote clients

ADR-0014 established the delivery fallback chain: direct → remux → transcode. ADR-0015 defined stream handles that carry either a direct URL or a proxy handle. This ADR extends the delivery decision to account for remote iroh clients.

**The delivery matrix:**

```
                         LAN client          Remote client (iroh)
                         ──────────          ────────────────────
Direct-playable source   Direct delivery     Direct delivery (handoff)
                         (client plays       (client fetches from
                          from CDN)           provider CDN directly)

Remux needed             Server proxy        Depends on profile setting:
                         (localhost is         • Handoff disabled: proxy
                          fast)                  through iroh tunnel
                                               • Handoff enabled: N/A
                                                 (remux requires server)

Transcode needed         Server proxy        Server proxy through iroh
                         (same)              (transcoding requires server)

Local file source        Server proxy        Server proxy through iroh
                         (file is on         (file is only on server)
                          the server)
```

**The key insight:** For CDN-backed sources (Debrid, Easynews) that are directly playable by the client, a remote iroh client should receive the CDN URL and fetch directly — exactly as a LAN client would. The iroh connection carries only the control traffic (browse, search, resolve source, receive stream handle with `mode: "direct"`). Media bytes flow directly from the CDN to the browser over the regular internet. The relay sees none of the media traffic.

**When proxy through iroh is required:**

- The source needs remuxing or transcoding (server must process the stream)
- The source is a local file on the server
- The source URL requires server-side authentication that cannot be safely shared (though ADR-0014 considers this acceptable in the household model)

**When proxy through iroh is optional but user-selectable:**

A profile-level preference controls whether remote playback is proxied through the server even when direct delivery is possible:

- **"Allow direct delivery" (default: on)** — Remote clients receive CDN URLs for compatible streams. Fastest, lowest relay/server bandwidth usage. The browser fetches directly from the provider CDN.
- **"Force proxy for remote playback" (off by default)** — All streams for remote clients are proxied through the Kondooit server and iroh tunnel. Uses server upload bandwidth and relay bandwidth. Enables: all traffic appearing to originate from the Kondooit server (privacy from CDN providers), centralized bandwidth monitoring, consistent transcoding behavior regardless of client location.

This preference extends the existing "force proxy" admin setting from ADR-0014 to the profile level. The server's delivery decision logic (ADR-0015) gains one additional input: `is_remote_client AND profile.force_proxy_remote`.

### 6. Protocol: HTTP tunneled over iroh

The Kondooit application protocol over iroh is HTTP. Not "HTTP-like." Not a custom binary protocol. Actual HTTP request/response pairs tunneled over iroh bidirectional streams.

**How it works:**

1. The browser runtime establishes an iroh connection to the Kondooit server.
2. For each HTTP request the browser needs to make (API call, page load, stream fetch), the runtime opens an iroh bidirectional stream.
3. The runtime writes a standard HTTP request (method, path, headers, body) into the stream.
4. The sidecar receives the stream, opens a TCP connection to Litestar on localhost:8000, and forwards the HTTP request.
5. Litestar processes the request normally (it does not know the request came from iroh).
6. Litestar's HTTP response flows back through the TCP connection → sidecar → iroh stream → browser runtime.
7. The browser runtime receives the HTTP response and delivers it to the calling code.

**Why HTTP tunneling rather than a custom protocol:**

- The Litestar API already exists and handles all Kondooit functionality. Tunneling HTTP means zero changes to the API layer.
- The web client (`web/`) already speaks HTTP to the API. The iroh tunnel is transparent — the web client works identically whether loaded over LAN HTTP or over the iroh tunnel.
- Authentication, CORS, middleware, rate limiting — all existing HTTP infrastructure works without modification.
- Stream handles (ADR-0015) work unchanged. A proxy-mode handle returns bytes through `GET /api/streams/{id}`, which works over the tunnel exactly as it does over LAN HTTP.
- Testing is simplified: any HTTP client can test the API directly; the iroh tunnel is a transport concern only.

**What the browser runtime provides to the web UI:**

The runtime intercepts HTTP requests from the Kondooit web UI and routes them through the iroh tunnel instead of direct HTTP. This can be implemented as:

- A Service Worker that intercepts `fetch()` calls to `/api/*` and routes them through the iroh tunnel
- Or: the runtime loads the web UI in an iframe and proxies all requests
- Or: the runtime acts as a local HTTP proxy and the web UI is configured to use it

The specific mechanism is an implementation detail. The architectural requirement is: the web UI code (`web/`) does not need to know about iroh. It makes standard `fetch()` calls and they arrive at the Kondooit server.

### 7. Server-side integration

The iroh sidecar is infrastructure. It lives behind the transport boundary established by ADR-0007 and ADR-0008.

**Where iroh code lives:**

```
server/
  kondooit/
    infrastructure/
      iroh/
        sidecar.py      ← manages the sidecar subprocess lifecycle
        control.py       ← communicates with the sidecar's Unix socket API
    api/
      remote_access.py   ← HTTP endpoints for the settings UI
                           (enable/disable, get status, generate ticket,
                            configure relay)
```

The domain layer has no knowledge of iroh. The application layer has no knowledge of iroh. The API layer has endpoints for the remote access settings UI. The infrastructure layer manages the sidecar process and communicates with it.

**Sidecar source code:**

```
kondooit-iroh/
  src/
    main.rs            ← entry point, CLI args
    endpoint.rs        ← iroh endpoint management, identity persistence
    tunnel.rs          ← HTTP tunneling (iroh stream ↔ TCP to localhost)
    control.rs         ← Unix socket control API
  Cargo.toml
```

This directory is within the main repository but produces a separate build artifact (a compiled binary). The Docker multi-stage build compiles it in a Rust builder stage and copies the binary into the final Python runtime image.

**Docker integration:**

```dockerfile
# Stage 1: Build Rust sidecar
FROM rust:1-bookworm AS iroh-builder
WORKDIR /build
COPY kondooit-iroh/ .
RUN cargo build --release

# Stage 2: Build Python server (existing)
FROM python:3.13-bookworm
# ... existing Python setup ...
COPY --from=iroh-builder /build/target/release/kondooit-iroh /usr/local/bin/
```

The entrypoint starts both processes. The sidecar is optional — if remote access is disabled in settings, the sidecar is not started. The Kondooit server functions normally over HTTP without the sidecar running.

### 8. What is NOT decided by this ADR

- **The Kondooit protocol handshake over iroh.** The initial implementation tunnels raw HTTP. A future optimization could add a lightweight handshake (server hello, protocol version negotiation) before HTTP tunneling begins. This is deferred until the basic tunnel works.

- **Peer authorization (iroh peer ID tracking).** The vision includes tracking which browser iroh endpoints have connected and allowing per-device revocation. This is a future capability. The initial implementation uses standard Kondooit authentication (username + password) over the tunnel.

- **Custom relay hosting.** The initial implementation uses the n0 public relay. Self-hosted relay support is a configuration option that can be added later without architectural changes (the sidecar's relay configuration is already exposed through the control API).

- **Native client iroh integration.** This ADR focuses on browser clients (iroh WASM). Native clients (Android, iOS, TV) could use native iroh SDKs with direct connections (bypassing the relay). The architecture supports this — the sidecar accepts any iroh connection, not just browser ones — but native client implementation is out of scope.

- **Media streaming directly over iroh streams.** The initial implementation tunnels HTTP, including media byte delivery for proxy-mode streams. A future optimization could use dedicated iroh streams for media delivery with flow control tuned for streaming. This is deferred — HTTP tunneling works first, optimize later.

## Rationale

- **Zero-config remote access.** The primary product goal. A user enables remote access, copies a link, sends it. No port forwarding, no domain, no DNS, no VPN, no networking knowledge. iroh + relays provide this.

- **Transport transparency.** By tunneling HTTP over iroh, the entire existing API and web client work without modification. The iroh layer is invisible to everything above the infrastructure boundary.

- **Rust sidecar over Python bindings.** iroh is a Rust-native library. Using it from Rust gives the most mature, performant, and reliable integration. The sidecar model keeps iroh completely out of the Python codebase, avoids async runtime bridging, and provides a clean process boundary. The cost (Docker multi-stage build, subprocess management, Unix socket IPC) is modest and well-understood.

- **Static browser runtime.** The runtime is deliberately minimal — a connection bootstrapper, not a client application. It has no framework dependencies, no build complexity, and no coupling to the Kondooit application code. It can be hosted on any static file server (GitHub Pages, Cloudflare Pages, S3).

- **Two-layer credentials.** Separating transport reachability (iroh ticket) from application access (Kondooit login) provides clean security boundaries, stable connection links, and independent revocation. A leaked link is equivalent to a leaked IP address, not a leaked password.

- **Direct delivery for remote clients.** ADR-0014's bandwidth analysis is even more compelling for remote clients: proxying a 25 Mbps stream through the relay wastes relay bandwidth and adds latency when the browser can fetch directly from the provider CDN. Direct delivery should be the default for remote clients, with proxy available as an opt-in for users who want all traffic routed through Kondooit.

## Alternatives considered

- **Python iroh bindings (in-process).** Would eliminate the sidecar subprocess and Unix socket IPC. Rejected because: iroh-ffi Python bindings are less mature than the native Rust SDK; bridging Tokio (iroh) and asyncio (Litestar) adds complexity; routing iroh-received bytes into Litestar's ASGI pipeline requires non-trivial integration; and any iroh crash would take down the entire Python server. The sidecar model isolates these concerns.

- **Docker sidecar (separate container).** Running the iroh endpoint as a separate Docker service rather than a subprocess within the same container. Rejected because: it complicates the `docker compose up` experience (two services instead of one), requires container-to-container networking configuration, makes identity persistence and control API communication more complex, and contradicts the "just start the container" product goal. A subprocess within the same container is simpler for the user.

- **Custom binary protocol over iroh.** Designing a Kondooit-specific binary protocol (protobuf messages, custom framing) rather than tunneling HTTP. Rejected because: it would require reimplementing API routing, authentication, middleware, and every API endpoint in a parallel protocol; the web client would need a protocol adapter; and the development/debugging experience would be significantly worse. HTTP tunneling gives us the full existing stack for free. A custom protocol can be considered as a future optimization if HTTP tunneling proves to have unacceptable overhead.

- **WebRTC instead of iroh.** WebRTC provides browser-to-server connectivity with NAT traversal. Rejected because: iroh is already an accepted technology choice (ADR-0008), WebRTC's data channels have lower throughput limits than iroh streams, WebRTC's complexity (ICE, STUN, TURN, SDP) is higher than iroh's ticket model, and iroh provides a unified transport for both browser and native clients.

- **Cloudflare Tunnel / Tailscale / other overlay networks.** Third-party services that provide remote access without port forwarding. Rejected because: they introduce external service dependencies, require accounts with third parties, may have bandwidth limits or costs, and contradict the self-hosted philosophy. iroh's relay infrastructure is open-source and can be self-hosted if desired.

- **No profile-level proxy toggle; always use the ADR-0014 default.** Would simplify the delivery decision. Rejected because: some users have legitimate reasons to want all remote traffic proxied through their server (privacy from CDN providers, bandwidth monitoring, consistent behavior). The toggle is a simple addition to the existing delivery decision logic and respects user choice.

## Consequences

- The Kondooit Docker image gains a compiled Rust binary (`kondooit-iroh`). The Dockerfile requires a multi-stage build with a Rust builder stage.
- The server gains infrastructure-layer code for managing the sidecar subprocess and communicating over the Unix socket control API.
- The API layer gains endpoints for the remote access settings UI (enable/disable, status, ticket generation, relay configuration).
- The web UI gains a Remote Access settings page.
- The repository gains a `kondooit-iroh/` directory containing the Rust sidecar source and a `kondooit-runtime/` directory containing the static browser runtime.
- Identity persistence requires the data volume to include an `iroh/` subdirectory.
- The profile domain entity gains a `force_proxy_remote` preference. The stream handle delivery decision logic (ADR-0015) gains an additional input for remote client detection.
- The browser runtime must be deployed separately to a static hosting service (GitHub Pages initially). CI/CD must handle this as a distinct deploy target.
- The Kondooit server remains fully functional without iroh. If remote access is disabled or the sidecar is not running, all existing HTTP functionality is unaffected.

## Relationship to other ADRs

- **ADR-0007** (iroh default transport): This ADR is the concrete implementation architecture for ADR-0007's transport-independence principle. The iroh sidecar is the transport implementation; the HTTP tunnel preserves the transport-independent API.
- **ADR-0008** (Technology baseline): iroh is listed as the networking technology. This ADR specifies that it runs as a Rust sidecar rather than through Python bindings — a refinement of how the technology is integrated, consistent with the principle that iroh is infrastructure.
- **ADR-0014** (Direct delivery default): Extended to remote iroh clients. Direct delivery remains the default; the relay is not in the media path for CDN-backed sources.
- **ADR-0015** (Stream handle delivery modes): Extended with a profile-level `force_proxy_remote` preference that influences the delivery mode decision for remote clients.
- **ADR-0005** (Household model): The two-layer credential model (transport ticket + application auth) is designed for the household context. Connection links are shared among household members who each have their own Kondooit login.
