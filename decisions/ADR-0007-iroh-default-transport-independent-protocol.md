# ADR-0007: iroh is the default remote transport; the application protocol is transport-independent

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should iroh-based connectivity be abstracted from conventional domain/reverse-proxy connectivity?", "What should the client/server protocol look like?" (transport aspect)

## Context

The vision lists iroh as a built-in connectivity mechanism and conventional domain/reverse-proxy as "also supported," but does not say whether iroh is the default or whether the client talks "iroh" directly. If iroh were embedded throughout the application, swapping or adding transports would be expensive.

## Decision

iroh is the **preferred/default remote transport**, but it is not the application protocol. The client communicates with the server through a Kondooit application protocol/API that is transport-independent. iroh is one transport underneath that protocol.

```
             Kondooit Protocol
                    │
          ┌─────────┴─────────┐
          │                   │
       iroh transport    HTTPS transport
          │                   │
          ▼                   ▼
       Server              Server
```

The client supports connection types: local network, iroh, HTTPS/reverse proxy. Default onboarding uses iroh (no domain, port forwarding, or static IP required). Advanced users can choose domain/reverse proxy; VPN/mesh may be added later.

**Principle:** The application protocol must remain transport-independent. iroh must not become deeply embedded throughout the application.

## Rationale

Making iroh the default gives the best zero-config remote experience (no port forwarding). Keeping the application protocol transport-independent means iroh can be swapped, augmented, or run alongside HTTPS without rewriting the app layer. This also future-proofs against new networking providers.

## Alternatives considered

- **iroh as the only transport.** Rejected: some deployments/users need or prefer conventional domain/reverse-proxy; excluding them is unnecessarily rigid.
- **iroh embedded directly in the application API.** Rejected: couples the whole application to one transport and makes adding transports expensive.
- **HTTPS as the default, iroh optional.** Rejected: loses the zero-config remote access that is a key product goal.

## Consequences

- The Kondooit application protocol is defined independently of any transport.
- A transport abstraction sits between the protocol and concrete transports (iroh, HTTPS, local).
- iroh is the default remote transport for onboarding; HTTPS is an advanced option.
- Adding a future transport (VPN/mesh) requires implementing the transport interface, not touching the application protocol.
- Networking providers are represented behind one interface (supports the broader provider/capability philosophy).
