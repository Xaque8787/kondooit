# Kondooit Ecosystem Workaround Map

## Purpose

This document records mechanisms that exist because of limitations or compatibility requirements of the existing media ecosystem. A workaround is a mechanism that exists not because it is the right abstraction, but because another application, protocol, or ecosystem constraint forces it.

The goal is to identify the underlying capability behind each workaround, so Kondooit can satisfy that capability directly rather than reproducing the indirection.

## Status

Research not yet begun. The areas below are hypotheses to investigate, not verified workarounds. Do not assert that any of these are definitely workarounds until source analysis verifies them.

## Known Areas To Investigate

### *arr download-client workflows
To be investigated. Many applications pretend to be download clients or communicate with download clients in ways shaped by the *arr ecosystem rather than by the underlying capability.

### Sonarr/Radarr compatibility
To be investigated. Some applications emulate Sonarr/Radarr APIs or generate data structures solely so *arr apps recognize them.

### Debrid virtual downloads
To be investigated. Debrid integrations may simulate download-client workflows to fit into *arr-driven pipelines.

### Symlink / file-based integrations
To be investigated. Some applications create symlinks or generate filesystem structures so other apps treat remote content as local.

### Media-server compatibility
To be investigated. Integrations with Jellyfin, Emby, Plex, etc. may involve compatibility-specific metadata, API shapes, or file layouts.

### IPTV compatibility
To be investigated. IPTV integrations may involve format conversion, playlist normalization, or protocol emulation for compatibility.

### EPG interoperability
To be investigated. EPG data may be fetched, transformed, or generated in shapes dictated by downstream consumers rather than by the source.

### API spoofing
To be investigated. Some applications expose fake APIs pretending to be another application to integrate with tools that expect that application.

### Virtual filesystem mechanisms
To be investigated. Mounting, FUSE, virtual folders, and similar mechanisms may exist to make remote content appear local to apps that only understand local files.

---

## Workaround Entry Format

Once research populates this document, each entry should follow:

```markdown
### Workaround: <name>

- **Existing Project(s):**
- **Problem:**
- **Existing Solution:**
- **External Constraint:**
- **Underlying Capability:**
- **Why Kondooit May Not Need It:**
- **Potential Kondooit Approach:**
- **Evidence:**
- **Confidence:** VERIFIED / INFERRED / UNCERTAIN
```

Do not assert that a workaround can be removed until the underlying constraint has been understood and verified against source code.
