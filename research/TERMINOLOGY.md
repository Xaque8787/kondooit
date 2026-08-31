# Kondooit Terminology

## Purpose

This document is the evolving canonical terminology map for the Kondooit project. It distinguishes:

- **Kondooit terminology** — terms with established meanings in this project.
- **Existing ecosystem terminology** — terms used by existing projects, which may or may not map cleanly to Kondooit concepts.
- **Ambiguous terms** — words used differently across the ecosystem.
- **Terms that should not be used interchangeably.**

Definitions here may be refined as repository research reveals additional ambiguities. When a term's meaning changes as a result of an accepted ADR, update the definition and reference the ADR.

---

## Established Kondooit Terms

### Provider Type

**Definition:** A category of external capability/integration. Represents *what kind* of operation a provider can perform (e.g., Debrid, IPTV, Usenet, Local Media, Metadata). Separate from any specific account or instance.

**Related Terms:** Provider, Provider Instance, Source.

**Potential Ambiguity:** In some ecosystems "provider" refers to both the type and the instance. In Kondooit these are deliberately separated.

**ADR Reference:** [ADR-0002](../decisions/ADR-0002-provider-vs-source-distinction.md)

---

### Provider Instance

**Definition:** A configured instance or account of a Provider Type (e.g., "My Real-Debrid account," "My IPTV subscription," "Local Storage at /media"). One Provider Type may have multiple instances.

**Related Terms:** Provider Type, Source, Credential.

**Potential Ambiguity:** Existing projects often call this simply "provider" or "account." In Kondooit, "provider" alone is ambiguous — use "Provider Type" or "Provider Instance" specifically.

**ADR Reference:** [ADR-0002](../decisions/ADR-0002-provider-vs-source-distinction.md)

---

### Source

**Definition:** A concrete piece of media availability returned by a Provider Instance for a particular piece of content. A single content item may have multiple sources from different providers (e.g., a 1080p WEB-DL from Debrid, a local file, and an IPTV VOD entry for the same movie).

**Related Terms:** Provider Instance, Content, Canonical Content Identity.

**Potential Ambiguity:** "Source" in some ecosystems means a torrent file, an indexer, or a media file. In Kondooit it specifically means *concrete availability of a content item from a provider instance*.

**ADR Reference:** [ADR-0002](../decisions/ADR-0002-provider-vs-source-distinction.md)

---

### Canonical Content Identity

**Definition:** The server-owned identity representing a piece of content independently of any particular provider. The core establishes identity from provider-supplied evidence (external IDs, filenames, metadata); providers do not own identity. Canonical identity is the join key across sources, metadata, playback, and user state.

**Related Terms:** Content, Metadata, Provider.

**Potential Ambiguity:** Existing projects often use TMDB/TVDB IDs directly as content identity. In Kondooit, external IDs are *evidence* fed into identity resolution; the canonical identity is owned by the core and may be backed by but is not equal to any single external ID.

**ADR Reference:** [ADR-0003](../decisions/ADR-0003-core-owns-canonical-identity.md)

---

### Live TV

**Definition:** A first-class content domain representing linear channels and their time-based programming. Live TV shares catalog, metadata, user, search, and playback infrastructure with OnDemand content where appropriate, but has its own domain model (Channel, Program/Event). It is unified with VOD at the catalog/navigation layer, not at the data-model layer.

**Related Terms:** Channel, Program, Event, EPG, OnDemand, Content.

**Potential Ambiguity:** "Live TV" in some ecosystems refers only to the stream, not the schedule/EPG. In Kondooit, Live TV includes channel identity, schedule, and EPG as first-class concerns.

**ADR Reference:** [ADR-0001](../decisions/ADR-0001-live-tv-first-class-content-type.md)

---

### Local Source

**Definition:** A Source representing content available from local or server-accessible storage (e.g., a file at `/media/movies/The Matrix.mkv`). A local source is just another source for the existing content item — it does not create a separate "owned library entity." "Library" is a view/filter over the unified catalog, not a separate content universe.

**Related Terms:** Source, Content, Acquisition, Download.

**Potential Ambiguity:** Traditional media servers treat local media as a separate "library" distinct from streaming. In Kondooit, local files are sources within the same unified catalog — there is no library/streaming bifurcation at the data-model level.

**ADR Reference:** [ADR-0004](../decisions/ADR-0004-downloads-create-local-sources.md)

---

### Playback Session

**Definition:** A server-managed representation of an active playback request. The core owns playback orchestration (which source, which mode, which client, session lifecycle). Providers resolve sources and return playable resources; they do not implement transport. Server-side proxying (range handling, buffering, bandwidth) is a core playback subsystem capability.

**Related Terms:** Source, Playback Engine, Transcoding, Direct Playback, Server Proxy.

**Potential Ambiguity:** Some ecosystems conflate "playback" with "streaming" or treat the client as the session owner. In Kondooit, the server owns the session; the client is thin.

**ADR Reference:** [ADR-0006](../decisions/ADR-0006-playback-orchestration-and-transport.md)

---

## Terms To Clarify Through Research

The following terms are used across the ecosystem with varying meanings. They will be clarified as repository research proceeds:

- **Release** — may mean a torrent/NZB result, a quality variant, or a provider-returned availability candidate.
- **Stream** — may mean a playable URL, an active playback session, or a transport mechanism.
- **Indexer** — may mean a torrent indexer, a Usenet indexer, or an abstract search source.
- **Library** — in Kondooit this is a view, not a data model. Existing projects may use it as a primary entity.
- **Download** — in Kondooit, a completed download becomes a local source. Existing projects may treat downloads as first-class entities.
- **Catalog** — in Kondooit, the unified browsing surface. Existing projects may not have an equivalent concept.
- **EPG** — electronic program guide. Meaning and data shape vary across IPTV tools.

---

## Rules

- Do not use "provider" alone when "Provider Type" or "Provider Instance" is meant.
- Do not conflate external IDs (TMDB, TVDB) with Canonical Content Identity.
- Do not refer to local media as a separate "library" in Kondooit's data model — it is a set of local sources.
- When documenting existing projects, use their terminology but note where it diverges from Kondooit's.
