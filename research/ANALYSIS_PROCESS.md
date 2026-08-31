# Kondooit Repository Analysis Process

This document is the canonical, persistent procedure for analyzing any repository placed under `source/`. A future Claude Code session should be able to read this file alone and understand exactly what is expected when instructed: "Analyze the repository at `source/<name>`."

---

## A. Purpose

Repository analysis exists to **understand existing software**, not to immediately design or implement Kondooit.

The goal is software archaeology: extract what a project genuinely does, classify each capability, distinguish domain functionality from implementation choices and ecosystem workarounds, and record findings as persistent, auditable research artifacts.

During individual repository analysis, do **not** decide "this becomes a Kondooit plugin." Describe "potential Kondooit relevance" as a hypothesis only. The actual architecture is determined after multiple repositories have been analyzed and compared.

---

## B. Preconditions

Before analyzing a repository, Claude must:

1. Read `CLAUDE.md`.
2. Read `vision/SYSTEM_VISION.md`.
3. Read `architecture/PRINCIPLES.md`.
4. Read `architecture/OPEN_QUESTIONS.md`.
5. Read all relevant ADRs in `decisions/`.
6. Read this file (`research/ANALYSIS_PROCESS.md`).
7. Inspect the repository under `source/<name>`.

If the repository is missing, **stop and report that it is unavailable.** Do not fabricate analysis from memory, READMEs alone, or secondhand descriptions.

Claims about how a project works must be verified against actual source code. If source is insufficient to verify a claim, label it `INFERRED` or `UNCERTAIN` — never present it as fact.

---

## C. Repository Inventory

Establish the project's shape. Record:

- **Project purpose** — what problem it solves, in plain terms.
- **Language(s)** — primary and secondary.
- **Framework(s)** — web, ORM, CLI, plugin, etc.
- **Entry points** — main files, server bootstrap, CLI commands.
- **Major directories** — top-level layout and what each contains.
- **Major subsystems** — identifiable components or modules.
- **Dependencies** — significant libraries from the manifest(s).
- **APIs** — REST, GraphQL, gRPC, internal, plugin interfaces.
- **Databases** — what database(s), schema approach, migrations.
- **Storage** — filesystem, object storage, config storage.
- **Workers/jobs** — background processes, schedulers, queues.
- **Configuration** — config files, env vars, defaults.
- **Authentication** — auth model, sessions, API keys.
- **Deployment model** — Docker, bare metal, systemd, etc.
- **External integrations** — services and other apps it talks to.

Do not yet decide how it maps into Kondooit. This stage is about understanding the project as-is.

---

## D. Functional Decomposition

Break the project into actual capabilities. Do not reproduce the project's marketing terminology. For every significant function ask: **"What does this software actually do?"**

Break it down into atomic or near-atomic capabilities. Examples:

- search
- discovery
- normalization
- content identification
- source resolution
- downloading
- streaming
- metadata enrichment
- playback
- transcoding
- EPG management
- scheduling
- monitoring
- local storage management
- proxying
- authentication

Each capability should be described independently of how the project implements it.

---

## E. Capability Classification

Every significant capability must be classified as exactly one of:

1. **Domain Capability** — a genuine problem the system needs to solve (finding sources, identifying content, resolving a stream, maintaining an EPG).
2. **Implementation Detail** — a way the project happens to implement a capability (a specific database, queue, framework, filesystem layout).
3. **Ecosystem Adapter** — integration with another application/protocol that provides a real capability, but shaped by that ecosystem's interface.
4. **Ecosystem Workaround** — a mechanism that exists only because another application imposes a constraint (spoofing, fake APIs, symlinks, simulated clients).
5. **User Interface** — presentation, navigation, client-facing behavior.
6. **Operational/Infrastructure** — deployment, logging, health, config, monitoring.
7. **Uncertain** — insufficient evidence to classify. Mark explicitly rather than guessing.

A capability must **not** be considered a Kondooit requirement merely because the existing project implements it.

---

## F. Evidence Requirements

Every meaningful technical claim must be classified as:

- **VERIFIED** — directly supported by source code, tests, configuration, or authoritative documentation. Cite the file/function/class.
- **INFERRED** — strongly supported by evidence but not explicitly established.
- **UNCERTAIN** — insufficient evidence; plausible but unverified.

When practical, identify the source files, classes, functions, API definitions, tests, or configuration that support important claims.

**Do not fabricate evidence.** If you cannot point to source, label the claim `INFERRED` or `UNCERTAIN`.

---

## G. Data Flow Analysis

For important capabilities, document:

```
Input
   ↓
Processing
   ↓
Output
   ↓
Persistent state
   ↓
External systems
```

Identify both synchronous and asynchronous flows. Note where state is mutated, where events are emitted, and where the flow crosses process or network boundaries.

---

## H. Data Model Analysis

Identify significant entities. Examples:

- Movie, Series, Season, Episode
- Channel, Program/Event
- Source, Release, Provider, Download, File, Stream
- Playback Session, User, Credential

For each relevant entity determine:

- **Purpose** — what it represents.
- **Identifiers** — internal and external IDs.
- **External IDs** — TMDB, TVDB, IMDb, etc.
- **Relationships** — what it links to.
- **Lifecycle** — creation, updates, deletion, state transitions.
- **Persistence** — where and how it is stored.
- **Ownership** — who owns the identity (the project, an external system, the user).
- **Domain-level vs. implementation-specific** — is this a real domain concept or an artifact of this project's architecture?

Do **not** assume the existing entity model is the correct Kondooit model. The goal is to extract the underlying concepts.

---

## I. Integration Analysis

For every significant external integration, determine:

- **What system** is being integrated.
- **Why** it is integrated — what capability it provides.
- **What data** is exchanged.
- **What protocol/API** is used.
- **What capability** is obtained.
- **Whether** the integration represents a genuine domain requirement.
- **Whether** it exists merely for ecosystem compatibility.

The important question is: **"What capability does this application actually need from this external system?"** — not "Should Kondooit integrate with this application?"

---

## J. Ecosystem Workaround Analysis

Explicitly search for:

- spoofed APIs
- mock APIs
- compatibility endpoints
- fake download clients
- fake media servers
- virtual files / virtual filesystems
- generated files
- symlinks
- fake filesystem structures
- compatibility metadata
- application-specific polling
- duplicated state
- duplicated metadata
- protocol emulation

For each workaround record:

1. **What is happening?**
2. **What problem does it solve?**
3. **Why does the existing ecosystem require it?**
4. **What underlying capability is actually needed?**
5. **Could Kondooit's architecture eliminate the workaround?**

Do not assume a workaround can be removed until the underlying constraint has been understood. Mark confidence as `VERIFIED`, `INFERRED`, or `UNCERTAIN`.

This analysis is especially important for the *arr ecosystem, Debrid integrations, media-server integrations, and IPTV integrations.

---

## K. Project Research Artifacts

When a repository is analyzed, create:

```
projects/<project-name>/
├── OVERVIEW.md
├── CAPABILITIES.md
├── ARCHITECTURE.md
├── DATA_MODEL.md
├── INTEGRATIONS.md
└── WORKAROUNDS.md
```

### OVERVIEW.md
What the project is, what problem it solves, major components, high-level architecture, important terminology. Concise.

### CAPABILITIES.md
Structured list of capabilities using the format in section L below.

### ARCHITECTURE.md
How the project is actually structured: major components, communication paths, data flow, background processes, APIs, storage, external dependencies. Describe important flows where practical.

### DATA_MODEL.md
Important entities and relationships. Include identifiers and external IDs where relevant.

### INTEGRATIONS.md
External systems and why they are used. For each: what capability is obtained, what data is exchanged, whether the integration is domain-intrinsic or ecosystem compatibility.

### WORKAROUNDS.md
Ecosystem-specific mechanisms, classified as genuine requirement / implementation choice / compatibility requirement / workaround.

Additional files may be created if useful, but keep the set intentionally lightweight.

---

## L. Capability Artifact Format

Use this exact format for each entry in `CAPABILITIES.md`:

```markdown
## Capability: <name>

### Description
...

### Classification
Domain Capability / Implementation Detail / Ecosystem Adapter /
Ecosystem Workaround / UI / Infrastructure / Uncertain

### Evidence
...

### Evidence Level
VERIFIED / INFERRED / UNCERTAIN

### Inputs
...

### Outputs
...

### Dependencies
...

### Persistent State
...

### External Systems
...

### Relationships
...

### Potential Kondooit Relevance
...

### Notes
...
```

**"Potential Kondooit Relevance" is a research hypothesis only. It is NOT an architectural decision.**

---

## M. Cross-Project Synthesis

After multiple repositories have been analyzed, compare their capabilities. Do **not** create one Kondooit abstraction per application.

Identify overlapping capabilities. Example:

- Project A: Debrid source discovery
- Project B: Debrid source discovery
- Project C: Debrid source discovery

Potential conclusion: **Debrid Source Discovery** — one capability, not three plugins — unless there is a genuine reason they are fundamentally different.

For each overlapping capability determine:

- what they have in common
- where they differ
- which differences are genuine domain requirements
- which are implementation-specific
- which are ecosystem-specific
- whether one abstraction can represent all of them
- whether multiple specialized abstractions are necessary

Do not simply union all features. Find the smallest clean set of abstractions.

---

## N. Capability Map

`research/CAPABILITY_MAP.md` is the canonical cross-project map. It is **not** a list of applications — it is a map of underlying capabilities.

For each capability, eventually track:

- Capability
- Description
- Projects providing it
- Common behavior
- Project-specific behavior
- Dependencies
- Workarounds
- Potential Kondooit abstraction
- Open questions
- Evidence

Do not fill this with assumptions before repositories are analyzed. The actual map must emerge from research.

---

## O. Entity Map

`research/ENTITY_MAP.md` is the cross-project comparison of domain entities.

For each entity compare:

- project terminology
- meaning
- identifiers
- relationships
- lifecycle
- important differences

Identify where different projects use:

- different names for the same concept
- the same name for different concepts

Do **not** finalize the Kondooit domain model in this file.

---

## P. Terminology

`research/TERMINOLOGY.md` is the evolving canonical terminology map. It distinguishes:

- existing ecosystem terminology
- Kondooit terminology
- ambiguous terms
- terms that should not be used interchangeably

It begins with the concepts already established by accepted ADRs (see the file for current entries). It may evolve as research reveals additional ambiguities.

---

## Q. Workaround Map

`research/ECOSYSTEM_WORKAROUNDS.md` is the cross-project inventory of ecosystem-specific workarounds.

For each workaround, eventually record:

- Existing Project(s)
- Problem
- Existing Solution
- External Constraint
- Underlying Capability
- Why Kondooit May Not Need It
- Potential Kondooit Approach
- Evidence
- Confidence

Do not assume a workaround can be removed until the underlying constraint has been understood.

---

## R. Handling New Repositories

Standard operating procedure when the user adds a repository under `source/` and says something like "Analyze this source":

1. **Identify** the repository under `source/<name>`.
2. **Read** the governing Kondooit documents (CLAUDE.md, vision, architecture, ADRs).
3. **Read** this file (`research/ANALYSIS_PROCESS.md`).
4. **Inspect** the repository — source code, config, manifests, tests, docs.
5. **Create** `projects/<project-name>/`.
6. **Perform** the complete analysis (stages C–J above).
7. **Populate** the six required project artifacts (section K).
8. **Identify** unresolved questions and record them.
9. **Update** cross-project research files (CAPABILITY_MAP, ENTITY_MAP, TERMINOLOGY, ECOSYSTEM_WORKAROUNDS) only where the new analysis confirms, extends, or contradicts existing entries.
10. **Distinguish** newly discovered facts from existing assumptions. Label evidence levels.
11. **Report** what was learned.
12. **Do not** implement Kondooit code unless separately instructed.

---

## S. Updating Existing Research

### When a new repository confirms an existing capability

Update the existing capability entry. Do **not** create a duplicate capability merely because the new project uses different terminology.

### When a new repository contradicts an existing conclusion

Do **not** silently rewrite history. Record the conflict and identify the affected research file and section.

If the conflict affects an **accepted architectural decision** (an ADR), follow the ADR process:

1. Document the discovery in `research/`.
2. Explain why the existing decision may need reconsideration.
3. Identify which ADR is affected.
4. Propose a new ADR if appropriate.
5. **Ask the user for confirmation** before changing a foundational architectural decision.

Never edit an accepted ADR in place to retroactively change its decision. Supersede it with a new ADR.

---

## T. Research vs. Architecture Boundary

This distinction must be maintained throughout the project:

- **Research documents** (`research/`, `projects/`) describe what was **discovered** about existing software.
- **Architecture documents** (`architecture/`) describe what Kondooit has **decided**.
- **ADR documents** (`decisions/`) explain **why** an architectural decision was made.

Research findings must **not** silently become architectural decisions. A capability discovered in an existing project is evidence, not authority. Only intrinsic domain functionality (or a clean abstraction of it) is a candidate for the unified architecture, and even then it must go through the ADR process before becoming canon.

**Existing applications are evidence. They are not architectural authorities.** Kondooit's System Vision, accepted ADRs, and principles govern the eventual design.
