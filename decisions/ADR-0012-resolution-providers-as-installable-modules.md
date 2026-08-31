# ADR-0012: Source resolvers as installable modules

- **Status:** Accepted
- **Date:** 2026-08-22
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "Should hash aggregator and scraper logic be embedded in the core application or loaded as external modules?"

## Context

In the Kodi ecosystem, media scrapers (Magneto, CocoScrapers, Orion, etc.) are decoupled from the addons that consume them (Umbrella, Fen, Seren, etc.). Users install scrapers as separate packages and enable them within their chosen addon. This decoupling provides several advantages:

1. Scrapers can be developed, updated, and distributed independently of the host application.
2. Different users can use different scraper combinations without the host application being aware of all possible scrapers at build time.
3. Scraper authors do not need to contribute to or coordinate with the host application to ship their modules.
4. When a scraper breaks (site goes down, API changes), it can be updated or replaced without touching the host application.

Kondooit faces a similar design question — but not uniformly across all provider types.

### The distinction: source providers vs. source resolvers

**Source providers** (TorBox, Easynews, IPTV services) are paid services with official, stable APIs. The user has a subscription, enters their credentials, and uses the service they pay for. These are analogous to metadata providers (TMDB, TVDB) — a small, stable set of well-defined integrations that implement a clean interface. The user's conscious decision to configure credentials IS the conscious choice to enable the capability.

**Source resolvers** (hash aggregators like Torrentio-protocol services, community-contributed scrapers, self-hosted hash databases) aggregate content availability information from the broader internet. These are:

- Potentially numerous (many possible configurations and instances)
- More legally ambiguous (they index content availability, not provide paid service access)
- Likely community-contributed (anyone can host a Torrentio-protocol instance with different configurations)
- Subject to frequent change (services appear and disappear, APIs shift)

The module-loader pattern provides genuine value for source resolvers but is unnecessary ceremony for source providers. TorBox changing their API is handled by updating the bundled TorBox provider — the same way a TMDB API change is handled by updating the bundled TMDB provider. Neither requires a module system.

## Decision

**Source resolvers** (hash aggregators, community-contributed scraper modules, self-hosted hash database clients) are **installable modules** that conform to a SourceResolver interface but are not hardcoded into the core application.

**Source providers** (TorBox, Easynews, IPTV services) are **bundled with the core** — registered at startup, configured and enabled by the user through credential entry. They follow the same pattern as metadata providers.

### What gets the module treatment

- Hash aggregators (Torrentio-protocol services, MediaFusion, TorrentsDB)
- Self-hosted hash databases (Bitmagnet, Zilean)
- Community-contributed scraper modules (future)
- Any source of content hashes or availability information from untrusted/gray-area origins

### What is bundled

- TorBox (debrid — paid service, official API, API key auth)
- Easynews (Usenet — paid service, official API, username/password auth)
- IPTV services (paid subscriptions, standard protocols M3U/Xtream Codes)
- Future debrid services (Real-Debrid, Premiumize, AllDebrid — same pattern as TorBox)

### Module structure

Each source resolver module is a self-contained directory with a defined structure:

```
module-name/
  manifest.json      — declares identity, version, capabilities, configuration schema
  resolver.py        — implements the SourceResolver interface
  ... (additional files as needed by the module)
```

The manifest declares:
- Module identity (name, version, author, description)
- Capability set (which SourceResolver capabilities this module implements)
- Configuration schema (what settings the module needs — typically a base URL)
- Compatibility (minimum Kondooit version required)

### Module loading

Kondooit's core provides a module loader that:

1. Discovers installed modules from configured paths
2. Validates manifests against the expected schema
3. Loads modules and verifies they implement the declared capabilities
4. Registers loaded modules as available source resolvers
5. Presents them in the provider settings UI like any other provider

### Module sources

Modules can be loaded from:

- **Local directory** — a filesystem path pointing to a module directory. This is the primary mechanism during development and for modules co-located in the same repository.
- **Remote URL** (future) — a URL pointing to a packaged module archive. This enables distribution outside the repository for production deployments.

During development, source resolver modules are developed inside this repository under a designated directory. The module loader points at these local paths. Before production, modules may be extracted to separate repositories and distributed via remote URLs — but the module interface and loading mechanism remain identical regardless of where the module lives.

### The core application provides

- The SourceResolver interface (abstract contract for hash/availability discovery)
- The SourceProvider interface (abstract contract for paid-service integrations — bundled)
- The module loader and lifecycle management (for resolvers)
- Provider settings storage (credentials, enable/disable, priority — for all provider types)
- The source discovery orchestration (which calls installed resolvers and bundled providers by capability)
- The filtering, sorting, and resolution pipeline
- The UI for browsing, configuring, and testing all providers and modules

### The core application DOES provide

- Bundled source provider implementations for paid services (TorBox, Easynews, IPTV)
- These implementations live in `infrastructure/providers/` alongside metadata providers

### The core application does NOT provide

- Hardcoded hash aggregator logic for any specific Torrentio-protocol service
- Direct knowledge of community scraper implementations
- Self-hosted hash database query logic embedded in the core codebase

## Rationale

The Kodi ecosystem's scraper separation exists because scrapers directly access pirate torrent indexer sites — legally gray code that benefits from distribution separation. Kondooit's source providers (TorBox, Easynews, IPTV) access paid services with the user's own credentials. The legal and practical concerns are fundamentally different.

Applying module-loader complexity to paid-service API clients adds:
- Installation ceremony without legal benefit (the user already makes a conscious choice by entering credentials)
- Development friction (updating a TorBox API change requires module packaging, not just a code fix)
- Testing complexity (modules need separate CI/deployment from core)

None of these costs are justified when the alternative is a clean interface implementation bundled with the core — the same pattern already proven by TMDB and TVDB.

For source resolvers (hash aggregators), the module system provides genuine value:
- **Legal separation** — the core does not ship code that indexes pirated content availability
- **Community extensibility** — anyone can write a resolver module without modifying core
- **Configuration diversity** — users can point at different Torrentio instances, self-hosted databases, etc.
- **Independent update cycles** — when a hash aggregator changes, only that module updates

## Alternatives considered

- **All source providers as installable modules (previous version of this ADR).** Rejected: applies module-loader complexity uniformly where it only provides value for a subset of providers. Paid-service API clients don't benefit from installation ceremony.

- **No module system at all — bundle everything including hash aggregators.** Rejected: hash aggregators are genuinely gray-area code that benefits from separation, and the set of possible resolvers is open-ended in a way that paid services are not.

- **Use a full plugin system with sandboxing and separate processes.** Rejected for now: adds significant complexity (IPC, security boundaries, resource isolation) that is not justified until the module ecosystem grows large or untrusted third-party modules are supported.

## Consequences

- Source providers (TorBox, Easynews, IPTV) live in `server/kondooit/infrastructure/providers/` alongside metadata providers.
- A `modules/` directory (or equivalent) exists for source resolver modules.
- Each resolver module has a manifest that declares its identity and capabilities.
- The core application includes a module loader that discovers and registers resolver modules.
- The SourceResolver interface is the formal contract between core and resolver modules.
- The SourceProvider interface is the formal contract for bundled paid-service providers.
- Provider settings UI shows both bundled providers and installed resolver modules.
- Modules developed in this repo can later be extracted to separate repos without changing their internal structure.

## Relationship to other ADRs

- **ADR-0002** (Provider vs. source): Supported. Both bundled providers and resolver modules produce sources. The three-level hierarchy (type → instance → source) applies to both.
- **ADR-0010** (Provider capability declaration): Supported. Both bundled providers and resolver modules declare capabilities. The orchestration layer queries only declared capabilities.
- **ADR-0011** (Provider priority and fallback): Supported. Both bundled providers and installed resolver modules participate in the priority system.
