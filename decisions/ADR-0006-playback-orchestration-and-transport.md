# ADR-0006: Playback orchestration is core; stream transport is a core subsystem

- **Status:** Superseded
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** ADR-0014
- **Resolves:** "How should playback capabilities be represented?", "How should remote streams be proxied?", "How should transcoding fit into the architecture?"

## Context

The vision proposes two playback routing modes: server-resolves/client-retrieves, and server-resolves-and-proxies. The proxy mode (range requests, buffering, sessions, bandwidth, transcoding) is server-level streaming infrastructure, not something individual providers should implement. If each provider had to implement "how the server's HTTP proxy handles a byte-range seek," provider interfaces would be bloated and inconsistent.

## Decision

Responsibilities are split:

- **Source resolution** — provider responsibility. A provider answers "here is the playable resource."
- **Playback session** — core responsibility. The core owns playback orchestration: which source, which mode, which client, session lifecycle.
- **Stream transport** — core playback infrastructure. Range handling, buffering, sessions, bandwidth controls, and proxying belong to the server playback subsystem.
- **Transcoding** — a capability/provider that the playback system can invoke, not a property of each playback provider.

Flow:

```
Provider
   │ resolve source
   ▼
Playable Source
   │
   ▼
Playback Engine (core)
   │
   ├── direct playback
   │
   └── server proxy
           │
           ├── range requests
           ├── buffering
           ├── sessions
           ├── bandwidth controls
           └── potentially transcoding (invoked as a capability)
```

So: providers resolve sources; the server owns playback orchestration and server-side streaming. Server-side proxying is a playback capability of the server, not a provider responsibility.

## Rationale

Providers know how to resolve a playable resource from their upstream; they should not know how the server proxies bytes to a client. Centralizing transport in the core keeps provider interfaces small, makes proxy behavior consistent across all providers, and lets transcoding be invoked uniformly regardless of source.

## Alternatives considered

- **Providers implement their own proxy transport.** Rejected: bloats every provider, leads to inconsistent proxy behavior, and couples provider integrations to client transport concerns.
- **Proxy/transcoding is a separate top-level subsystem outside the core.** Rejected: playback orchestration and transport are tightly coupled; splitting them adds indirection without benefit.
- **Transcoding hard-coded into the playback engine.** Rejected: transcoding is a capability with multiple possible implementations (hardware/software, different codecs) and should be invokable, not built in.

## Consequences

- Provider playback interfaces return playable resources; they do not implement proxy transport.
- The core has a playback engine subsystem owning sessions, direct vs. proxy routing, range/buffering/bandwidth.
- Transcoding is modeled as an invokable capability/provider, not a property of playback providers.
- The two routing modes (direct, proxy) are modes of the playback engine, not separate provider interfaces.
- This refines principle 5 ("Playback is not necessarily core"): playback orchestration and transport are core; source resolution is a provider capability.
