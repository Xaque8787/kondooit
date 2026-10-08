# CLAUDE.md — Persistent Operating Instructions

This file is the governing instruction set for every Claude Code session in this repository. Read it before taking any action that affects architecture, documentation, or code.

## 1. Project Purpose

This project is a self-hosted, server-centric media platform — conceptually "server-centric Kodi."

The server is the single source of truth and orchestration point for a unified media catalog. Clients (Android, Apple, Web, TV, etc.) are intentionally thin: they authenticate, browse the server's unified catalog, request playback, and receive media. Media intelligence — metadata, source discovery, resolution, acquisition, playback routing — lives on the server, not the client.

See `vision/SYSTEM_VISION.md` for the full North Star vision. **Consult it before making any major decision.**

## 2. North Star Vision

The system presents one unified catalog whose primary question is "Can this content be played?" — not "Has this content been downloaded?" Content is represented independently of where it comes from. A single movie may simultaneously have local availability, Debrid availability, IPTV VOD availability, Usenet availability, and other streaming availability. These are different sources/providers for the same underlying content.

Metadata and content identity are separated from content acquisition and playback. Downloading/persisting content locally is a secondary capability, not the gating condition for appearing in the catalog.

## 3. Core vs. Provider/Plugin Capabilities

The core server is intentionally capability-agnostic. The core provides foundational services:

- content identity
- catalog
- metadata
- users, profiles, permissions
- authentication
- APIs
- orchestration
- source resolution / ranking
- configuration
- job management
- event / state management

Capabilities are delivered through well-defined provider/plugin interfaces. Examples (non-exhaustive, non-final): metadata providers, source discovery providers, playback providers, acquisition providers, local media providers, IPTV providers, Usenet providers, Debrid providers, indexer providers, storage providers, network/connectivity providers, transcoding providers, EPG providers.

**Playback is not necessarily hard-coded into the core.** Do not assume it must be.

## 4. Extract Capabilities — Do Not Merge Applications

The goal is NOT to merge existing applications (Jellyfin, Sonarr, Radarr, Prowlarr, AIOStreams, Torrentio, Comet, MediaFusion, Decypharr, NZBDAV, AltMount, Dispatcharr, Threadfin, etc.) into one binary.

The goal is to study those projects, extract their useful capabilities, identify the abstractions behind those capabilities, and re-implement those capabilities behind a clean unified architecture.

Existing applications are sources of domain knowledge and reusable implementation ideas — **not architectural boundaries that must be preserved.** Do not reproduce an existing app's internal architecture just because it is familiar.

## 5. Identify Ecosystem Workarounds

Much of the existing ecosystem contains workarounds: applications "spoofing" download-client workflows, indirect scaffolding, adapter chains, and coupling that exists for historical/ecosystem reasons rather than because it is the right abstraction.

When analyzing an existing project, always ask:

1. What capability does this project actually provide?
2. Which capabilities are intrinsic domain functionality?
3. Which capabilities are adapters?
4. Which capabilities are ecosystem workarounds?
5. Which capabilities overlap with other projects?
6. Which capabilities belong in the core?
7. Which should become provider/plugin interfaces?
8. Which existing implementations are reusable?
9. Which portions should be rewritten because the new architecture eliminates their original constraints?

Record findings in `research/` and `projects/`.

## 6. Persistent Project Memory

**Do not rely on conversational memory as the authoritative project state.** The repository itself is the project's persistent knowledge base.

- Significant architectural decisions are documented as ADRs in `decisions/` (see §7).
- Research findings live in `research/`.
- Per-project analyses live in `projects/`.
- Architectural direction lives in `architecture/`.
- The governing vision lives in `vision/SYSTEM_VISION.md`.

Future sessions must be able to recover full project state by reading these files. If a decision is not written down, it does not yet exist as project canon.

## 7. Architectural Decision Records (ADRs)

Every significant architectural decision must be recorded as an ADR in `decisions/` using the numbering convention `ADR-NNNN-short-title.md`. An ADR records: context, decision, rationale, alternatives considered, and consequences.

"Significant" includes: choosing a framework, defining a core/provider boundary, locking a plugin interface, selecting a protocol, changing a previously-decided boundary, or any decision that future work would depend on.

### Decision Status

Every ADR carries a `Status` field with one of four values:

- **Proposed** — drafted, not yet authoritative.
- **Accepted** — adopted and currently authoritative.
- **Superseded** — replaced by a later ADR; the `Superseded by` field names the replacement.
- **Deprecated** — withdrawn without a direct replacement; kept for history.

Transitions: `Proposed` → `Accepted` (or removed/deprecated); `Accepted` → `Superseded` or `Deprecated`. `Superseded` and `Deprecated` are terminal. Full rules are in `decisions/README.md`.

## 8. Do Not Silently Change Fundamental Architecture

Once an architectural decision is recorded in an ADR or in `architecture/`, do not change it silently. To change it, write a new ADR that supersedes the prior one and references it. Never edit an ADR to retroactively change a past decision — supersede it.

Concretely: if ADR-0003 is later judged wrong, leave ADR-0003's decision text intact, update only its `Status` to `Superseded` and add `Superseded by: ADR-0042`, then write ADR-0042 with the new reasoning. This preserves the architectural history — especially valuable when an AI is making decisions over a long-running project, since future sessions can reconstruct why a decision was made, what alternatives were rejected, and when/how it changed.

## 9. Distinguish Confirmed Facts from Assumptions

When writing documentation or analysis, explicitly separate:

- **Confirmed fact** — verified by reading actual source code, running the project, or reading authoritative docs. Cite the source.
- **Assumption / hypothesis** — plausible but not yet verified. Label it as such.
- **Open question** — unresolved. Record in the Open Architectural Questions section of `architecture/`.

Never present an assumption as a confirmed fact. Never claim a project works a certain way without having inspected its actual source code.

## 10. Inspect Actual Source Code Before Claiming How a Project Works

Before making any claim about how an existing open-source project works — its capabilities, boundaries, data flow, or interfaces — inspect its actual source code (under `source/` when supplied, or the upstream repository). Do not rely on memory, blog posts, or secondhand descriptions as authoritative.

If source is not yet available, mark the claim as an assumption or an open question — do not state it as fact.

## 11. Avoid Premature Implementation

This is a long-term, research-driven project. Do not jump to implementation before the relevant abstractions are understood.

- Do not lock in plugin interfaces before researching the projects that would implement them.
- Do not select frameworks merely because they are familiar.
- Do not write production code for a capability whose boundary is still an open question.
- Prefer a clean abstraction over compatibility with an existing application's internal architecture.

When uncertain, mark the uncertainty explicitly and continue research. A documented open question is more valuable than a premature answer.

## 12. Maintain Documentation as the Project Evolves

Documentation is not a one-time artifact. As the project evolves:

- Update `architecture/` when boundaries shift.
- Add ADRs for every new significant decision.
- Record research findings as they happen — do not batch them at the end.
- Keep `vision/SYSTEM_VISION.md` as the stable North Star; update it only deliberately and record the change in an ADR.
- When a previously-open question is resolved, move it out of the Open Questions section and into an ADR.

## 13. Repository Layout

```
CLAUDE.md              Governing operating instructions (this file)
vision/                North Star vision and long-form product direction
architecture/          Architectural principles, boundaries, open questions
decisions/             Architectural Decision Records (ADRs)
research/              Cross-project research and capability analysis
projects/              Per-existing-project analyses (one file per project)
roadmap/               Development milestones and implementation scope
source/                Local clones of existing open-source projects (supplied later)
docs/                  General documentation, guides, glossary
scripts/               Repo maintenance and analysis helper scripts
tests/                  Test harness (populated in implementation phases)
```

`source/` is git-ignored by convention — external repositories are supplied, not committed. Do not commit large external codebases into this repo.

## 14. Current Phase

The project is in the **Architecture and Project-Foundation phase**. No application source code exists yet. Do not proceed into source-code analysis or implementation until the user explicitly asks to begin the next phase.

Eight foundational ADRs (ADR-0001 through ADR-0008) have been accepted and are encoded as principles 13–29 in `architecture/PRINCIPLES.md`. Consult them before making decisions that touch content modeling, provider/source boundaries, identity, acquisition, playback, tenancy, connectivity, or implementation technology.

## 15. Development Roadmap

`roadmap/ROADMAP.md` defines the current development milestones and implementation scope.

Before beginning implementation work:

1. Read `roadmap/ROADMAP.md`.
2. Identify the current milestone.
3. Read the milestone's explicit goals.
4. Read its explicit exclusions.
5. Implement only the capabilities required for the current milestone unless the user explicitly expands the scope.

The roadmap does not override the System Vision or accepted architectural decisions. The hierarchy is:

```
System Vision
    ↓
Architecture Principles
    ↓
Accepted ADRs
    ↓
Development Roadmap
    ↓
Implementation
```

- The System Vision describes the ultimate product.
- Architecture defines how the system is structured.
- ADRs explain important architectural decisions.
- The Roadmap defines what should be implemented at the current stage.

The roadmap constrains **what** to build, not **how**. For example, if v0.0.1 includes TMDB and TVDB, that does not mean hard-coding `if provider == "tmdb"` branches — the provider abstraction (principle 4, ADR-0002) still applies. The roadmap says "build TMDB and TVDB" and the architecture says "build them as providers." Both are true. Do not use the roadmap as an excuse to bypass established abstractions, and do not use abstractions as an excuse to build capabilities the roadmap hasn't called for yet.

## 16. Technology Baseline

The current preferred implementation stack is defined in [ADR-0008](decisions/ADR-0008-technology-baseline-and-implementation-layer-boundaries.md):

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

These are implementation decisions, not domain concepts. They may be reconsidered through the ADR process if research demonstrates unsuitability. Do not substitute another framework merely because it is familiar or fashionable.

## 17. Architectural Layering and Dependency Direction

The system is layered as follows:

```
React Web UI → API Layer (Litestar) → Application Layer → Domain Layer
                                                          ↑
                                          Infrastructure (PostgreSQL, iroh, FFmpeg)
```

Dependencies point inward toward the domain. The Domain Layer must not know that Litestar, PostgreSQL, iroh, React, FFmpeg, or Docker exists. Implementation technologies adapt to the domain through explicit interfaces; the domain never adapts to them.

The domain model must not contain:
- Litestar request/response objects
- SQLAlchemy models as domain entities
- PostgreSQL-specific behavior
- React concepts
- iroh endpoint objects
- FFmpeg command-line structures
- Docker environment assumptions

This invariant is encoded as principles 24–29 in `architecture/PRINCIPLES.md` and in ADR-0008.

## 18. Docker as Preferred Deployment

Docker / Docker Compose is the preferred and officially supported deployment mechanism. The initial development experience should be:

```
git clone ...
cd kondooit
docker compose up --build
```

This must produce a functional development instance with the Kondooit server and PostgreSQL, without requiring the developer to manually install Python, PostgreSQL, Node.js, or database servers on the host. Docker simplifies deployment; it must not become a domain dependency.

## 19. v0.0.1 Implementation Boundary

Before beginning v0.0.1 implementation, consult `roadmap/ROADMAP.md` for the full milestone definition. In summary, v0.0.1 includes:

- Python/Litestar server with PostgreSQL
- Docker Compose development environment with local Dockerfile build
- Administrator creation and authentication
- TMDB/TVDB metadata providers (behind the provider abstraction)
- Media catalog UI (React + TypeScript)
- Initial iroh connectivity validation (optional transport, independent of HTTP; browser-based iroh client desirable but not required)

v0.0.1 explicitly excludes: media playback, streaming, transcoding, Debrid/Usenet/IPTV/torrent/local-media providers, EPG, acquisition, multi-user profiles, and server-side stream proxying. The architecture may establish interfaces for future features, but actual implementation must remain within the v0.0.1 scope. These exclusions describe v0.0.1 as originally scoped; playback, streaming/proxying, remux and basic transcoding, Debrid/Usenet providers, and profiles have since been delivered — see the "Delivered Beyond the Original Milestone Plan" section of `roadmap/ROADMAP.md` for current state.

## 20. Database Schema and Migrations

Defined by [ADR-0019](decisions/ADR-0019-schema-owned-by-models-alembic-for-alterations.md). The server runs against its own PostgreSQL via Docker Compose; hosted-database tooling (Supabase, `apply_migration`, RLS policies) is not used by Kondooit and must not be added.

- **The SQLAlchemy models are the complete schema.** Every table, column, index, and constraint is defined in the models. Nothing may exist only in a migration.
- **Startup owns initialization.** `kondooit.infrastructure.schema.initialize_schema` creates missing tables from the models, stamps a database with no recorded revision at `head`, and otherwise runs `alembic upgrade head`. All of this happens in one transaction, and failure aborts startup. New model modules must be imported in `schema.py` so their tables are registered.
- **New table:** add the model only. Do not write a migration.
- **Change to an existing table** (add, remove, or rename a column; change a constraint or index; backfill data): change the model, then add an Alembic revision under `server/alembic/versions/` that checks current state before acting (for example, using `sa.inspect(op.get_bind())`). The revision must be a no-op on a database freshly created from the models.
- `0001_baseline` is empty and marks the schema as of ADR-0019. Do not add table creation to it.
