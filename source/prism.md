# Prism Research Notes

## Overview

**Repository:** https://github.com/Goldenfreddy0703/Prism
**Type:** Kodi video addon (plugin.video.prism)
**Origin:** Community-maintained fork of [Seren](https://github.com/nixgates/plugin.video.seren) by Nixgates
**License:** GPL-3.0
**Status:** Early release

Prism is an all-in-one Kodi addon for Movies, TV Shows, and Anime. It inherits Seren's core architecture — a multi-source addon with a modular provider package system — and extends it with anime support, Simkl integration (replacing/supplementing Trakt), a theme system, and additional debrid service support.

The addon description states: "Prism is a modular provider based, cloud service streaming software that is tightly interwoven with Simkl."

---

## Repository Structure

```
Prism/
├── context.prism/              # Context menu addon (right-click actions)
├── plugin.video.prism/         # Main video addon
│   ├── resources/
│   │   ├── lib/
│   │   │   ├── debrid/         # Debrid service integrations
│   │   │   │   ├── real_debrid.py
│   │   │   │   ├── premiumize.py
│   │   │   │   ├── all_debrid.py
│   │   │   │   ├── torbox.py       # Added by Prism (not in original Seren)
│   │   │   │   └── offcloud.py     # Added by Prism (not in original Seren)
│   │   │   ├── modules/        # Core logic modules
│   │   │   │   ├── resolver.py     # Source resolution and playback orchestration
│   │   │   │   ├── source_utils.py # Source ranking and filtering
│   │   │   │   ├── providers/      # Provider package management
│   │   │   │   └── ...
│   │   │   ├── database/       # SQLite caching layer
│   │   │   ├── indexers/       # Content browsing (movies, tvshows, episodes)
│   │   │   └── gui/            # Custom Kodi windows/dialogs
│   │   └── settings.xml
│   ├── seren.py                # Entry point (retained from Seren)
│   └── service.py              # Background service
├── addon.xml
└── README.md
```

Note: The directory structure is inherited from Seren. Prism's additions are primarily within the existing structure rather than new top-level directories.

---

## Key Concepts

### 1. Provider Packages (External Scrapers)

Provider packages are the core extensibility mechanism inherited from Seren. They are **not bundled with Prism** — users install them separately via the Provider Manager.

**What they are:**
- ZIP files containing Python scraper modules
- Each module knows how to search a specific torrent indexer/site
- They return torrent hashes (info_hashes), magnet links, or direct URLs
- They are installed/updated independently of the main addon

**How they work:**
- Installed via: Prism → Tools → Provider Manager → Install Package
- Each package contains multiple "providers" (individual scrapers)
- Providers can be enabled/disabled individually
- The package system allows the addon to remain "clean" while users choose their own source discovery modules

**Architecture insight:** This is a plugin system where source discovery is fully externalized. The core addon knows nothing about specific torrent sites — it just calls provider packages through a standard interface and receives back a list of source results.

**Relevance to Kondooit:** This maps directly to Kondooit's provider/plugin architecture (ADR-0002, ADR-0012). The separation between core and source discovery is the same pattern Kondooit intends, though Kondooit would implement providers as server-side modules rather than client-side Python scripts.

### 2. Debrid Services

Debrid services are the primary playback mechanism. Prism supports:
- **Real-Debrid** (most popular)
- **Premiumize**
- **AllDebrid**
- **TorBox** (added by Prism)
- **Offcloud** (added by Prism)

**What debrid services do:**
1. Accept torrent hashes
2. Report which hashes are already cached on their CDN (instant availability check)
3. For cached hashes: provide direct HTTPS download/stream URLs
4. For uncached hashes: optionally queue them for downloading/caching
5. Act as a CDN — the user streams from the debrid service's servers, not from torrent peers

**Key distinction:** Debrid services are NOT source discovery — they are source resolution. They transform a torrent hash (which is just an identifier) into a playable stream URL.

### 3. Local File Playback

Added by Prism (not in original Seren). Users can point Prism at a local/network folder and play files directly. This bypasses both provider packages and debrid services entirely.

---

## Source Resolution Flow (The Critical Path)

This is the most architecturally significant process in Prism/Seren. It describes how the system goes from "user wants to watch Movie X" to "video is playing."

### Step 1: Source Scraping (Discovery)

When a user selects content to play:

1. The addon identifies the content (TMDB/TVDB/IMDB IDs, title, year, season/episode)
2. All enabled provider packages are called in parallel (threaded scraping)
3. Each provider searches its target site(s) for matching torrents
4. Providers return source objects containing:
   - `release_title` — the filename/release name
   - `info_hash` — torrent hash (the critical identifier)
   - `size` — file size
   - `quality` — parsed quality (4K/1080p/720p/SD)
   - `source` — the source site name
   - `type` — torrent, hoster, or direct
   - Additional metadata (codec, HDR, audio format, etc.)
5. Results are aggregated into a single source list
6. A scraping progress dialog shows the user how many sources were found

**Timeout:** Scraping has a configurable timeout (default ~15-20 seconds). After timeout, whatever has been found so far is used.

### Step 2: Cache Checking (Debrid Availability)

This is what separates Seren/Prism from simpler addons:

1. All discovered torrent hashes are collected
2. These hashes are sent in batch to the user's configured debrid service(s)
3. The debrid service returns which hashes are **already cached** on its CDN
4. Sources are tagged as "cached" or "uncached"

**Why this matters:**
- A cached source = instant playback (the debrid service already has the file)
- An uncached source = the debrid service would need to download the torrent first (minutes to hours)
- Users overwhelmingly prefer cached sources

**Real-Debrid specifics (post-2024 changes):**
- RD changed their API to make batch cache checking less reliable
- Seren 3.0.62+ moved to checking cache status at resolution time (when user actually tries to play)
- This is an ecosystem adaptation, not a fundamental architectural change

### Step 3: Source Ranking and Filtering

After cache checking, sources are ranked:

1. **Pre-emptive filtering:**
   - Remove sources below minimum quality setting
   - Remove sources with excluded keywords (e.g., "CAM", "TS")
   - Apply file size limits
   - Filter by audio language preferences

2. **Ranking criteria (in approximate priority order):**
   - Cached status (cached >> uncached)
   - Quality tier (2160p > 1080p > 720p > SD)
   - HDR presence (Dolby Vision > HDR10+ > HDR10 > SDR)
   - Audio quality (Atmos > TrueHD > DTS-HD > DD5.1 > stereo)
   - Codec preference (HEVC > H.264 for 4K; either for lower res)
   - File size (larger generally preferred within same quality, up to limits)
   - Source reputation/reliability

3. **The `source_utils.py` module** handles parsing release titles to extract quality, codec, HDR format, audio format, and other attributes from the filename string. This is regex-heavy string parsing — the same kind of parsing Kondooit's Easynews provider already does for quality/codec detection.

### Step 4: Presentation (Auto-play vs. Manual)

Two modes:
- **Auto-play:** Automatically selects the highest-ranked source and attempts to play it. If it fails, falls through to the next source.
- **Source select:** Shows the user a ranked list of all sources. User picks one manually.

### Step 5: Resolution (Hash → Stream URL)

When a source is selected for playback:

1. The source's `info_hash` is sent to the debrid service
2. The debrid service returns:
   - For **cached** sources: a direct HTTPS URL to the specific video file
   - For **uncached** sources: initiates caching (user can choose to wait or skip)
3. If the torrent contains multiple files (e.g., a season pack), the resolver must select the correct file:
   - Match by episode number in filename
   - Match by file size (largest video file)
   - Match by file extension (video files only)

**The resolver module (`resolver.py`)** orchestrates this:
- Tries each debrid service in priority order
- Handles fallback if one service fails
- Manages file selection within multi-file torrents
- Returns a playable URL or signals failure

### Step 6: Playback

The resolved HTTPS URL is handed to Kodi's built-in video player. From here, Kodi handles:
- Video decoding
- Subtitle rendering
- Playback controls (pause, seek, etc.)
- Resume position tracking

---

## Architecture Analysis

### What Prism/Seren Actually Does (Capability Extraction)

| Capability | Description | How It Works |
|---|---|---|
| **Content Browsing** | Browse/discover movies, TV shows, anime | Simkl/Trakt API integration, TMDB/TVDB metadata |
| **Source Discovery** | Find available sources for a piece of content | Provider packages scrape indexer sites for torrent hashes |
| **Cache Checking** | Determine if a source is instantly playable | Batch hash lookup against debrid service APIs |
| **Source Ranking** | Order sources by quality and availability | Parse release titles, rank by quality/size/cache status |
| **Source Resolution** | Transform a source identifier into a stream URL | Debrid API: hash → HTTPS download URL |
| **File Selection** | Pick the right file from multi-file torrents | Filename matching within debrid file listings |
| **Playback** | Play the resolved stream | Hand URL to Kodi's built-in player |
| **Progress Tracking** | Track watch progress, watchlist | Simkl/Trakt sync |
| **Local Playback** | Play local/network files | Direct file path to Kodi player |

### Genuine Domain Capabilities vs. Implementation Details

**Genuine domain capabilities (relevant to Kondooit):**

1. **Modular source discovery** — The idea that source discovery is externalized through a plugin interface is architecturally sound. Kondooit already has this in ADR-0012.

2. **Cache-aware source resolution** — The two-phase approach (discover hashes → check cache availability → resolve to stream URL) is the fundamental debrid workflow. This is a genuine capability that Kondooit will need when implementing debrid providers.

3. **Release title parsing** — Extracting quality, codec, HDR, audio format, and other attributes from release filenames. This is shared infrastructure that every source provider needs. Kondooit already has a basic version in the Easynews provider's `_detect_quality` and `_detect_codec`.

4. **Source ranking/filtering** — User-configurable preferences for quality, size, codec that determine which source is "best." This is a core Kondooit capability — source ranking across heterogeneous providers.

5. **Multi-file torrent file selection** — When a source contains multiple files (season packs, extras), the system must identify the correct file. This is debrid-specific infrastructure.

6. **Auto-play with fallback** — Try the best source, fall through to next on failure. Graceful degradation across sources.

**Implementation details (not directly portable):**

1. **Threaded client-side scraping** — Provider packages run as Python threads in the Kodi addon. Kondooit runs providers server-side.

2. **Kodi-specific UI** — Dialog windows, progress bars, context menus. Kondooit has its own web UI.

3. **Kodi player integration** — Handing URLs to `xbmc.Player()`. Kondooit will have its own playback orchestration (ADR-0006).

4. **SQLite caching** — Local client-side cache. Kondooit uses PostgreSQL server-side.

### Ecosystem Workarounds Identified

1. **Provider packages as ZIP files** — This is a Kodi addon ecosystem constraint. Kodi doesn't have a native plugin-within-plugin system, so Seren invented one using ZIP files with Python modules. Kondooit doesn't need this packaging mechanism — server-side providers can be proper Python modules.

2. **Client-side scraping** — Scraping runs on the user's device because Seren has no server. This creates timeout pressure, network constraints, and threading complexity. Kondooit's server-centric architecture eliminates this.

3. **Trakt/Simkl as the content database** — Seren/Prism uses Trakt (and now Simkl) as its source of truth for content identity, watchlists, and progress. This is because a client-side addon has no persistent database. Kondooit owns its own content catalog and identity (ADR-0003).

4. **RD cache check workarounds** — Real-Debrid's API changes forced Seren to move cache checking from batch pre-check to per-resolution check. This is an adaptation to a specific provider's API instability, not an architectural choice. Kondooit should design the cache-check interface to accommodate both batch and per-item checking.

---

## Debrid Integration Deep Dive

### The Debrid Provider Interface (Abstracted)

Looking across Seren/Prism's debrid implementations, they share a common interface pattern:

```
interface DebridProvider:
    authorize()           → OAuth device flow, store token
    check_cache(hashes[]) → {hash: [cached_files]}  
    add_torrent(hash)     → torrent_id
    get_torrent_info(id)  → {files, status, progress}
    resolve(hash, file)   → stream_url (HTTPS)
    delete_torrent(id)    → void
```

Each debrid service implements this differently:

**Real-Debrid:**
- Auth: OAuth2 device code flow
- Cache check: POST `/torrents/instantAvailability/{hash}` (now unreliable for batch)
- Resolve: POST `/torrents/addTorrent` → GET `/torrents/info/{id}` → POST `/unrestrict/link`
- Returns: Direct HTTPS download URL from RD CDN

**Premiumize:**
- Auth: OAuth2 device code flow
- Cache check: GET `/cache/check?items[]={hash}`
- Resolve: POST `/transfer/directdl` with magnet
- Returns: Direct HTTPS stream URL

**AllDebrid:**
- Auth: PIN-based auth
- Cache check: GET `/magnet/instant?magnets[]={hash}`
- Resolve: POST `/magnet/upload` → GET `/magnet/status` → POST `/link/unlock`
- Returns: Direct HTTPS download URL

**TorBox (Prism addition):**
- Auth: API key
- Cache check: GET `/torrents/checkcached?hash={hash}`
- Resolve: POST `/torrents/createtorrent` → GET `/torrents/requestdl`
- Returns: Direct HTTPS stream URL

**Offcloud (Prism addition):**
- Auth: API key
- Different workflow — more download-oriented than streaming

### Key Observation: The Three-Step Debrid Pattern

Despite API differences, every debrid service follows the same logical pattern:

1. **Cache check** — "Do you already have this hash?" → yes/no per hash
2. **Add/claim** — "I want to access this hash" → service acknowledges
3. **Resolve** — "Give me a download URL for this file" → HTTPS stream URL

This three-step pattern is the debrid provider capability interface for Kondooit. The specific API calls differ per service, but the capability contract is consistent.

---

## Comparison: Prism vs. Umbrella (Source Resolution)

| Aspect | Prism (Seren fork) | Umbrella |
|---|---|---|
| **Source discovery** | External provider packages (plugin system) | Built-in scrapers (hardcoded in addon) |
| **Primary playback** | Debrid services (torrent hash → stream) | Debrid + direct hosters + Easynews |
| **Cache checking** | Batch hash check against debrid APIs | Same pattern |
| **Source ranking** | Sophisticated multi-factor ranking | Similar but simpler |
| **Easynews support** | Not built-in (would be in a provider package) | Built-in, first-class |
| **Architecture** | Clean separation: core ↔ providers ↔ debrid | Monolithic: everything in one addon |
| **Extensibility** | Provider package system | Fork-and-modify |
| **Content tracking** | Simkl/Trakt integration | Trakt integration |
| **Local files** | Supported (Prism addition) | Not a focus |

**Key architectural difference:** Prism/Seren has a genuinely modular architecture where source discovery is pluggable. Umbrella is monolithic — all scrapers are built into the addon. Prism's approach is much closer to Kondooit's intended architecture.

---

## Relevance to Kondooit Architecture

### Directly Applicable Patterns

1. **Provider Package Interface** — Prism's provider package contract (search → return hashes with metadata) maps to Kondooit's source provider interface. The key fields are: release title, info_hash, size, quality, type.

2. **Debrid as Source Resolution** — The three-step pattern (cache check → add → resolve) should inform Kondooit's debrid provider capability interface. This is distinct from source discovery.

3. **Source Ranking as a Core Capability** — Prism demonstrates that source ranking is complex enough to be its own module. Kondooit should treat source ranking as a core capability, not something embedded in individual providers.

4. **Release Title Parsing as Shared Infrastructure** — Every source provider needs to parse release titles. This should be a shared utility in Kondooit, not duplicated per provider (currently Easynews has its own basic version).

5. **Auto-play with Fallback** — The pattern of trying sources in ranked order with automatic fallback on failure is a good UX pattern for Kondooit's playback orchestration.

6. **Multi-file Selection** — When a debrid source contains multiple files, the system needs logic to pick the right one. This is infrastructure that sits between source resolution and playback.

### Capabilities Kondooit Should Extract

From Prism's architecture, these are the distinct capabilities:

| Capability | Kondooit Layer | Notes |
|---|---|---|
| Source discovery (scraping) | Source providers (plugins) | Per ADR-0012 |
| Cache availability check | Debrid provider interface | Batch + per-item |
| Source ranking/filtering | Core application service | User preferences + quality heuristics |
| Release title parsing | Shared infrastructure utility | Regex-based attribute extraction |
| Debrid resolution (hash → URL) | Debrid provider interface | Three-step pattern |
| File selection (multi-file) | Debrid provider interface or core | Episode matching within packs |
| Playback orchestration | Core (ADR-0006) | Try ranked sources, fallback |
| Progress tracking | Core user state | Already partially implemented |

### What NOT to Adopt

1. **Client-side provider execution** — Kondooit runs providers server-side. No need for ZIP package distribution or client-side Python execution.

2. **Trakt/Simkl as content database** — Kondooit owns its own catalog (ADR-0003). External tracking services could be sync targets, not sources of truth.

3. **Kodi-specific abstractions** — Window management, settings.xml, xbmc.Player — none of this applies.

4. **Per-resolution cache checking** — RD's API instability forced Seren into this. Kondooit should design for batch cache checking with per-item fallback, not the other way around.

---

## Open Questions for Kondooit

1. **Should debrid providers be a single capability interface or separate capabilities?** Prism treats all debrid services as implementations of one interface. But the capabilities vary (some support streaming, some are download-only, some have cloud storage features). Should Kondooit have a single `DebridProvider` interface or more granular capability declarations?

2. **Where does source ranking live?** Prism's `source_utils.py` is a module within the addon. In Kondooit's layered architecture, source ranking touches both domain logic (quality preferences) and infrastructure (parsing release titles). The ranking rules are arguably domain, while the title parsing is infrastructure.

3. **Should release title parsing be a domain concept or infrastructure?** The parsed attributes (quality, codec, HDR format) are domain concepts. The regex parsing of filenames is infrastructure. Suggesting: domain defines the attribute types, infrastructure provides the parser.

4. **How should Kondooit handle the debrid cache check → resolution flow?** This is a multi-step async process. The UI needs to show: "found 50 sources → 12 cached → playing best match." This suggests an event-driven or streaming API rather than a single request-response.

---

## Summary

Prism/Seren's most valuable contribution to Kondooit's architecture is the **clear separation between source discovery, source resolution, and playback** — and the demonstration that debrid services follow a consistent three-step pattern regardless of API differences. The provider package system validates Kondooit's plugin architecture decisions, and the source ranking system demonstrates that ranking is complex enough to warrant its own dedicated module.

The main thing Prism does that Kondooit should study carefully is the **full pipeline from content selection to playback**: scrape → cache check → rank → resolve → play → fallback. Each step is a distinct capability with its own interface, and the orchestration of these steps is the core value of the system.
