# ADR-0008: Technology baseline and implementation-layer boundaries

- **Status:** Accepted
- **Date:** 2026-08-17
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "What technology stack should Kondooit use for its initial implementation, and how should those technologies relate to the domain model?"

## Context

The project has established a domain-driven, capability-agnostic architecture through ADR-0001 through ADR-0007. Before implementation begins (v0.0.1), the implementation technology stack must be decided so that development can proceed without ambiguity. Equally important, the boundary between implementation technologies and the domain model must be explicit — the domain must not become coupled to any specific framework, database, transport, or deployment mechanism.

## Decision

### Technology baseline

The current preferred implementation stack is:

| Layer | Technology |
|---|---|
| Server language | Python |
| HTTP/API framework | Litestar |
| Web client | React + TypeScript |
| Database | PostgreSQL |
| Data access | SQLAlchemy |
| Validation | Pydantic |
| Networking | iroh |
| Media processing | FFmpeg |
| Deployment | Docker / Docker Compose |

### Architectural layering

```
                    ┌─────────────────────┐
                    │    React Web UI     │
                    └──────────┬──────────┘
                               │
                         HTTP / WebSocket
                               │
                    ┌──────────▼──────────┐
                    │     API Layer       │
                    │      Litestar       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Application Layer   │
                    │                     │
                    │ orchestration       │
                    │ authorization       │
                    │ workflows           │
                    │ playback sessions   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Domain Layer     │
                    │                     │
                    │ Content             │
                    │ Source              │
                    │ Provider            │
                    │ User                │
                    │ PlaybackSession     │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
       Capabilities       Networking       Infrastructure
             │                 │                 │
       ┌─────┼─────┐         iroh          PostgreSQL
       │     │     │                       Storage
    Metadata Discovery Playback             FFmpeg
       │     │     │
      TMDB Debrid ...
      TVDB IPTV
```

### Dependency direction

Dependencies point inward toward the domain:

```
Web Client
    ↓
API Layer
    ↓
Application Layer
    ↓
Domain Layer

External Systems
    ↓
Infrastructure Layer
    ↓
Application Layer
    ↓
Domain Layer
```

The Domain Layer has as few external dependencies as reasonably possible. It must not know that Litestar, PostgreSQL, iroh, React, FFmpeg, or Docker exists.

### Technology isolation rules

- **Litestar** must remain an API/application-layer detail. Litestar types must not leak into the domain model. The domain should be usable without Litestar.
- **SQLAlchemy** models are infrastructure/data-access representations, not domain entities. The domain defines its own entities; SQLAlchemy models adapt to them.
- **PostgreSQL** is the canonical database, not SQLite. The architecture must not depend on SQLite-specific behavior. SQLite may be used only for isolated tests or tooling.
- **iroh** is a networking implementation behind a Kondooit networking abstraction, not a domain concept. The application protocol remains transport-independent (per ADR-0007).
- **FFmpeg** performs media processing. Kondooit invokes it; Kondooit does not reimplement media processing in Python.
- **React** is a client implementation. The server API must be client-neutral. Domain logic must not live in the React application.
- **Docker** is the preferred deployment mechanism. The initial target is Docker Compose with a local Dockerfile build context.

### Python as the server language

Python is chosen for the server because of:
- developer familiarity
- strong ecosystem for API and integration work
- strong ecosystem for media and automation tooling
- strong interoperability with existing projects being researched
- suitability for the primarily I/O-oriented workload
- availability of iroh Python bindings
- suitability for AI-assisted development and maintenance

Python should not be used for CPU-intensive media processing. Specialized native software (FFmpeg) performs that work.

### Docker as preferred deployment

Docker Compose is the officially supported deployment and development mechanism. A clean checkout should support:

```
docker compose up --build
```

producing a functional development instance with the Kondooit server and PostgreSQL. The developer should not need to manually install Python, PostgreSQL, Node.js, or database servers on the host for the canonical startup path.

## Rationale

These technologies are chosen because they are well-suited to the project's needs and they are replaceable. The architectural invariant — that implementation technologies are subordinate to the domain and capability contracts — means that any of these choices can be reconsidered through the ADR process if later research demonstrates unsuitability.

The layering and dependency-direction rules ensure the domain model remains pure and that framework coupling stays at the infrastructure/application boundary where it can be swapped.

## Alternatives considered

- **Node.js/TypeScript for the server.** Rejected: weaker ecosystem for media automation tooling; less interoperability with existing Python-based projects being researched.
- **FastAPI instead of Litestar.** Rejected: Litestar provides stronger architectural features for layered applications (dependency injection, plugin system, OpenAPI); the decision can be revisited if experience proves otherwise.
- **SQLite as the default database.** Rejected: expected concurrent users, background workers, metadata synchronization, discovery jobs, EPG synchronization, and playback session state require PostgreSQL's concurrent transactional behavior and indexing. Designing around SQLite would create migration debt.
- **Embedding iroh directly in the application protocol.** Rejected: violates ADR-0007's transport-independence principle.
- **Bare-metal deployment as the primary path.** Rejected: Docker Compose provides a reproducible, self-contained development experience that does not require manual host setup.

## Consequences

- The server is Python with Litestar; the web client is React + TypeScript.
- PostgreSQL is the canonical database; the architecture must not depend on SQLite-specific behavior.
- iroh sits behind a Kondooit networking abstraction.
- The domain layer is framework-agnostic; infrastructure adapts to domain interfaces.
- Docker Compose is the canonical development and deployment path.
- These choices are reversible through the ADR process, but the domain-isolation invariant is not — any replacement technology must respect the same boundary.
