# Mydia

**Repository:** https://github.com/getmydia/mydia
**Documentation:** https://docs.mydia.dev
**Status:** Early development (0.x.x)
**License:** (not verified — check repository)
**Last inspected:** 2026-10-05

## Overview

Mydia is a self-hosted media management platform for tracking, organizing, and monitoring movies and TV shows. It is built with Phoenix LiveView (Elixir) on the backend and Flutter for the cross-platform player client. It uses iroh for peer-to-peer remote access between the server and the Flutter player.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Elixir / Phoenix LiveView |
| Player client | Flutter (cross-platform: Android, Android TV, desktop) |
| P2P networking | iroh (Rust) |
| Server-side iroh integration | Rustler NIF wrapping a shared Rust crate |
| Client-side iroh integration | `flutter_rust_bridge` wrapping the same shared Rust crate |
| Metadata | Separate metadata-relay service (proxies TVDB/TMDB) |
| Deployment | Nix-based (NixOS examples provided) |

## Architecture (Confirmed from AGENTS.md)

### Key Components

1. **Core (Rust):** The shared networking logic is implemented in a pure Rust crate (`native/mydia_p2p_core`) on top of iroh. This ensures protocol parity between client and server. Both the server and the client compile and link against the same Rust code.

2. **Backend (Elixir):** The Phoenix app wraps the core crate using a Rustler NIF (`Mydia.P2p`). The backend acts as a permanent iroh node — it is always online, always connected to a relay, and accepts incoming connections from clients.

3. **Frontend (Flutter):** The player app wraps the same core crate using `flutter_rust_bridge`. It connects to the backend for discovery and control.

### Native Crates (from repo structure)

```
native/
  mydia_p2p/           ← Rustler NIF crate (Elixir FFI bridge)
  mydia_p2p_core/      ← Shared pure-Rust iroh networking logic
  mydia_plugin_macros/  ← Plugin system procedural macros
  mydia_plugin_sdk/     ← Plugin SDK for extensions
  mydia_subsync/        ← Subtitle synchronization (FFmpeg-based)
```

The `mydia_p2p_core` crate contains the actual iroh endpoint management, connection logic, and protocol handling. The `mydia_p2p` crate is the thin Rustler NIF wrapper that exposes this to Elixir. The Flutter client uses `flutter_rust_bridge` to call into the same `mydia_p2p_core` crate.

### Connectivity

- **Identity:** Every node has an Ed25519 keypair; the public key is its node ID.
- **Discovery:** Nodes publish signed records mapping their key to their current addresses and relay, distributed over DNS by iroh's default discovery service.
- **Transport:** QUIC over UDP, encrypted with TLS 1.3.
- **Relay:** Mydia operates their own relay; iroh's public relays are the fallback.
- **Media:** Media streams (HLS) are served over the p2p connection (via a local proxy in the client).

Notably, the AGENTS.md explicitly states: "There is no libp2p, no Kademlia DHT, no mDNS, no TCP, and no Noise handshake. An earlier revision of this file described that design; it was replaced by iroh."

### Metadata Relay Service

Mydia uses a companion service called **metadata-relay**:
- Proxies metadata requests to external services (TVDB, TMDB)
- Protects API keys by avoiding direct client-to-service connections
- Reduces rate limiting by centralizing API requests
- Developed alongside Mydia but deployed separately
- Multiple Mydia instances can share a single metadata-relay deployment

### Plugin System

Mydia has a plugin system (`mydia_plugin_sdk`, `mydia_plugin_macros`). Recent releases mention "Plugin Contract 1.5" and native Plex server migration to a bundled plugin. Plugins appear to provide "shelves" on the home screen ("Picked for you" rails powered by plugin shelves).

## What Was NOT Verified (Assumptions / Open Questions)

The following could not be confirmed by reading actual source code. These are based on the AGENTS.md description and repo structure only.

- **The exact wire protocol over iroh.** AGENTS.md says "HLS streams are served over the p2p connection (via a local proxy in the client)" but does not specify whether this is HTTP tunneled over iroh streams, a custom binary protocol, or iroh blobs. The source code in `native/mydia_p2p_core/src/` was not inspected.
- **How the Flutter client's local proxy works.** It is unclear whether the client spins up a local HTTP server that the Flutter media player points to, or whether it pipes bytes directly into a video player widget.
- **Whether media bytes flow through the relay or direct P2P.** For native clients with NAT hole-punching, direct P2P is likely. For browser clients (if any exist), relay-only is expected. Mydia's primary client is Flutter (native), so hole-punching should work.
- **Connection ticket format.** Whether Mydia uses iroh NodeTickets, raw node IDs, or a custom bootstrap payload.
- **Whether the Rustler NIF approach has any reliability issues.** Rustler NIFs run in the BEAM VM; a crash in the NIF could crash the Erlang process. This is a known trade-off vs. a sidecar subprocess model.
- **The specific iroh version used.** The `Cargo.toml` for `mydia_p2p_core` was not inspected.

## Relevance to Kondooit

See `research/mydia_research.md` for a detailed comparison with Kondooit's iroh architecture.
