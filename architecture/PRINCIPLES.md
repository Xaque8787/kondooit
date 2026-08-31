# Architectural Principles

Foundational invariants for the system. These are stable constraints that future work must respect; specific technology choices are recorded as ADRs in `../decisions/`.

Principles 1–12 are foundational; principles 13–29 are early architectural decisions encoded as ADRs and restated here so they are visible alongside the invariants. Each ADR-backed principle links to its ADR. Principles 30–31 are architectural decisions encoded as ADRs (ADR-0009, ADR-0010).

## 1. The server is the source of truth

All media intelligence — metadata, catalog, identity, source discovery, resolution, ranking, acquisition orchestration, playback routing — lives on the server. Clients are thin.

## 2. Content is independent of source

Content is represented once, independently of where it comes from. Local, Debrid, IPTV VOD, Usenet, and other streaming availability are different **sources** for the same underlying **content**.

## 3. Metadata is separate from acquisition, playback, and local persistence

Content identity and metadata are established independently of how content is acquired, played, or stored locally. A title appears in the discovery interface because a metadata provider knows about it — not because it has been downloaded, and not because it has been imported into a local database. Provider metadata is evidence supplied on demand; it does not need to become a permanent local record to be visible in the UI.

## 4. The core is capability-agnostic

The core provides foundational services (identity, catalog, metadata, users, permissions, auth, APIs, orchestration, resolution, configuration, jobs, events). Capabilities are delivered through well-defined provider/plugin interfaces.

## 5. Playback orchestration is core; source resolution is a provider capability

The core owns playback orchestration and server-side streaming (sessions, proxy, range, buffering, bandwidth). Providers resolve sources and return playable resources; they do not implement transport. See [ADR-0006](../decisions/ADR-0006-playback-orchestration-and-transport.md).

## 6. Extract capabilities, do not merge applications

Existing projects are sources of domain knowledge and reusable implementation ideas — not architectural boundaries to preserve. The architecture is designed top-down from the product vision.

## 7. Identify workarounds, do not reproduce them

Much of the existing ecosystem is held together by workarounds (spoofed download clients, adapter chains, indirect scaffolding). The new architecture identifies the underlying capability rather than reproducing the workaround.

## 8. Clean abstractions over compatibility

Prefer a clean abstraction over compatibility with an existing application's internal architecture. Existing implementations may inform the design but must not dictate it.

## 9. No premature locking

Plugin interfaces, protocols, and frameworks are not locked in until the relevant research is complete. When uncertain, record an open question rather than guessing.

## 10. Decisions are written and superseded, never silently changed

Significant decisions are ADRs. To change one, write a new ADR that supersedes it. Never edit a past decision in place.

## 11. Facts must be verified

Claims about how an existing project works must be verified against its actual source code. Unverified claims are labeled assumptions or open questions.

## 12. Streaming-first

The default flow resolves a source and streams. Downloading is a secondary capability, never the gating condition for catalog presence or playability.

## 13. Live TV is a first-class content type

Live TV shares catalog infrastructure with VOD but has its own domain model (Channel, Program/Event). The catalog is unified at the navigation layer, not at the data-model layer. See [ADR-0001](../decisions/ADR-0001-live-tv-first-class-content-type.md).

## 14. Providers are integrations; sources are concrete availability

A **provider** is an integration capable of performing operations. A **source** is concrete media availability returned by a provider for a particular content item. Provider capability (type) is separate from provider instance. See [ADR-0002](../decisions/ADR-0002-provider-vs-source-distinction.md).

## 15. The core owns canonical content identity, not a local copy of the provider catalog

Providers provide evidence about content (IDs, filenames, metadata); the core establishes canonical content identity. Providers do not own identity. However, "canonical identity" means a stable representation that allows the same content to be recognized across providers — it does **not** mean a full local copy of provider metadata. Identity is lightweight and may initially be as simple as a provider/content-type/external-ID reference. A provider-independent identity (e.g., a Kondooit UUID) should be introduced only where the architecture actually requires it. See [ADR-0003](../decisions/ADR-0003-core-owns-canonical-identity.md).

## 16. Downloads create local sources, not separate content entities

A completed download becomes another source for the existing content item. "Library" is a view/state of the catalog, not a separate content universe. See [ADR-0004](../decisions/ADR-0004-downloads-create-local-sources.md).

## 17. Single-server, multi-user household model

The initial product is one server installation with multiple users and profiles sharing one provider ecosystem. It is not a multi-tenant SaaS platform. The design must not preclude future multi-tenancy but must not optimize for it. See [ADR-0005](../decisions/ADR-0005-single-server-household-model.md).

## 18. Server-side proxying is a playback capability of the core

Range handling, sessions, buffering, bandwidth, and proxying belong to the server playback subsystem, not to providers. Transcoding is an invokable capability the playback system can call. See [ADR-0006](../decisions/ADR-0006-playback-orchestration-and-transport.md).

## 19. iroh is the preferred/default remote transport

iroh is the default remote connectivity mechanism for zero-config onboarding. It is not the application protocol itself. See [ADR-0007](../decisions/ADR-0007-iroh-default-transport-independent-protocol.md).

## 20. The client/server protocol must remain transport-independent

The Kondooit application protocol sits above transports (iroh, HTTPS, local). iroh must not become deeply embedded throughout the application. See [ADR-0007](../decisions/ADR-0007-iroh-default-transport-independent-protocol.md).

## 21. Existing applications are sources of capabilities and domain knowledge, not architectural boundaries

A concept's existence in an existing project does not imply it belongs in the unified architecture.

## 22. Do not assume a concept's presence implies its inclusion

When analyzing an existing project, never assume that a concept's existence in that project means that concept belongs in the unified architecture. Determine whether it represents a genuine domain requirement, an implementation choice, or an ecosystem workaround.

## 23. Distinguish domain requirements from implementation choices and workarounds

Every capability found in an existing project must be classified as one of: intrinsic domain functionality, adapter, ecosystem workaround, or overlap with another project. Only intrinsic domain functionality (or a clean abstraction of it) is a candidate for the unified architecture.

## 24. The domain layer is independent of implementation technologies

The domain model must not depend on any specific API framework, database, transport, client framework, media processor, or deployment mechanism. Implementation technologies adapt to the domain through explicit interfaces; the domain never adapts to them. See [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md).

## 25. Dependencies point inward toward the domain

The dependency direction is: Web Client → API Layer → Application Layer → Domain Layer. Infrastructure and external implementations depend inward toward interfaces defined by the application/domain. The domain layer has as few external dependencies as reasonably possible. See [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md).

## 26. The API framework is an implementation detail

Litestar (or any future API framework) must remain at the API/application-layer boundary. Its types and concepts must not leak into the domain model. The domain must be usable without the API framework. See [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md).

## 27. The database is an infrastructure concern, not a domain concept

PostgreSQL is the canonical database, accessed through a data-access boundary (SQLAlchemy). The domain must not contain PostgreSQL-specific logic or SQLAlchemy models as domain entities. SQLite may be used only for isolated tests, never as an architectural dependency. See [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md).

## 28. Transport independence is maintained through a networking abstraction

iroh is a networking implementation behind a Kondooit networking abstraction. The application protocol remains transport-independent. iroh must not become embedded in the domain or application layers. See [ADR-0007](../decisions/ADR-0007-iroh-default-transport-independent-protocol.md) and [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md).

## 29. Containerized deployment is preferred

Docker / Docker Compose is the preferred deployment and development mechanism. The application must be runnable from a clean checkout via `docker compose up --build` without requiring manual host installation of runtime dependencies. Docker simplifies deployment; it must not become a domain dependency. See [ADR-0008](../decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md).

## 30. Content discovery is provider-driven, not local-catalog-driven

The primary browsing experience is backed by metadata provider APIs, not by a locally persisted copy of provider catalogs. The landing page, search, trending, popular, genres, and discovery all query configured metadata providers and aggregate results. A user should not have to "import" content into a local database for it to appear in the UI. Local persistence is reserved for application state (users, configuration, favorites, watch state) and optional caching — not as the primary data source for browsing. See [ADR-0009](../decisions/ADR-0009-provider-driven-content-discovery.md).

## 31. Providers declare their capabilities

Providers declare which discovery capabilities they support rather than being forced to implement every method. If TMDB supports "now playing" and TVDB does not, the abstraction must express that difference. The aggregation layer only calls capabilities a provider supports. This avoids forcing providers to implement fake equivalents or weakening the abstraction to the lowest common denominator. See [ADR-0010](../decisions/ADR-0010-provider-capability-declaration.md).
