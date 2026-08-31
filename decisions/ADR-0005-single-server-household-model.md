# ADR-0005: Single-server, multi-user household model

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should per-user permissions be modeled and enforced?" (scope aspect)

## Context

"Multi-user" could mean one household with profiles (Kodi/Jellyfin style) or true multi-tenancy with independent provider infrastructures per tenant. These imply very different designs for credential isolation, storage, and permissions. The vision mentions multiple users, profiles, and permissions but does not scope the tenancy model.

## Decision

The initial architecture is a **single-server, multi-user household model**, not a multi-tenant SaaS platform.

```
Server
│
├── Server configuration
│   ├── Debrid accounts
│   ├── IPTV accounts
│   ├── Metadata providers
│   └── Storage
│
├── User A
│   ├── profile
│   ├── history
│   ├── watchlist
│   └── permissions
│
├── User B
│   ├── profile
│   └── ...
│
└── User C
```

All users share the server's configured provider ecosystem. Users have granular permissions, for example:

- User A: local media ✓, Debrid ✓, IPTV ✓, acquisition ✓
- User B: local media ✓, IPTV ✓, acquisition ✗
- Guest: selected content ✓, provider configuration ✗, acquisition ✗

The architecture must not make future multi-tenancy impossible, but it must not optimize for it.

## Rationale

The initial product is a self-hosted household media server. Designing for tenant isolation adds complexity (separate provider infrastructures, per-tenant storage, credential hard isolation) that the initial product does not need. Keeping the model single-server/multi-user is simpler and sufficient.

## Alternatives considered

- **Multi-tenant SaaS from the start.** Rejected: unnecessary complexity for a self-hosted household product; would force per-tenant provider isolation and storage separation prematurely.
- **Single-user only.** Rejected: profiles, permissions, and per-user history are part of the vision.

## Consequences

- One server installation, one shared provider ecosystem, multiple users with profiles.
- Permissions are per-user and granular (browse, play, download, administer, etc.).
- Provider credentials are configured at server level, not per user.
- The design must not preclude future multi-tenancy (e.g., avoid baking "all users share all providers" so deeply that per-user provider scoping becomes impossible later), but must not build for it now.
- This decision should be revisited if the product direction shifts toward hosted/SaaS.
