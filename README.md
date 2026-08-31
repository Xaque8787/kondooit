# Kondooit

A unified media system that discovers, organizes, and resolves content
from multiple provider types through a coherent interface.

## What It Does

Kondooit presents content from metadata providers (TMDB, TVDB) and
resolves playable sources from source providers (debrid services, Usenet,
IPTV) — all through a single web interface. No media import step. No
manual library building. Content appears because providers know about it.

## Architecture

Kondooit is a platform that orchestrates provider capabilities, not a
monolithic media application. The core application provides:

- Content discovery and aggregation from metadata providers
- Source discovery orchestration and resolution pipeline
- Provider management (configuration, priority, enable/disable)
- Module loading for source resolvers (ADR-0012)
- User authentication and state

### Provider Types

```
Bundled Providers                    Modular Source Resolvers (ADR-0012)
├── MetadataProvider                 └── Hash Aggregator (Torrentio-protocol)
│   ├── TMDB                             (future: community scrapers,
│   └── TVDB                              self-hosted hash databases)
└── SourceProvider
    ├── TorBox (debrid)
    ├── Easynews (Usenet)
    └── IPTV (M3U / Xtream Codes)
```

**Metadata providers** and **source providers** are bundled with the
core. They are paid services with official, stable APIs — the user
configures credentials and enables them. This is the same pattern for
both: clean interface, capability declaration, registered at startup.

**Source resolvers** (hash aggregators, community-contributed scrapers)
are **installable modules** loaded through the module system defined in
ADR-0012. These aggregate content availability information from the
broader internet and benefit from distribution separation.

### Module Architecture (Source Resolvers Only)

Source resolver modules are self-contained packages:

```
modules/
  hash-aggregator/
    manifest.json       — identity, capabilities, config schema
    resolver.py         — SourceResolver implementation
```

The core application discovers and loads resolver modules from
configured paths. During development, modules live in this repository.
In production, they can be loaded from local directories or (future)
remote URLs.

Bundled providers (TorBox, Easynews, IPTV) live in
`server/kondooit/infrastructure/providers/` alongside metadata
providers — no module loader involved.

### Layer Boundaries

```
API Layer (Litestar)
    ↓
Application Layer (orchestration, services, ports)
    ↓
Domain Layer (content entities, source entities, release parsing)
    ↓
Infrastructure Layer (database, provider implementations, module loader)
```

The domain layer has no infrastructure dependencies. Provider
implementations depend inward. The application layer orchestrates through
interfaces, never through concrete provider types.

## Technology

- **Server:** Python, Litestar, SQLAlchemy, PostgreSQL
- **Web client:** React, TypeScript, Vite, Tailwind CSS
- **Deployment:** Docker Compose
- **Database:** PostgreSQL (via Docker in development)

## Development

```bash
docker compose up --build
```

This starts the server, database, and web client. The web interface is
accessible at `http://localhost` (port 80). The API is accessible at
`http://localhost:8000`.

On first access, you will be prompted to create an administrator account
and configure at least one metadata provider (TMDB recommended — get an
API key at https://www.themoviedb.org/settings/api).

## Repository Structure

```
server/             — Python backend (Litestar API server)
web/                — React frontend
modules/            — Source resolver modules (ADR-0012, loaded by module system)
architecture/       — Architectural principles
decisions/          — Architectural Decision Records (ADRs)
roadmap/            — Development milestones
research/           — Analysis and planning documents
vision/             — System vision
docs/               — Developer documentation
```

## Current Status

**v0.0.1 — Complete.** Server foundation, provider-driven content
discovery, admin authentication, TMDB + TVDB metadata providers, web
client with search/browse/detail views.

**v0.0.2 — In Progress.** Phase 1: bundled source providers (TorBox,
Easynews, IPTV). Phase 2: modular source resolvers (hash aggregators).
See `roadmap/ROADMAP.md`.

## Key Decisions

The `decisions/` directory contains all accepted ADRs. Key ones:

- **ADR-0002:** Provider vs. source distinction (three-level hierarchy)
- **ADR-0003:** Core owns canonical identity (external IDs are evidence)
- **ADR-0009:** Provider-driven content discovery (no import step)
- **ADR-0010:** Provider capability declaration (providers declare what they can do)
- **ADR-0012:** Source resolvers as installable modules (hash aggregators, community scrapers — not paid-service providers)
