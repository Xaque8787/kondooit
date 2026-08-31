# Projects

Per-existing-project analyses. One file per project: `PROJECT-<name>.md`.

## Target projects (non-exhaustive)

Jellyfin, Sonarr, Radarr, Prowlarr, AIOStreams, Torrentio, Comet, MediaFusion, Decypharr, NZBDAV, AltMount, Dispatcharr, Threadfin, and potentially others.

## Per-project analysis template

```
# <Project Name>

## Overview
What the project is and what it does.

## Capabilities
What capabilities it actually provides (verified against source).

## Capability classification
- Intrinsic domain functionality
- Adapters
- Ecosystem workarounds
- Overlaps with other projects

## Reusability
- Reusable implementation code
- Portions to rewrite because the new architecture eliminates original constraints

## Placement hypothesis
Which capabilities belong in core vs. provider/plugin interface (subject to ADR).

## Source references
File/line citations for key claims.

## Status
Confirmed / Assumption / Open question — per claim.
```

## Rules

- Do not write a project file until the project's source has been inspected.
- No project files exist yet.
