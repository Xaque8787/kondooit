# a4kScrapers Research Notes

## Overview

**Repository:** https://github.com/Goldenfreddy0703/a4kScrapers
**Original:** https://github.com/a4k-openproject/a4kScrapers (upstream, now less active)
**Type:** Provider package (plugin) for Prism, Seren, and a4kStreaming
**License:** GPL
**Current version:** 2.99.126
**Language:** Python

a4kScrapers is a provider package — a collection of torrent scrapers that plug into host addons (Prism, Seren, a4kStreaming) to provide source discovery capability. It is the most commonly used provider package in the Prism/Seren ecosystem.

The package does **one thing**: given content identification (IMDB/TVDB IDs, title, year, season, episode), it searches torrent indexer sites and aggregator services and returns a list of torrent sources (info_hashes, release titles, file sizes). It does NOT handle debrid resolution, playback, or metadata — those are the host addon's responsibilities.

---

## Repository Structure

```
a4kScrapers/
├── providers/                    # Individual scraper modules
│   ├── __init__.py
│   └── a4kScrapers/
│       └── en/                   # Language namespace
│           └── torrent/          # Scraper type (torrent vs hoster)
│               ├── leet.py       # 1337x scraper
│               ├── piratebay.py  # PirateBay scraper
│               ├── yts.py        # YTS scraper
│               ├── eztv.py       # EZTV scraper
│               ├── torrentio.py  # Torrentio (Stremio addon) scraper
│               ├── comet.py      # Comet (Stremio addon) scraper
│               ├── mediafusion.py# MediaFusion aggregator scraper
│               ├── nyaa.py       # Nyaa anime scraper
│               └── ...           # ~29 total scrapers
│
├── providerModules/              # Shared framework / core library
│   ├── __init__.py
│   └── a4kScrapers/
│       ├── __init__.py
│       ├── core.py               # Base scraper classes, orchestration
│       ├── request.py            # HTTP request handling
│       ├── urls.py               # Domain/URL configuration per scraper
│       ├── utils.py              # Shared utilities
│       ├── source_utils.py       # Source parsing, title matching, quality detection
│       ├── third_party/          # Bundled dependencies (cloudscraper, etc.)
│       └── ...
│
├── meta.json                     # Version metadata, update URLs
├── CHANGELOG.md
└── README.md
```

### Key structural conventions:

1. **`providers/`** contains individual scraper modules — one Python file per torrent site or aggregator service. Each file is a self-contained scraper.

2. **`providerModules/`** contains the shared framework that all scrapers depend on — base classes, HTTP utilities, URL management, title matching, quality detection.

3. **Language namespace (`en/`)** — scrapers are organized by language. Most scrapers are under `en/` (English). This allows the host addon to load only language-relevant scrapers.

4. **Type namespace (`torrent/`)** — scrapers are categorized by type. The torrent directory contains scrapers that return torrent info_hashes. A `hosters/` directory could exist for direct-link scrapers (less common in a4kScrapers).

5. **`meta.json`** — contains version number and remote update URL. The host addon checks this for automatic updates.

---

## Scraper Categories

### Stremio / Aggregators (10 scrapers)

| Scraper | Target | Notes |
|---|---|---|
| `torrentio` | Torrentio Stremio addon | Queries Torrentio's API for cached torrent results |
| `comet` | Comet Stremio addon | Similar to Torrentio, different aggregation source |
| `mediafusion` | MediaFusion | Aggregates multiple torrent sources |
| `aiostreams` | AIOStreams | Meta-aggregator wrapping other Stremio addons |
| `dmm` | Debrid Media Manager | Queries DMM's torrent index |
| `meteor` | Meteor addon | Stremio-ecosystem aggregator |
| `torrentsdb` | TorrentsDB | Torrent database/index |
| `torz` | Torz | Torrent aggregator |
| `zilean` | Zilean | DMM hash list indexer |
| `bitmagnet` | Bitmagnet | DHT crawler / torrent index |

**Key insight:** These scrapers don't scrape HTML torrent sites. They query structured APIs from the Stremio addon ecosystem. This means a4kScrapers acts as a **bridge** between the Kodi provider-package interface and the Stremio addon ecosystem, translating between two different plugin architectures.

### General Torrent Sites (12 scrapers)

| Scraper | Target | Notes |
|---|---|---|
| `leet` | 1337x | Major general torrent site |
| `piratebay` | The Pirate Bay | Classic torrent index |
| `yts` | YTS/YIFY | Movie-focused, known for small encodes |
| `eztv` | EZTV | TV show focused |
| `kickass` / `kickass2` | KickassTorrents | General torrent site (mirrors) |
| `knaben` | Knaben | Torrent meta-search |
| `magnetdl` | MagnetDL | General torrent site |
| `torrentdownload` | TorrentDownloads | General torrent site |
| `torrentproject2` | Torrent Project | Torrent search engine |
| `torrentz2` | Torrentz2 | Meta-search engine |
| `bitsearch` | BitSearch | Torrent search engine |

These are traditional HTML scrapers — they make HTTP requests to torrent sites, parse the HTML response, and extract torrent info_hashes and metadata.

### Anime (5 scrapers)

| Scraper | Target | Notes |
|---|---|---|
| `nyaa` | Nyaa.si | Primary anime torrent tracker |
| `animetosho` | AnimeTosho | Anime torrent aggregator |
| `anirena` | AniRena | Anime torrent tracker |
| `nekobt` | NekoBT | Anime torrent tracker |
| `subsplease` | SubsPlease | Anime fansub group |

Added by Goldenfreddy0703's fork to support Prism's anime capabilities.

### Other (2 scrapers)

| Scraper | Target | Notes |
|---|---|---|
| `cached` | Local cache DB | Queries a pre-built hash database |
| `showrss` | ShowRSS | RSS-based TV show tracker |

---

## Provider Interface Contract

Each scraper module must conform to the interface expected by the host addon (Prism/Seren). Based on the Seren/Prism provider loading system, each scraper module exposes a `source` class with these methods:

### Required Methods

```python
class source:
    def __init__(self):
        # Initialize scraper state, set configuration
        pass

    def movie(self, imdb, title, localtitle, aliases, year):
        """
        Search for movie sources.
        
        Args:
            imdb: IMDB ID (e.g., "tt1234567")
            title: English title
            localtitle: Localized title
            aliases: Alternative titles
            year: Release year
            
        Returns:
            list[dict] — list of source result dictionaries
        """
        pass

    def episode(self, url, imdb, tvdb, title, premiered, season, episode):
        """
        Search for TV episode sources.
        
        Args:
            url: (varies by implementation)
            imdb: IMDB ID of the series
            tvdb: TVDB ID of the series
            title: Series title
            premiered: Air date
            season: Season number
            episode: Episode number
            
        Returns:
            list[dict] — list of source result dictionaries
        """
        pass
```

### Source Result Format

Each source result is a dictionary with these fields:

```python
{
    "release_title": "Movie.Name.2024.1080p.BluRay.x264-GROUP",  # Full release name
    "hash": "abc123def456...",           # Torrent info_hash (40-char hex)
    "quality": "1080p",                  # Detected quality tier
    "size": 2147483648,                  # File size in bytes (or as string "2.0 GB")
    "source": "1337x",                   # Name of the scraper/site that found this
    "type": "torrent",                   # Source type (torrent, hoster, direct)
    # Optional fields:
    "seeds": 150,                        # Seed count (if available)
    "magnet": "magnet:?xt=urn:btih:...", # Full magnet link (if hash not extractable)
    "url": "https://...",                # Direct URL (for hoster sources)
    "info": ["HDR", "HEVC", "DTS"],      # Parsed quality tags
}
```

The **info_hash** is the critical field. It's what the host addon sends to debrid services for cache checking and resolution. The release_title is used for quality detection and ranking. Everything else is supplementary.

---

## The Shared Framework (`providerModules/`)

The `providerModules/a4kScrapers/` directory contains the shared infrastructure that all scrapers build on.

### Core Components

**`core.py` — Base scraper classes:**
- Provides base classes that individual scrapers inherit from
- Handles the common flow: construct search query → make HTTP request → parse results → filter by title match → return sources
- Differentiates between "torrent" scrapers (HTML scraping) and "aggregator" scrapers (API querying)
- Manages threading and timeout behavior

**`request.py` — HTTP request handling:**
- Wraps Python's `requests` library with Kodi-compatible networking
- Handles CloudFlare protection (via `cloudscraper` bundled in `third_party/`)
- Manages rate limiting, retries, and timeouts
- Provides session management (cookie persistence across requests)
- Handles domain fallback (if primary domain is down, try mirrors)

**`urls.py` — URL/domain configuration:**
- Maps each scraper name to its current domain(s)
- Provides domain mirror/fallback lists
- Centralizes URL configuration so individual scrapers don't hardcode domains

**`source_utils.py` — Source parsing and quality detection:**
- Parses release titles to extract quality attributes:
  - Resolution: 2160p/4K, 1080p, 720p, SD
  - Codec: HEVC/H.265, H.264/AVC, AV1
  - HDR: Dolby Vision, HDR10+, HDR10
  - Audio: Atmos, TrueHD, DTS-HD MA, DD5.1, AAC
  - Source type: BluRay, WEB-DL, WEBRip, HDTV, CAM
- Provides title matching / filtering:
  - Verifies scraped results actually match the requested content
  - Handles common title variations, year mismatches, etc.
  - Filters out false positives (e.g., sequel with similar name)

**`utils.py` — General utilities:**
- Hash extraction from magnet links
- Size parsing (string → bytes)
- String normalization for comparison
- HTML entity decoding

### Scraper Inheritance Pattern

Individual scrapers follow a pattern like:

```python
# providers/a4kScrapers/en/torrent/leet.py (conceptual)

from providerModules.a4kScrapers import core

class source(core.TorrentScraper):
    def __init__(self):
        super().__init__(
            name="1337x",
            url="https://1337x.to",
            search_path="/search/{query}/1/"
        )

    def _parse_results(self, html):
        # Site-specific HTML parsing to extract:
        # - release titles
        # - torrent detail page URLs
        # - seeds/peers counts
        # Returns list of raw results
        pass

    def _get_hash(self, result):
        # Follow detail page URL, extract magnet link, parse info_hash
        pass
```

The base class (`core.TorrentScraper`) handles:
1. Constructing the search query from title/year/season/episode
2. Making the HTTP request with proper headers and CloudFlare handling
3. Calling the subclass's `_parse_results()` to get raw results
4. Filtering results by title match
5. Calling `_get_hash()` for each matching result
6. Building the standardized source dict
7. Returning the source list

This means individual scrapers only need to implement:
- How to parse the specific site's HTML (`_parse_results`)
- How to extract the info_hash from that site's detail/magnet page (`_get_hash`)

### Aggregator Scraper Pattern

The Stremio/aggregator scrapers work differently:

```python
# providers/a4kScrapers/en/torrent/torrentio.py (conceptual)

from providerModules.a4kScrapers import core

class source(core.AggregatorScraper):
    def __init__(self):
        super().__init__(
            name="torrentio",
            base_url="https://torrentio.strem.fun"
        )

    def _query(self, content_type, imdb_id, season=None, episode=None):
        # Build Stremio manifest API URL:
        # /stream/movie/{imdb_id}.json
        # /stream/series/{imdb_id}:{season}:{episode}.json
        #
        # Parse JSON response containing stream objects
        # Each stream object has: infoHash, title, fileIdx
        # Return as standardized source dicts
        pass
```

Key difference: aggregator scrapers query a **structured JSON API** rather than parsing HTML. They receive info_hashes directly in the API response — no need to follow detail pages or parse magnet links. This makes them faster and more reliable than HTML scrapers.

---

## How the Host Addon Uses a4kScrapers

The integration flow between Prism/Seren and a4kScrapers:

### 1. Installation

- User provides a URL to the provider package ZIP (GitHub zipball URL)
- Host addon downloads and extracts the ZIP
- Provider modules are loaded into the addon's Python environment
- `meta.json` is read for version tracking

### 2. Discovery Phase

When user selects content to play:

1. Host addon collects content identifiers (IMDB ID, title, year, season, episode)
2. Host addon iterates over all enabled scrapers from all installed provider packages
3. Each scraper's `movie()` or `episode()` method is called in a **thread pool** (parallel execution)
4. A progress dialog shows: "Searching... Found X sources"
5. After timeout (configurable, ~15-20 seconds), scraping stops
6. All source results from all scrapers are aggregated into a single list

### 3. Post-Discovery (handled by host, not a4kScrapers)

7. Host addon extracts all info_hashes from the source list
8. Hashes are sent to debrid service(s) for cache checking
9. Sources are ranked (cached first, then by quality/size)
10. User picks a source (or auto-play selects the best)
11. Selected hash is resolved through debrid to an HTTPS stream URL

**a4kScrapers' responsibility ends at step 6** — it returns source dictionaries and is done. Everything after is the host addon's domain.

---

## Stremio Addon Bridge Pattern (Architecturally Significant)

The most architecturally interesting aspect of a4kScrapers is how it bridges two different plugin ecosystems:

**Stremio addons** (Torrentio, Comet, MediaFusion, etc.) expose a standardized REST API:
```
GET /stream/{type}/{id}.json
→ { streams: [{ infoHash, title, fileIdx, ... }] }
```

**Seren/Prism provider packages** expose a Python class interface:
```python
source.movie(imdb, title, ...) → [{ hash, release_title, ... }]
source.episode(url, imdb, tvdb, ...) → [{ hash, release_title, ... }]
```

a4kScrapers' aggregator scrapers translate between these:
1. Accept Seren/Prism's method call with content identifiers
2. Construct the Stremio API URL from those identifiers
3. Make an HTTP request to the Stremio addon's API
4. Parse the JSON response
5. Translate Stremio stream objects into Seren/Prism source dicts
6. Return the translated results

This is an **ecosystem adapter** — it allows Kodi users to access the Stremio addon ecosystem's source discovery through Prism/Seren's interface. It's not a genuine capability; it's integration plumbing.

**Relevance to Kondooit:** Kondooit should NOT reproduce this bridging pattern. Instead, Kondooit should define its own source provider interface and implement Torrentio/Comet/MediaFusion as native Kondooit providers. The Stremio manifest API format is useful reference for what data these services return, but the adapter layer is an ecosystem workaround.

---

## Architecture Analysis

### What a4kScrapers Actually Does (Capability Extraction)

| Capability | Description |
|---|---|
| **Torrent site scraping** | Parse HTML from torrent indexers to extract info_hashes and metadata |
| **Aggregator API querying** | Query Stremio-ecosystem APIs for pre-indexed torrent results |
| **Title matching** | Verify that scraped results match the requested content |
| **Quality detection** | Parse release titles to extract quality/codec/HDR/audio attributes |
| **Domain management** | Handle mirror URLs, domain changes, CloudFlare protection |
| **Result normalization** | Convert site-specific formats into a standardized source dict |

### Genuine Domain Capabilities vs. Implementation Details

**Genuine capabilities relevant to Kondooit:**

1. **Source discovery as a pluggable interface** — The contract is clean: content identity in → source list out. This validates Kondooit's ADR-0012 (resolution providers as installable modules).

2. **Release title parsing** — Extracting quality attributes from filenames is shared infrastructure needed across all source providers. a4kScrapers' `source_utils.py` implements this comprehensively. Kondooit already has a basic version in the Easynews provider (`_detect_quality`, `_detect_codec`) but could benefit from a more complete shared implementation.

3. **Title matching / verification** — Ensuring scraped results actually match the requested content is non-trivial. Titles have variations, sequels have similar names, foreign titles differ. This is validation logic that any source provider needs.

4. **The aggregator pattern** — While the bridge itself is an ecosystem workaround, the underlying insight is valid: some source providers query centralized indexes (Zilean, Bitmagnet, TorrentDB) rather than individual sites. Kondooit's source provider interface should accommodate both "search and scrape" and "query an index" patterns.

**Implementation details (not portable):**

1. **CloudFlare bypass** — Site-specific anti-bot workaround. Kondooit's server-side providers may encounter similar challenges but would handle them differently (server-side requests with proper session management).

2. **Kodi-specific networking** — Uses Kodi's URL resolver and Python `requests`. Kondooit uses its own HTTP client infrastructure.

3. **ZIP package distribution** — Ecosystem packaging constraint. Kondooit providers are server-side Python modules.

4. **HTML parsing per site** — Each traditional scraper's HTML parsing is site-specific and fragile (breaks when sites change layout). This is the cost of scraping vs. querying structured APIs.

### Ecosystem Workarounds Identified

1. **The entire Stremio bridge** — Aggregator scrapers exist because Kodi's ecosystem and Stremio's ecosystem are separate. In a unified system like Kondooit, you'd implement Torrentio/Comet as native providers, not wrap them through a translation layer.

2. **Domain mirror management** — Torrent sites frequently change domains. a4kScrapers centralizes mirror lists in `urls.py`. This is an ecosystem reality that any system scraping these sites must handle, but it's operational maintenance rather than domain architecture.

3. **CloudFlare handling** — Bundling `cloudscraper` to bypass anti-bot protection is a workaround for the adversarial relationship between scrapers and sites. Server-side providers in Kondooit may face this too but handle it at the infrastructure level.

4. **Thread-pool scraping** — Running scrapers in parallel threads on the client is necessary because Kodi addons are client-side and need to complete within a UI timeout. Kondooit's server-side architecture can use async I/O, background jobs, or pre-indexed caches instead.

---

## The Source Provider Interface for Kondooit

a4kScrapers demonstrates what the minimum viable source provider interface looks like:

### Input (what the provider receives)

```
ContentQuery:
  content_type: "movie" | "episode"
  imdb_id: str          # Primary external identifier
  tvdb_id: str | None   # For TV content
  title: str            # English title
  aliases: list[str]    # Alternative titles
  year: int             # Release year (movie) or premiere year (series)
  season: int | None    # For episodes
  episode: int | None   # For episodes
```

### Output (what the provider returns)

```
SourceResult:
  release_title: str    # Full release name (used for quality parsing)
  info_hash: str        # Torrent info_hash (40-char hex) — the critical identifier
  size_bytes: int       # File size
  quality: str          # Detected quality tier (2160p, 1080p, 720p, SD)
  provider_name: str    # Which provider found this
  source_site: str      # Which site/service it came from
  seeds: int | None     # Seed count (if available)
  # Parsed attributes (from release title):
  codec: str | None     # HEVC, H.264, AV1
  hdr: str | None       # DV, HDR10+, HDR10
  audio: str | None     # Atmos, TrueHD, DTS-HD, DD5.1
  source_type: str | None  # BluRay, WEB-DL, HDTV, CAM
```

### The contract is simple

**In:** "What do you have for this movie/episode?"
**Out:** "Here are N torrent sources with their hashes and metadata."

The provider does NOT:
- Check debrid cache status (that's the debrid provider's job)
- Rank sources against each other (that's the core's job)
- Resolve hashes to stream URLs (that's the debrid provider's job)
- Handle playback (that's the playback orchestrator's job)

This clean separation of concerns is the most valuable architectural lesson from a4kScrapers.

---

## Comparison with Existing Kondooit Providers

### Current state

Kondooit already has source providers (Easynews, TorBox) in `server/kondooit/infrastructure/providers/`. Comparing the interface:

| Aspect | a4kScrapers | Kondooit (current) |
|---|---|---|
| Interface | Python class with `movie()` / `episode()` | Port interface in application layer |
| Input | Positional args (imdb, title, year, ...) | Structured query objects |
| Output | List of dicts | Domain objects |
| Quality parsing | Comprehensive shared `source_utils.py` | Basic per-provider (`_detect_quality`) |
| Title matching | Shared verification framework | Per-provider or absent |
| Hash extraction | Scraper-specific | N/A (Easynews uses direct URLs, TorBox has API) |

### Gaps and opportunities

1. **Release title parsing should be shared** — Both Easynews and TorBox providers need to parse release titles. a4kScrapers demonstrates this should be a shared utility, not duplicated per provider. Kondooit should extract this into a shared infrastructure module.

2. **Title matching should be shared** — Verifying that a source result actually matches the requested content is important for avoiding false positives. This should be infrastructure, not per-provider logic.

3. **The provider interface should support both hash-based and URL-based sources** — a4kScrapers returns torrent hashes. Easynews returns direct download URLs. TorBox may return either. The source result type should accommodate both.

---

## Summary

a4kScrapers is the practical demonstration of what a source discovery plugin system looks like in production. Its key contributions to Kondooit's understanding:

1. **The provider contract is simple and clean**: content identity in → source list out. Each provider is independent and knows only about its target site/service.

2. **Shared infrastructure matters**: Release title parsing, title matching, and HTTP request handling are shared across all scrapers. Duplicating these per provider is wasteful and error-prone.

3. **Two scraper patterns exist**: HTML scrapers (parse torrent site pages) and API scrapers (query structured APIs like Stremio addons, Zilean, Bitmagnet). Kondooit's provider interface should accommodate both.

4. **The Stremio bridge is an ecosystem workaround**, not an architectural pattern to reproduce. Kondooit should implement Torrentio/Comet/MediaFusion as native providers rather than wrapping them through a translation layer.

5. **The info_hash is the universal currency** of the torrent source ecosystem. Every torrent source ultimately provides a hash; every debrid service consumes a hash. This is the junction point between source discovery and source resolution.

6. **Fragility is inherent in HTML scraping** — sites change layouts, domains change, CloudFlare blocks requests. API-based source discovery (aggregators, indexes) is more reliable. Kondooit should prefer structured API providers where available.
