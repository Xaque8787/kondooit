# Kondooit Scraper Module — Source Categorization

**Date:** 2026-08-24
**Status:** Research / planning
**Purpose:** Consolidated categorization of all scrapers found across a4kScrapers, CocoScrapers, and MagnetoScrapers, classified by configuration requirements.

---

## Architecture Summary

```
User configures Source Provider (TorBox, Easynews — credentials, one-time)
  → User installs Scraper Module (zero config)
    → All Tier 1 scrapers active immediately
    → User can toggle individual scrapers on/off
    → User can optionally configure Tier 2 scrapers (instance URLs, etc.)
  → Search for content → get results → resolve via Source Provider
```

**Scraper Module** = a bundle of individual scrapers that discover torrent info_hashes and source metadata. These are the "discovery" layer. They find what exists; they don't resolve it into playable streams.

**Source Provider** (TorBox, Easynews, etc.) = the "resolution" layer. Takes discovered hashes, checks cache, resolves to playable URLs. Requires personal credentials.

---

## Tier 1 — Zero-Config (Public, On by Default)

These scrapers target public services that require no authentication, no API key, and no instance URL. They work immediately upon installation.

### Stremio Aggregators (Public Instances)

| Scraper | Target | Content | Found In | Notes |
|---|---|---|---|---|
| **torrentio** | Torrentio | Movies, TV | a4k, Coco, Magneto | Public instance at torrentio.strem.fun. JSON API, no auth. Most reliable aggregator. |
| **mediafusion** | MediaFusion | Movies, TV | a4k, Coco, Magneto | Public instance available. JSON API, no auth. |

### General Torrent Sites

| Scraper | Target | Content | Found In | Status (2025) | Notes |
|---|---|---|---|---|---|
| **1337x** | 1337x.to | Movies, TV | a4k, Coco, Magneto | Working | 2-request HTML parse (slow but reliable). Major general torrent site. |
| **piratebay** | The Pirate Bay | Movies, TV | a4k, Coco, Magneto | Working | API-based. Classic torrent index. |
| **ytsmx** | YTS/YIFY | Movies only | a4k, Coco, Magneto | Working | Uses IMDB ID query. Small encodes, movies only. |
| **eztv** | EZTV | TV only | a4k, Coco, Magneto | Working | TV shows only. Does not do pack files. |
| **knaben** | Knaben | Movies, TV | a4k, Coco, Magneto | Working | Torrent meta-search aggregator. |
| **kickass2** | KickassTorrents | Movies, TV | a4k, Coco, Magneto | Working | Mirror-based, intermittent uptime. |
| **bitsearch** | BitSearch | Movies, TV | a4k, Coco, Magneto | Working | Torrent search engine. |
| **torrentdownload** | TorrentDownloads | Movies, TV | a4k, Coco, Magneto | Working | General torrent site. |
| **torrentproject2** | Torrent Project | Movies, TV | a4k, Coco, Magneto | Working | Torrent search engine. |
| **torrentgalaxy** | TorrentGalaxy | Movies, TV | Coco, Magneto | Working | May use CloudFlare (fragile). |
| **torrentfunk** | TorrentFunk | Movies, TV | Coco | Working | 2-request HTML parse. |
| **yourbittorrent** | YourBitTorrent | Movies, TV | Coco | Working | Slow (priority 9 in CocoScrapers). |
| **isohunt2** | isoHunt | Movies, TV | Coco | Working | Mirror-based. |
| **bitcq** | BitCQ | Movies, TV | Coco | Working | Single-request HTML parse. |
| **bitlord** | BitLord | Movies, TV | Coco | Working | API-based (fast). |
| **torrentquest** | TorrentQuest | Movies, TV | Coco | Working | Mirror of MagnetDL. |

### Anime

| Scraper | Target | Content | Found In | Notes |
|---|---|---|---|---|
| **nyaa** | Nyaa.si | Anime | a4k, Coco, Magneto | Primary anime torrent tracker. Public. |
| **animetosho** | AnimeTosho | Anime | a4k | Anime torrent aggregator. Public. |
| **anirena** | AniRena | Anime | a4k | Anime torrent tracker. Public. |
| **subsplease** | SubsPlease | Anime | a4k | Anime fansub releases. Public. |

### Other

| Scraper | Target | Content | Found In | Notes |
|---|---|---|---|---|
| **showrss** | ShowRSS | TV | a4k | RSS-based TV show tracker. Public. |
| **rutor** | Rutor | Movies, TV | Magneto | Russian torrent tracker. Public. |
| **torlock** | Torlock | Movies, TV | Magneto | Public torrent site. |

---

## Tier 2 — Requires Configuration (Off by Default)

These scrapers require at minimum an instance URL, API key, or account to function. They are disabled by default and show a "configure to enable" state in the UI.

### Self-Hosted Aggregators (Need Instance URL)

| Scraper | Target | Config Required | Found In | Notes |
|---|---|---|---|---|
| **comet** | Comet | Instance URL + debrid config | a4k, Coco, Magneto | Self-hosted Stremio addon. User must run their own instance with their debrid credentials baked into the URL. |
| **zilean** | Zilean | Instance URL | a4k, Magneto | DMM hash list indexer. Must be self-hosted or community instance. Fast (pre-indexed hashes). |
| **bitmagnet** | Bitmagnet | Instance URL | a4k, Magneto | Self-hosted DHT crawler. Powerful but requires dedicated infrastructure. |
| **dmm** | Debrid Media Manager | Instance URL | a4k, Magneto | Self-hosted or community instance. Torrent index from DMM hash lists. |

### Self-Hosted Indexer Managers (Need URL + API Key)

| Scraper | Target | Config Required | Found In | Notes |
|---|---|---|---|---|
| **prowlarr** | Prowlarr | URL + API key | Coco, Magneto | Self-hosted indexer manager. Aggregates many private/public indexers behind one API. Powerful but complex setup. |

### Unclear / Possibly Configurable

| Scraper | Target | Config Required | Found In | Notes |
|---|---|---|---|---|
| **meteor** | Meteor addon | Likely instance URL | a4k, Magneto | Stremio ecosystem aggregator. Public instance status unclear. |
| **torrentsdb** | TorrentsDB | Likely instance URL | a4k, Magneto | Torrent database/index. Public instance status unclear. |
| **torz** | Torz | Likely instance URL | a4k, Magneto | Torrent aggregator. Public instance status unclear. |
| **aiostreams** | AIOStreams | Configuration URL | a4k | Meta-aggregator wrapping other Stremio addons. Requires building a config URL. |

---

## Dead / Removed Scrapers (Do Not Implement)

Based on CocoScrapers' 2025 update and cross-referencing status:

| Scraper | Reason | Notes |
|---|---|---|
| torrentz2 | Download links no longer work | Removed from Coco 06-27-23 |
| limetorrents | CloudFlare v2, fails | Removed from Coco early 2025 |
| ext/extratorrent | CloudFlare v2 | Removed |
| knightcrawler | Fails | Removed from Magneto early 2025 |
| magnetdl | Referenced in a4k but status unclear | Listed in a4k, not in Coco/Magneto 2025 working lists |
| torrentparadise | Dead site | Historical |
| btdb, btdig, btscene | Dead sites | Historical |
| glodls, zooqle, idope | Not in any current working package | Likely dead or degraded |

---

## Recommended Kondooit v1 Scraper Module — Default Set

For the first scraper module release, prioritize scrapers that are:
1. Present in multiple packages (validated by multiple communities)
2. Confirmed working as of early 2025
3. Cover both movies and TV content
4. Include at least one anime source

### Recommended Tier 1 Defaults (enabled on install)

| Priority | Scraper | Why |
|---|---|---|
| 1 | **torrentio** | Most reliable, fastest, returns pre-indexed cached results. Public API. In all 3 packages. |
| 2 | **mediafusion** | Second major aggregator. Public API. In all 3 packages. |
| 3 | **1337x** | Largest general torrent site. In all 3 packages. Confirmed working 2025. |
| 4 | **piratebay** | Classic index, API-based (fast). In all 3 packages. |
| 5 | **knaben** | Meta-search aggregator, fast. In all 3 packages. |
| 6 | **eztv** | Best for TV-specific content. In all 3 packages. |
| 7 | **ytsmx** | Best for movies (small, fast encodes). In all 3 packages. |
| 8 | **bitsearch** | Good general search. In all 3 packages. |
| 9 | **torrentdownload** | Good general fallback. In all 3 packages. |
| 10 | **nyaa** | Anime coverage. In all 3 packages. |
| 11 | **kickass2** | Additional coverage. In all 3 packages. |
| 12 | **torrentproject2** | Additional meta-search. In all 3 packages. |

### Recommended Tier 1 Optional (disabled by default, toggle to enable)

| Scraper | Why disabled by default |
|---|---|
| torrentgalaxy | CloudFlare issues, intermittent |
| torrentfunk | Slow (2-request parse) |
| yourbittorrent | Very slow (priority 9) |
| isohunt2 | Marginal additional coverage |
| bitcq | Marginal additional coverage |
| bitlord | May overlap with others |
| torrentquest | Mirror of MagnetDL |
| animetosho | Niche (anime only) |
| anirena | Niche (anime only) |
| subsplease | Niche (anime fansub only) |
| showrss | RSS only, limited |
| rutor | Russian content primarily |
| torlock | Marginal coverage |

### Tier 2 (configure to enable)

| Scraper | Config needed |
|---|---|
| comet | Instance URL (self-hosted) |
| zilean | Instance URL |
| bitmagnet | Instance URL |
| dmm | Instance URL |
| prowlarr | URL + API key |
| meteor | Instance URL (pending verification) |
| torrentsdb | Instance URL (pending verification) |
| torz | Instance URL (pending verification) |
| aiostreams | Configuration URL |

---

## Implementation Approach

### Scraper Types (Implementation Categories)

Based on analyzing the code patterns across all three packages, scrapers fall into two implementation categories:

**1. API Scrapers (Stremio-protocol / JSON API)**

These query structured REST APIs and receive JSON with info_hashes directly:
- torrentio, mediafusion, comet, zilean, bitmagnet, dmm, meteor, torrentsdb, torz, aiostreams
- Pattern: `GET {base_url}/stream/{type}/{imdb_id}.json` or similar
- Fast, reliable, no HTML parsing
- Returns: `{ streams: [{ infoHash, title, ... }] }` or equivalent

**2. HTML Scrapers (Site-specific parsers)**

These make HTTP requests to torrent websites and parse HTML to extract info_hashes:
- 1337x, piratebay, ytsmx, eztv, knaben, kickass2, bitsearch, torrentdownload, torrentproject2, nyaa, etc.
- Pattern: construct search URL → parse HTML → extract hashes/magnet links
- Slower, fragile (breaks when sites change), may face CloudFlare
- Some are 1-request (search returns magnet links directly), some are 2-request (search → detail page → magnet link)

### Shared Infrastructure Needed

1. **Release title parser** — quality/codec/HDR/audio detection from filenames (shared across all scrapers)
2. **Title matcher** — verify results match requested content (avoid false positives)
3. **HTTP client** — handles retries, timeouts, user-agent rotation, basic CloudFlare v1
4. **Domain manager** — handles mirror URLs for sites that frequently change domains
5. **Scraper registry** — loads/manages enabled scrapers, provides toggle UI

### Per-Scraper Toggle Storage

Each scraper's enabled/disabled state stored per-user in the database:
- `scraper_module_settings` table with user_id, scraper_key, enabled (boolean)
- Default state defined in the scraper module's manifest
- UI shows toggle list grouped by category (Aggregators, General, Anime, Configurable)

---

## Relationship to Existing Architecture

This scraper module concept maps to the existing Kondooit architecture as follows:

- **Scraper Module** = a collection of source providers implementing the `SourceProvider` interface (ADR-0012)
- **Individual scrapers** = specific `SourceProvider` implementations with `HASH_DISCOVERY` capability
- **Per-scraper toggles** = provider enable/disable (ADR-0010 capability declaration)
- **Tier 2 configuration** = provider settings (existing `source_provider_credentials` table)

The scraper module does NOT replace the existing TorBox/Easynews source providers — those are resolution providers. The scraper module provides the discovery layer that feeds hashes INTO those resolution providers.

---

## Scraper Module Installation Mechanism

### Installation Sources

A scraper module can be installed from three sources. All three are **explicit admin actions** triggered from the UI — nothing auto-loads on server startup.

| Source | Format | Example | Use Case |
|---|---|---|---|
| **GitHub URL** | Repository URL | `https://github.com/kondooit/scrapers-default` | Production — downloaded as zip via GitHub API |
| **ZIP URL** | Direct link to .zip | `https://releases.example.com/scrapers-v1.2.0.zip` | Production — any HTTP-hosted archive |
| **Local path** | Container filesystem path | `/scraper_modules/kondooit-scrapers-default` | Development — directory mounted into container |

**No git dependency.** Remote sources are always fetched via HTTP (curl/wget equivalent — Python `httpx`/`aiohttp`). GitHub repos are downloaded as zip archives using the GitHub archive URL pattern (`https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip`). This keeps the container lightweight and works with any HTTP-accessible host, not just GitHub.

### Installation Flow

All three sources go through the same explicit install flow triggered by the admin in the UI:

```
Admin navigates to Source Resolvers settings page
  → Clicks "Install Module"
  → Enters source: URL or local container path
  → Server validates source:
  │
  ├─ GitHub URL → construct archive URL → HTTP GET .zip → extract to temp
  ├─ ZIP URL → HTTP GET .zip → extract to temp
  └─ Local path → verify directory exists on container filesystem
  │
  ├─ Validate: check for manifest.json at root of extracted/referenced dir
  ├─ For remote: copy to persistent install location /data/scraper_modules/{module-id}/
  ├─ For local: register path as-is (no copy — reads directly from mount)
  ├─ Register: store module metadata + source fingerprint in database
  ├─ Load scrapers: import individual scrapers from the module
  └─ Apply defaults: enable Tier 1 scrapers, disable Tier 2
  │
  → Module appears in UI with per-scraper toggle list
```

**Key distinction for local path:** The server does NOT auto-scan or auto-load from `/scraper_modules/`. The admin must still go through the install flow and explicitly provide the path. This keeps the experience consistent — you always "install" a module, whether remote or local. The only difference is that local modules read from the mounted directory directly (changes reflect on next search) while remote modules are extracted to a persistent volume.

### Package Format (What's Inside)

A scraper module is a directory (or zip) with this structure:

```
kondooit-scrapers-default/
├── manifest.json          ← required: module identity + scraper declarations
├── scrapers/
│   ├── torrentio.py       ← one file per scraper
│   ├── mediafusion.py
│   ├── piratebay.py
│   ├── 1337x.py
│   ├── nyaa.py
│   └── ...
└── shared/                ← optional: shared utilities used by scrapers
    ├── html_parser.py
    ├── stremio_protocol.py
    └── ...
```

### manifest.json

```json
{
  "id": "kondooit-scrapers-default",
  "name": "Kondooit Default Scrapers",
  "version": "1.0.0",
  "description": "Default scraper bundle for Kondooit — public torrent sites and aggregators",
  "min_kondooit_version": "0.1.0",
  "scrapers": [
    {
      "key": "torrentio",
      "name": "Torrentio",
      "type": "api",
      "category": "aggregator",
      "content_types": ["movie", "series"],
      "tier": 1,
      "default_enabled": true,
      "config_schema": null
    },
    {
      "key": "1337x",
      "name": "1337x",
      "type": "html",
      "category": "general",
      "content_types": ["movie", "series"],
      "tier": 1,
      "default_enabled": true,
      "config_schema": null
    },
    {
      "key": "zilean",
      "name": "Zilean",
      "type": "api",
      "category": "aggregator",
      "content_types": ["movie", "series"],
      "tier": 2,
      "default_enabled": false,
      "config_schema": {
        "instance_url": { "type": "url", "label": "Zilean Instance URL", "required": true }
      }
    }
  ]
}
```

**Key fields:**
- `tier: 1` = zero-config, works immediately
- `tier: 2` = needs configuration before enabling
- `default_enabled` = initial toggle state on install
- `config_schema` = null means no config needed; otherwise defines what the UI should show
- `type` = "api" (JSON/REST) or "html" (HTML parsing) — informational, affects timeout defaults
- `category` = "aggregator", "general", "anime", "configurable" — for UI grouping

### Local Development Setup

During development, the scraper module source lives inside the project at:

```
scraper_modules/
└── kondooit-scrapers-default/
    ├── manifest.json
    ├── scrapers/
    │   ├── torrentio.py
    │   └── ...
    └── shared/
        └── ...
```

This directory is mounted into the server container via docker-compose:

```yaml
# docker-compose.yml (server service)
volumes:
  - ./scraper_modules:/scraper_modules:ro
```

**The module is NOT auto-loaded.** The developer must still install it through the UI (or a seed/bootstrap script) by providing the container path `/scraper_modules/kondooit-scrapers-default`. This ensures the install flow is exercised during development and behaves identically to production.

Once installed with a local path:
- Scraper logic changes (editing `.py` files) take effect on the next source search — no restart needed.
- Manifest changes (adding/removing scrapers) require re-install or a "reload" action in the UI.
- The module's `source_type` is recorded as `"local"` in the database.

### Remote Installation (Production)

When an admin provides a GitHub URL or ZIP URL via the UI:

1. **Download:** Server makes an HTTP GET request (no git, no shell commands) to fetch the .zip archive.
   - GitHub URLs: transformed to `https://github.com/{owner}/{repo}/archive/refs/heads/main.zip`
   - ZIP URLs: fetched directly
2. **Extract:** Unzipped to a temp directory.
3. **Validate:** Check for `manifest.json` at the root (or one level deep if the zip contains a wrapper directory).
4. **Install:** Copy validated contents to persistent volume: `/data/scraper_modules/{module-id}/`
5. **Fingerprint:** Compute and store a content hash (SHA-256 of manifest.json + all scraper files concatenated) for update detection.
6. **Register:** Store module metadata, source URL, and fingerprint in the database.
7. **Load:** Import scrapers and apply default toggle states.

### Update Mechanism

Scraper modules change frequently (sites change their HTML, APIs evolve, new scrapers are added). Kondooit provides both passive and active update detection.

#### Fingerprinting (How We Detect Changes)

At install time, the server computes and stores a **content fingerprint**:

```
fingerprint = SHA-256(manifest.json content + sorted concatenation of all scraper/*.py files)
```

This fingerprint represents "what is currently installed."

#### Update Check Process

| Source Type | How We Check | What We Compare |
|---|---|---|
| **GitHub URL** | HTTP GET the archive zip, extract to temp, compute fingerprint | Stored fingerprint vs. new fingerprint |
| **ZIP URL** | HTTP HEAD first — check `ETag` / `Last-Modified` / `Content-Length` headers. If any differ from stored values, download and compute fingerprint. If headers unavailable or inconclusive, full download + fingerprint. | Stored HTTP headers + fingerprint vs. current |
| **Local path** | Recompute fingerprint from the mounted directory | Stored fingerprint vs. current filesystem state |

#### Passive Check (Background — "Update Available" Badge)

The server runs a periodic background task (configurable interval, default every 6 hours):

1. For each installed remote module, performs a lightweight check:
   - **ZIP URL:** HTTP HEAD request only — checks if `ETag`, `Last-Modified`, or `Content-Length` differ from stored values. Zero bandwidth if headers haven't changed.
   - **GitHub URL:** HTTP HEAD on the archive URL, or optionally use the GitHub API `GET /repos/{owner}/{repo}/commits/{branch}` to check the latest commit SHA (single lightweight API call, no download).
2. If the remote source appears different:
   - Sets a flag in the database: `update_available = true`
   - The UI shows an "Update Available" badge on the Source Resolvers page next to the module.
3. If the remote source appears unchanged:
   - No action, no badge.
4. **Local modules:** Fingerprint is recomputed from disk on every check. If files changed since install, badge appears with "Reload Available" instead.

The passive check **never auto-updates** — it only sets the badge. The admin must explicitly trigger the update.

#### Active Update (Admin-Triggered — "Update" Button)

When the admin clicks "Update" (or "Reload" for local modules):

1. **Download** the current remote source (full HTTP GET of zip).
2. **Extract** to temp, compute new fingerprint.
3. **Compare** to installed fingerprint. If identical, report "already up to date."
4. If different:
   - **Overwrite** the installed files completely (full replacement, not merge).
   - Update the stored fingerprint, version (from new manifest), and `updated_at` timestamp.
   - Reload scrapers from the new files.
   - Preserve user toggle/config state (scraper_settings table is keyed by scraper_key — if a scraper_key still exists in the new manifest, its toggle state is preserved; if removed, the setting is cleaned up; if new, defaults apply).
5. Show a summary: "Updated from v1.0.0 to v1.1.0 — 2 scrapers added, 1 removed."

#### For Local Modules (Reload)

Local modules use "Reload" instead of "Update" since the source is already on disk:

1. Re-read manifest.json from the mounted path.
2. Recompute fingerprint.
3. If different from stored: reload scrapers, update stored manifest data + fingerprint.
4. If same: report "no changes detected."

#### Stored Update Metadata

Added to the `scraper_modules` table:

| Column | Type | Description |
|---|---|---|
| content_fingerprint | text | SHA-256 fingerprint at install/update time |
| remote_etag | text | Last known ETag from remote server (null for local) |
| remote_last_modified | text | Last known Last-Modified header (null for local) |
| remote_content_length | bigint | Last known Content-Length (null for local) |
| last_checked_at | timestamptz | Last time passive check ran |
| update_available | boolean | Flag for UI badge (default false) |
| github_commit_sha | text | For GitHub sources: last known commit SHA |

### Database Storage

**`scraper_modules` table** — tracks installed modules:

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| module_id | text | From manifest.json `id` field |
| name | text | Human-readable name |
| version | text | Semver version from manifest |
| source_type | text | "github", "zip_url", "local" |
| source_url | text | Original URL or container path |
| install_path | text | Filesystem path where module lives |
| content_fingerprint | text | SHA-256 hash of installed content |
| remote_etag | text | ETag header from last download (null for local) |
| remote_last_modified | text | Last-Modified header (null for local) |
| remote_content_length | bigint | Content-Length header (null for local) |
| github_commit_sha | text | Latest commit SHA for GitHub sources |
| update_available | boolean | Flag for "update available" badge (default false) |
| last_checked_at | timestamptz | Last time update check ran |
| installed_at | timestamptz | Installation timestamp |
| updated_at | timestamptz | Last update/reload timestamp |

**`scraper_settings` table** — per-user scraper toggle state:

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid | FK to users |
| module_id | text | FK reference to module |
| scraper_key | text | e.g., "torrentio", "1337x" |
| enabled | boolean | Toggle state |
| config | jsonb | Tier 2 config (instance URL, etc.) — null for Tier 1 |

### Security Considerations

- Scraper modules execute arbitrary Python on the server. This is an **admin-only** operation — only the server administrator can install modules.
- The UI should clearly warn that installing a module executes third-party code.
- Local path mounting (development) is inherently trusted (developer controls the filesystem).
- Remote installs: consider optional checksum/signature verification in future. For v1, admin trust is sufficient (same trust model as Docker images).
- Scrapers run in the server process but should be sandboxed from core application state (no direct database access — they receive structured inputs and return structured outputs).

### Scraper Interface Contract

Each scraper file must export a class (or object) implementing this contract:

```python
class Scraper:
    # Called by the module loader to verify the scraper is functional
    async def health_check(self) -> bool: ...

    # Discover sources for a movie
    async def search_movie(
        self,
        imdb_id: str,
        title: str,
        year: int,
        config: dict | None = None,  # Tier 2 scrapers receive their config here
    ) -> list[ScraperResult]: ...

    # Discover sources for a TV episode
    async def search_episode(
        self,
        imdb_id: str,
        title: str,
        season: int,
        episode: int,
        config: dict | None = None,
    ) -> list[ScraperResult]: ...
```

`ScraperResult` is a simple dict/dataclass:

```python
@dataclass
class ScraperResult:
    info_hash: str           # 40-char hex hash
    title: str               # Release name (e.g., "Movie.2024.1080p.WEB-DL.x265-GROUP")
    size_bytes: int | None   # File size if known
    seeders: int | None      # Seeder count if known
    source: str              # Which scraper found this (auto-set by loader)
```

The server's source discovery service calls all enabled scrapers concurrently, collects results, deduplicates by `info_hash`, and passes hashes to the resolution layer (TorBox cache check, etc.).

### Multi-Provider Resolution and Result Display

**Decision:** When multiple source providers (TorBox, AllDebrid, Premiumize, etc.) are configured, the system queries ALL of them in parallel with the discovered hashes. Results are displayed as **separate rows per provider**, not deduplicated.

**Rationale:** The user should see every available resolution path explicitly. If the same hash is cached on both TorBox and Premiumize, that appears as two rows — each tagged with the provider name. This gives the user conscious control over which provider resolves/plays the content.

**Flow:**

```
Scrapers discover hashes (provider-agnostic)
  → Deduplicate hashes (same hash from multiple scrapers = one hash)
  → Fan out hashes to ALL configured CACHE_CHECK providers (in parallel)
  → Each provider returns: which hashes it has cached + file details
  → Results presented as: one row per (hash × provider) combination
  → Each row shows: release name, quality, size, provider badge
  → User selects which row to play → resolves through that specific provider
```

**Key points:**
- Scraper-level dedup: yes (same hash found by multiple scrapers = one hash sent to providers)
- Provider-level dedup: NO (same hash cached on two providers = two result rows)
- Each result row is tagged with which provider can serve it
- Sort by quality/size as primary criteria, provider priority as secondary
- Future enhancement: auto-select mode that deduplicates by hash using provider priority + user preferences

**Responsibilities separation:**
- Scraper module: discovers info_hashes (knows nothing about debrid providers)
- Source providers (TorBox, etc.): server-side infrastructure — implement CACHE_CHECK and RESOLVE using their specific APIs
- Server orchestration: fans out hashes to all providers, collects results, merges into unified response
- UI: renders results with provider badges, user picks one

### Development Workflow

1. Create `scraper_modules/kondooit-scrapers-default/manifest.json`
2. Write first scraper (e.g., `scrapers/torrentio.py`)
3. Mount into Docker via docker-compose volume
4. Server loads on startup, scraper appears in the UI
5. Toggle on/off, run source searches, iterate on scraper logic
6. When ready for release: push directory to GitHub, users install via URL

---

## Open Questions

1. ~~**Should the scraper module be "built-in" or truly installable?**~~ **Resolved:** Installable from day one, using local path for development and URLs for production.

2. **Concurrent execution strategy?** All enabled scrapers should run concurrently with a global timeout (e.g., 15 seconds). Individual scraper failures should not block others.

3. **Rate limiting / politeness?** Some torrent sites may rate-limit or block if hit too aggressively. Need per-scraper rate limit configuration.

4. ~~**Result deduplication?**~~ **Resolved:** Deduplicate at the scraper level (same hash from multiple scrapers = one hash). Do NOT deduplicate at the provider level (same hash on TorBox + Premiumize = two result rows). User picks which provider to use. Auto-select/dedup is a future enhancement.

5. **Meteor, TorrentsDB, Torz classification?** Need to verify whether these have stable public instances or require self-hosting. Currently classified as Tier 2 (conservative).

6. **Module update mechanism?** Should the system auto-check for updates, or only update when the user manually triggers it? For v1, manual-only is simpler.

7. **Multiple modules?** Can a user install multiple scraper modules (e.g., a "default" module plus a community "anime-extras" module)? Architecture supports it (module_id scoping) but v1 could restrict to one active module.
