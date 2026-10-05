# Live TV Research — Dispatcharr & Vodstrm Analysis and Implementation Plan

**Date:** 2026-10-05
**Status:** Research (pre-implementation)
**Sources analyzed:** [Dispatcharr](https://github.com/dispatcharr/dispatcharr.git), [Vodstrm](https://github.com/Xaque8787/vodstrm.git)
**Source code:** Cloned to `source/dispatcharr-repo/` and `source/vodstrm-repo/` (git-ignored)

---

## 1. Executive Summary

This document analyzes two existing projects — Dispatcharr (a full-featured IPTV management platform) and Vodstrm (an IPTV VOD-to-strm library generator) — to extract the capabilities Kondooit needs for its live TV and IPTV VOD features. The analysis is based on reading the actual source code of both projects.

Kondooit does not need to replicate Dispatcharr's full feature set. The scope is deliberately limited to:

1. M3U and Xtream Codes provider ingestion
2. XMLTV EPG ingestion
3. Auto-matching channels to EPG entries
4. Channel management (numbering, manual EPG assignment, enable/disable)
5. Per-channel and per-provider user agent assignment
6. Scheduled provider and EPG refresh
7. IPTV VOD content parsed as source candidates for the unified catalog

The plan maps these capabilities onto Kondooit's existing architecture (domain-centric, provider abstraction, layered dependencies) and identifies what to adopt, what to simplify, and what to reject from each project.

---

## 2. Dispatcharr Analysis

Dispatcharr is a Django + Celery application that manages IPTV providers, channels, EPG, stream proxying, DVR recording, and multi-user access. It is a mature, feature-rich platform. The following analysis covers only the areas relevant to Kondooit's scope.

### 2.1 M3U / Xtream Code Provider Ingestion

**Confirmed facts (verified from source code):**

**M3UAccount model** (`apps/m3u/models.py`):
- `account_type` field distinguishes `STD` (standard M3U URL/file) from `XC` (Xtream Codes)
- XC accounts store `server_url`, `username`, `password`; STD accounts store `file_path` or URL
- `user_agent` FK to `core.UserAgent` — per-provider UA
- `max_streams` — concurrent stream limit
- `refresh_interval` (hours) + `refresh_task` FK to `PeriodicTask` — scheduled refresh
- `stale_stream_days` (default 7) — streams not seen in this many days are deleted
- `priority` — used for VOD provider selection when multiple providers offer the same content
- `status` field: idle/fetching/parsing/error/success/pending_setup/disabled

**M3U parsing** (`apps/m3u/tasks.py`):
- `fetch_m3u_lines()` downloads the M3U URL using the account's user agent, streaming to a temp file. Handles `.gz`, `.xz`, `.zip` compression.
- `iter_m3u_entries()` is a generator that walks lines, assembling entries:
  - `#EXTINF:` lines parsed by `parse_extinf_line()` — extracts `key="value"` attributes via regex, then the display name
  - `#EXTGRP:` lines — sets `group-title` if not already in EXTINF attrs
  - `#EXTVLCOPT:` lines — accumulated as VLC options
  - URL lines (http/rtsp/rtp/udp) — completes the pending entry
- `process_m3u_batch_direct()` processes entries in batches with thread-safe DB connections
- Applies `M3UFilter` rules (regex include/exclude by group, name, or url)
- Extracts `tvg-id`, `tvg-logo`, `group-title`, `tvg-chno`, `tv_archive`/`tv_archive_duration`

**Xtream Codes ingestion** (`core/xtream_codes.py` `Client` class):
- `get_live_categories()` → `player_api.php?...&action=get_live_categories`
- `get_all_live_streams()` → fetches ALL live streams in one call, filtered by enabled category IDs
- Each XC stream maps to: `tvg-id` ← `epg_channel_id`, `tvg-logo` ← `stream_icon`, `group-title` ← category name
- Stream URL constructed as `{server_url}/live/{username}/{password}/{stream_id}.ts`
- `tv_archive`/`tv_archive_duration` → catchup support flags

**Stream identity stability** (`Stream.generate_hash_key()`):
- SHA-256 hash of configurable fields (from `CoreSettings.get_m3u_hash_key()`)
- For XC accounts: when `url` is in hash keys, `stream_id` is used instead — ensures credential/URL changes don't break identity
- `m3u_id` always included for XC to prevent cross-account collisions

**M3UFilter** (`apps/m3u/models.py`):
- `filter_type`: "group" | "name" | "url"
- `regex_pattern` — applied case-insensitively
- `exclude` flag — if True, matches are dropped; if False, only matches pass

**Relevance to Kondooit:**
- The STD vs XC distinction is genuine domain logic — two different ingestion protocols with different data shapes. Kondooit should model this similarly.
- The stream hash-based identity is a proven approach for stable references across refreshes. Kondooit should adopt an equivalent.
- M3UFilter is an implementation detail — Kondooit's provider abstraction can handle filtering differently if needed. Not a first-class concern.
- The stale stream cleanup is a practical necessity for any system that re-syncs provider data.

### 2.2 EPG / XMLTV Handling

**Confirmed facts:**

**EPGSource model** (`apps/epg/models.py`):
- `source_type`: "xmltv" | "schedules_direct" | "dummy"
- `url`, `file_path`, `extracted_file_path` — cached XML on disk
- `refresh_interval` + `refresh_task` FK to `PeriodicTask`
- `priority` — higher wins when multiple sources match the same channel

**EPGData model**:
- `tvg_id`, `name`, `icon_url`, `epg_source` FK
- `unique_together = ('tvg_id', 'epg_source')`
- Linked to Channel via FK

**ProgramData model**:
- `epg` FK to EPGData, `start_time`, `end_time`, `title`, `sub_title`, `description`
- `custom_properties` JSON — season/episode numbers, etc.
- Indexed on `(epg, start_time, end_time)`

**XMLTV ingestion** (`apps/epg/tasks.py`):
- `fetch_xmltv()` downloads URL, streams to temp file. Detects compression (gzip/xz/zip) via magic bytes. Extracts to `.xml` cache.
- `parse_channels_only()` uses `lxml.etree.iterparse()` streaming over XML with `tag=('channel', 'programme')`. A `_PrependStream` wrapper injects a DOCTYPE declaring HTML 4 named entities so `&eacute;` etc. resolve correctly.
- Extracts `id` (tvg_id), `display-name`, `icon[src]` from `<channel>` elements. Bulk creates/updates in batches of 500.
- `parse_programs_for_source()` streams XML filtering `<programme>` elements by `channel` attribute. Programs are swapped atomically per-channel (delete old + insert new in one transaction).
- A byte-offset programme index (`EPGSourceIndex`) enables per-channel lazy parsing — seeks directly to relevant XML chunks instead of re-scanning.

**Relevance to Kondooit:**
- XMLTV is the standard EPG format. The streaming SAX parser with entity declaration prepend is a proven technique for large XMLTV files.
- The EPGSource → EPGData → ProgramData three-level model is clean and maps well to Kondooit's domain layer.
- Per-channel lazy parsing is an optimization worth adopting — many channels may never need their programme data parsed.
- Schedules Direct support is out of scope for Kondooit's initial implementation. XMLTV only.
- The DOCTYPE entity prepend is an implementation detail worth noting but not architecturally significant.

### 2.3 Channel-to-EPG Auto-Matching

**Confirmed facts** (`apps/channels/epg_matching.py`):

A 3-tier matching system:

**Tier 1: Exact ID Match**
- Channel's `tvg_id` (lowercased/stripped) looked up in in-memory index. O(1) lookup.
- Also checks `tvc_guide_stationid` (Gracenote ID).

**Tier 2: Fuzzy Match (rapidfuzz)**
- `_fuzzy_scan_core()` computes `fuzz.ratio()` between normalized names.
- Region bonus: EPG entries with matching `.xx` region suffixes in tvg_id get +15; non-matching get -15; plain text match gets +10.
- EPG entries sorted by `epg_source_priority` (higher priority wins ties).
- Tracks top-K candidates (default 20) via a heap.

**Tier 3: ML Validation (sentence-transformers)**
- Uses `all-MiniLM-L6-v2` model (lazy-loaded, cached in `/data/models`).
- Only invoked when fuzzy score is in the "medium" range.
- Can validate the single best candidate or, as a last resort, try ML against all top-K fuzzy candidates.

**Thresholds** (two modes):

| Threshold | Bulk (>1 channel) | Single channel |
|---|---|---|
| FUZZY_HIGH_CONFIDENCE | 90 | 85 |
| FUZZY_SKIP_ML | 80 | 75 |
| FUZZY_MEDIUM_CONFIDENCE | 70 | 40 |
| ML_HIGH_CONFIDENCE | 0.75 | 0.65 |
| ML_LAST_RESORT | 0.65 | 0.50 |
| FUZZY_LAST_RESORT_MIN | 50 | 20 |

Bulk matching uses conservative thresholds to reduce false positives across thousands of channels. Single-channel matching is aggressive since a user explicitly triggered it.

**Name normalization** (`normalize_name()`):
1. Strips configured prefixes/suffixes/custom strings
2. Lowercases
3. Removes `[bracketed]` content
4. Preserves call signs in `(CAPS)` parentheses
5. Removes `(parenthesized)` content
6. Removes non-word characters
7. Filters extraneous words: tv, channel, network, television, east, west, hd, uhd, 24/7, 1080p, 720p, 540p, 480p, film, movie, movies

**Relevance to Kondooit:**
- The 3-tier approach (exact → fuzzy → ML) is the right pattern. However, Kondooit should start with tiers 1 and 2 only. The ML tier adds a sentence-transformers dependency and model download — too heavy for initial implementation.
- The name normalization with extraneous word filtering is directly reusable logic. This is the key to good match rates.
- The two-mode threshold system (conservative for bulk, aggressive for single) is a practical design worth adopting.
- The region bonus is useful but can be deferred if not needed initially.

### 2.4 Channel Management

**Confirmed facts** (`apps/channels/models.py`):

**Channel model:**
- `channel_number` (FloatField — supports decimals like 2.1)
- `name`, `logo` FK, `channel_group` FK, `tvg_id`, `tvc_guide_stationid`
- `epg_data` FK — manual or auto-matched EPG
- `uuid` (UUIDField for stable client-facing IDs)
- `is_catchup`, `catchup_days` — rolled up from streams
- `hidden_from_output` — excludes from output but auto-sync still updates
- `streams` M2M to Stream through `ChannelStream` (with `order` field for failover priority)

**ChannelOverride pattern** — critical design:
- OneToOneField to Channel with nullable fields for `name`, `channel_number`, `channel_group`, `logo`, `tvg_id`, `epg_data`
- Sync writes only to `Channel.*`, never to `ChannelOverride`
- User customizations persist across refreshes
- `effective_*` properties resolve override → channel fallback

**ChannelGroup & ChannelGroupM3UAccount:**
- ChannelGroup: simple name-based grouping
- ChannelGroupM3UAccount: junction with `enabled`, `auto_channel_sync` flags

**Auto channel sync:**
- When `auto_channel_sync=True` on a group, channels auto-create/delete to match provider streams
- Numbering modes: `provider` (use provider's number), `next_available` (lowest free), `fixed` (sequential from cursor)

**Relevance to Kondooit:**
- The ChannelOverride pattern is the most valuable takeaway. Without it, provider refreshes would overwrite user customizations. Kondooit should adopt an equivalent — provider data and user overrides are separate concerns.
- Channel groups are the natural organizing unit. Kondooit should model these.
- The `channel_number` as a float (supporting sub-channels like 2.1) is a proven choice.
- Auto channel sync with numbering modes is useful but can be simplified for initial implementation — `next_available` numbering is sufficient.
- The `hidden_from_output` flag is a good alternative to deletion for channels the user doesn't want to see.

### 2.5 User Agent Assignment

**Confirmed facts:**

**`core.UserAgent` model:** `name`, `user_agent` (UA string), `is_active`.

Three levels of UA assignment:
1. **System default** (`CoreSettings.get_default_user_agent()`) — stored in settings, Redis-cached
2. **Per M3U account** (`M3UAccount.user_agent` FK) — used for M3U downloads and XC API calls
3. **Per Stream Profile** (`StreamProfile.user_agent` FK) — used for external process execution

`M3UAccount.get_user_agent_string()` returns the account's UA if set, else the system default.

**Relevance to Kondooit:**
- Three-level UA assignment is a proven pattern. Some IPTV providers block or behave differently based on the User-Agent string.
- Kondooit should implement: system default UA, per-provider UA override. Per-channel UA is over-engineering for initial scope — per-provider covers the common case.
- A reasonable default UA should be provided (e.g., a common browser UA or VLC UA).

### 2.6 Scheduled Refresh

**Confirmed facts** (`core/scheduling.py`):

- Uses Celery Beat + `django_celery_beat` for periodic task scheduling
- `create_or_update_periodic_task()` supports both interval (hours) and cron schedules
- Per-account: `M3UAccount.refresh_interval` (hours) + `refresh_task` FK
- Per-EPG: `EPGSource.refresh_interval` (hours) + `refresh_task` FK
- Task locking: `acquire_task_lock()` / `release_task_lock()` with `TaskLockRenewer` — Redis-based with auto-renewal, prevents concurrent refreshes of the same source
- Deferral: If refresh is blocked, deferred via `apply_async(countdown=15)` with max retry count

**Relevance to Kondooit:**
- Kondooit does not use Celery or Redis. The scheduled refresh should use a simpler mechanism — APScheduler (like Vodstrm uses) or a lightweight asyncio task scheduler.
- The per-source refresh interval (in hours) is the right model. The user asked for a "simple definable hour interval."
- Task locking to prevent concurrent refreshes is important — without it, a slow M3U download could overlap with the next scheduled run. This can be a simple in-process lock for the initial implementation (single-server model per ADR-0005).
- The deferral/retry pattern is useful but can be simplified — just skip the run if a previous one is still in progress.

### 2.7 Stream Proxy

**Confirmed facts** (`apps/proxy/live_proxy/server.py`):

- gevent-based MPEG-TS proxy server
- Manages `StreamManager` instances per channel (input streams)
- Manages `ClientManager` instances per channel (connected clients)
- Redis pub/sub for multi-worker coordination
- Single upstream → many clients via Redis-backed shared buffer
- One upstream feed shared across all connected clients

**Relevance to Kondooit:**
- Stream proxying is out of scope for this phase. ADR-0014 establishes direct delivery as the default, with proxy as fallback. For live TV, direct delivery means the client fetches the stream URL directly from the IPTV provider.
- The multi-client shared-buffer proxy is a future optimization. Kondooit's initial live TV implementation should hand the stream URL to the client and let it fetch directly.
- Connection counting (max_streams enforcement) is relevant for the future but not for initial scope.

### 2.8 DVR / Recording

Dispatcharr has full DVR support: Recording model, RecurringRecordingRule, comskip, series rules, recording templates. This is noted but explicitly out of scope for Kondooit's live TV implementation. The roadmap does not include DVR.

---

## 3. Vodstrm Analysis

Vodstrm is a Python/FastAPI application that ingests IPTV playlists, classifies content into types (movie, series, live, tv_vod), persists to SQLite, applies filters, and generates `.strm` files on the filesystem. The `.strm` files are consumed by media servers (Jellyfin, Plex, Stremio).

### 3.1 M3U Parsing

**Confirmed facts** (`app/ingestion/parser.py`):

`parse_m3u(file_path, provider, ingest_time, force_vod)` returns a dict with keys: `movies`, `series`, `live_tv`, `tv_vod`, `unsorted`, `batch_id`, `summary`.

Line-by-line state machine:
- `#EXTINF` → parsed by `_parse_extinf()` — splits at last quote to separate attributes from display name. Extracts `tvg-id`, `tvg-logo`, `tvg-name`, `group-title` etc.
- `#EXTGRP:` → stored as group
- Non-`#` line → treated as `stream_url`; current entry is classified and bucketed

**Classification cascade** (`_classify()`, in strict priority order):

| Priority | Condition | Type | Extra fields |
|---|---|---|---|
| 1 | `duration == "-1"` (unless `force_vod`) | `live` | — |
| 2 | Regex `\bS(\d{1,3})[ ._-]?E(\d{1,3})\b` or `\b\d{1,3}xX\d{1,3}\b` | `series` | season, episode |
| 3 | Air-date pattern `\d{4}[ ._-]\d{2}[ ._-]\d{2}` | `tv_vod` | air_date |
| 4 | 4-digit year `\b(19\d{2}|20\d{2})\b` | `movie` | year |
| 5 | Fallback | `unsorted` | — |

`cleaned_title` is derived by trimming the title at the classifying token, then stripping trailing `._- `.

**Content-addressable identity** (`_make_entry_id`):
- SHA-256 of `type:cleaned_title_lower:season:episode:year:air_date`
- Same content from different providers produces the same `entry_id` — enables cross-provider deduplication

**`force_vod` flag**: When true, the `duration == "-1"` → live check is skipped. Entries fall through to series/movie/unsorted classification. This allows treating "live" duration entries as VOD.

**Relevance to Kondooit:**
- The classification cascade is directly relevant. Kondooit needs to separate live channels from VOD content in M3U playlists. The priority order (live duration → SxxExx → air-date → year → unsorted) is a proven heuristic.
- The content-addressable identity is a good approach for VOD deduplication across providers. Kondooit should adopt an equivalent for IPTV VOD entries.
- The `force_vod` flag is important — some providers mark everything as live duration even for VOD content. Kondooit should support this.
- The `_IngestionLogger` pattern (per-line error catching, continue parsing) is practical for handling malformed playlists gracefully.

### 3.2 Xtream Codes API

**Confirmed facts** (`app/ingestion/xtream_native.py`):

**`XtreamClient`** wraps the Xtream Player API at `{base}/player_api.php`:
- `get_json(action, **extra)`: GET with `username`, `password`, `action` params. 60s timeout. Raises redacted errors (never exposes credentials).
- `authenticate()`: calls with no action, checks `user_info.auth == "1"`

**Endpoints called** (in `build_parsed_result`):

| Player API action | Purpose |
|---|---|
| (no action) | Authentication |
| `get_live_streams` | All live channel entries |
| `get_vod_streams` | All VOD/movie entries |
| `get_series` | All series summaries (catalog) |
| `get_live_categories` | Category ID → name map for live |
| `get_vod_categories` | Category ID → name map for VOD |
| `get_series_categories` | Category ID → name map for series |
| `get_series_info` (per series) | Episode details (lazy, on-demand) |

**Two-tier series handling:**
1. **Catalog tier** (`xtream_series_catalog` table): `get_series` returns all series summaries in one call. DELETE + bulk INSERT per provider. Makes every known series browseable before episodes are fetched.
2. **Cache tier** (`xtream_series_cache` table): Episode details per series, fetched on demand via `get_series_info`. Normalizes nested `{season_key: [episode, ...]}` into flat list. Deduplicates by `(season, episode)`.

**Playback URL construction** (`_playback_url`):
`{base}/{media_type}/{username}/{password}/{stream_id}.{extension}`
- Extension: `m3u8` if `stream_format == "hls"` else `ts`
- If `direct_source` is a valid HTTP(S) URL, used directly instead

**`ensure_series_loaded(title)`**: Lazy episode materialization — triggered when a user browses a series. Re-fetches series info, normalizes episodes, persists entries, runs filters, generates strm files.

**Relevance to Kondooit:**
- The Xtream API endpoint enumeration is directly reusable. These are the standard Xtream Codes Player API endpoints.
- The two-tier series handling (catalog first, episodes lazy) is an important pattern. Fetching all series info upfront would be hundreds of API calls. The catalog-then-lazy approach is practical.
- The `force_vod` concept applies to XC too — XC separates live/VOD/series natively via different API endpoints, so `force_vod` is less relevant for XC than for M3U.
- The redacted error pattern (never expose credentials in error messages) is a security best practice Kondooit should adopt.
- For Kondooit's purposes, the lazy series loading is less critical — Kondooit's VOD ingestion can be a background process that eventually fetches all series info. But the catalog-first approach is still valuable for making content quickly browseable.

### 3.3 STRM File Generation

**Confirmed facts** (`app/tasks/strm.py`):

`generate_strm()` is an idempotent global reconciliation:
- Evaluates ALL eligible streams across ALL providers
- Selects one winner per entry (lowest priority number, ties broken by provider slug)
- Syncs the filesystem (write new, update URL changed, move path changed, skip unchanged)
- Three cleanup passes: delete excluded, delete superseded by download, clear losers
- Orphan sweep: walks filesystem tree, deletes any .strm not in DB

`.strm` file format: plain text, one line, just the stream URL.

**Winner selection** (`_winning_stream_ids`):
- Joins streams → entries → providers
- Requires `is_active=1`, `exclude=0`, include_only check
- Requires `type != 'live'` (live excluded from strm)
- ORDER BY `priority, slug` — first row per entry wins

**Relevance to Kondooit:**
- Kondooit does NOT need .strm files. This is a Vodstrm-specific concept for media server integration. Kondooit is the media server.
- What Kondooit DOES need from this: the winner selection logic. When multiple IPTV providers offer the same VOD content, Kondooit should select one as the primary source (by priority). This maps to Kondooit's existing source provider priority concept (ADR-0011).
- The stale cleanup pattern (delete streams whose batch_id doesn't match current) is relevant for Kondooit's refresh logic.
- The orphan sweep concept is relevant — after refresh, any content that was removed from the provider should be cleaned up from Kondooit's catalog.

### 3.4 "Generate All" vs "Import Selected"

**Confirmed facts:**

Two modes controlled by `providers.strm_mode`:

- **`generate_all`** (default): All non-excluded streams generate .strm files automatically. Full mirror of provider catalog minus excluded content.
- **`import_selected`**: Only streams explicitly marked `imported=1` generate .strm files. Follow rules and manual Add/Remove control what's imported.

The user specified Kondooit should focus on the "generate all" implementation only. This simplifies the design — no follow rules, no manual import/export, no import_selected mode.

**Relevance to Kondooit:**
- Kondooit should implement "generate all" only: ingest all VOD content from configured IPTV providers, classify it, and make it available as source candidates in the unified catalog.
- No follow rules, no manual import selection, no .strm files.
- The VOD content becomes another source type in Kondooit's source discovery pipeline. When a user searches for sources for a movie, IPTV VOD matches appear alongside Debrid and Easynews results.

### 3.5 Database Models

**Confirmed facts** (`app/database.py`):

Key tables:
- `providers`: `type` (m3u/xtream/local_file), `strm_mode`, `priority`, `is_active`, `stream_format`, `force_vod`, `quality_terms` (JSON)
- `entries`: `entry_id` (deterministic hash), `type` (movie/series/live/tv_vod/unsorted), `cleaned_title`, `year`, `season`, `episode`, `air_date`, `cover_art`, `tmdb_id`
- `streams`: `entry_id` FK, `stream_url`, `provider`, `batch_id`, `metadata_json`, filter output columns, `strm_path`, `last_written_url`
- `xtream_series_catalog`: per-provider series summaries
- `xtream_series_cache`: per-provider per-series episode cache

**Relevance to Kondooit:**
- The entries/streams separation (what content is vs where it comes from) maps directly to Kondooit's content/source distinction (ADR-0002). An entry = content identity; a stream = a source from a specific provider.
- Kondooit should NOT replicate the SQLite schema. Kondooit uses PostgreSQL via SQLAlchemy at the infrastructure layer, with domain entities at the domain layer. The schema design is informative but not prescriptive.

### 3.6 Scheduling

**Confirmed facts** (`app/scheduler.py`):

APScheduler `BackgroundScheduler`:
- `SQLAlchemyJobStore` (sqlite) — jobs persist across restarts
- `ThreadPoolExecutor(20)` — 20 concurrent jobs
- `job_defaults`: `coalesce=True`, `max_instances=1`, `misfire_grace_time=604800`
- Timezone from settings

Task types: `download_all_providers`, `clean_strm_orphans`, `generate_strm`, `process_downloads`. Triggers: cron or interval (seconds).

**Relevance to Kondooit:**
- APScheduler is a lightweight, proven scheduler that fits Kondooit's Python server without requiring Celery + Redis. This is a better fit than Dispatcharr's Celery-based approach.
- `coalesce=True` and `max_instances=1` are important defaults — merge missed runs and prevent overlapping executions.
- Kondooit should use APScheduler (or a similar lightweight scheduler) for both provider refresh and EPG refresh. The scheduler lives in the infrastructure layer.

---

## 4. Capability Classification

Per the project's governing instructions (§5, §14 of CLAUDE.md), every capability found in an existing project must be classified as: intrinsic domain functionality, adapter, ecosystem workaround, or overlap.

### From Dispatcharr

| Capability | Classification | Kondooit? |
|---|---|---|
| M3U parsing | Intrinsic domain functionality | Yes — IPTV provider capability |
| Xtream Codes API client | Intrinsic domain functionality | Yes — IPTV provider capability |
| XMLTV EPG parsing | Intrinsic domain functionality | Yes — EPG capability |
| Channel-to-EPG matching (exact + fuzzy) | Intrinsic domain functionality | Yes — with simplification |
| Channel-to-EPG matching (ML) | Implementation choice | No — too heavy for initial scope |
| Channel model with numbering, groups | Intrinsic domain functionality | Yes — live TV domain |
| ChannelOverride (user customization preservation) | Intrinsic domain functionality | Yes — clean separation of provider vs user data |
| User agent assignment (per-provider) | Intrinsic domain functionality | Yes — provider behavior varies by UA |
| User agent assignment (per-stream-profile) | Implementation choice | No — stream profiles are not in scope |
| Scheduled refresh (interval-based) | Intrinsic domain functionality | Yes — but simpler mechanism |
| Task locking (prevent concurrent refresh) | Implementation detail | Yes — simplified to in-process lock |
| Stream proxy (gevent, Redis buffer) | Implementation choice | No — future capability, not initial scope |
| Connection counting / preemption | Implementation choice | No — future capability |
| DVR / Recording | Feature outside scope | No |
| Schedules Direct | Implementation choice | No — XMLTV only for initial scope |
| Multi-user profiles | Feature outside scope | No — separate roadmap item |
| HDHR / XC output | Ecosystem workaround | No — Kondooit has its own client protocol |

### From Vodstrm

| Capability | Classification | Kondooit? |
|---|---|---|
| M3U parsing (same as Dispatcharr) | Intrinsic domain functionality | Yes |
| Content classification cascade (live/series/movie/tv_vod) | Intrinsic domain functionality | Yes — core VOD ingestion logic |
| Content-addressable identity (SHA-256 of type:title:season:episode:year) | Intrinsic domain functionality | Yes — for VOD dedup across providers |
| `force_vod` flag | Implementation choice | Yes — practical necessity for some providers |
| Xtream Codes API (same endpoints as Dispatcharr) | Intrinsic domain functionality | Yes |
| Two-tier series handling (catalog + lazy episodes) | Implementation choice | Yes — catalog-first for quick browseability |
| .strm file generation | Ecosystem workaround | No — Kondooit IS the media server |
| Filter engine (replace/remove/exclude/include_only) | Implementation choice | Simplified — basic exclude filters only |
| Follow rules (import_selected mode) | Implementation choice | No — generate_all only |
| Download queue | Feature outside scope | No |
| TMDB enrichment | Overlap with existing Kondooit capability | No — Kondooit already has TMDB metadata |
| APScheduler for refresh | Implementation choice | Yes — better fit than Celery for Kondooit |
| Stale stream cleanup | Intrinsic domain functionality | Yes |
| Provider deactivation handover | Implementation detail | Yes — when provider is disabled, sources should be cleaned up |

---

## 5. Implementation Plan for Kondooit

This plan maps the analyzed capabilities onto Kondooit's architecture (domain → application → infrastructure → API) and defines the implementation approach for each of the six scope items plus VOD ingestion.

### 5.1 Scope Summary

1. M3U and Xtream Codes provider ingestion
2. XMLTV EPG ingestion (file or remote URL)
3. Auto-matching channels from M3U/XC to EPG
4. Channel management (numbering, manual EPG, enable/disable)
5. Per-provider and per-channel user agent assignment
6. Scheduled provider/EPG refresh (hour interval)
7. IPTV VOD ingestion as source candidates (generate_all approach)

### 5.2 Architectural Placement

All live TV concepts are new domain entities. They follow the existing Kondooit layering:

```
domain/
  channel.py          (NEW — Channel, ChannelGroup, ChannelOverride)
  epg.py              (NEW — EPGSource, EPGChannel, Program)
  iptv_vod.py         (NEW — VODEntry, VODStream — IPTV VOD content identity)

application/
  iptv_ports.py       (NEW — IPTVProviderPort, EPGSourcePort)
  iptv_service.py     (NEW — ingestion orchestration, channel sync)
  epg_service.py      (NEW — EPG matching, program data queries)
  vod_ingestion_service.py (NEW — VOD parsing, classification, dedup)

infrastructure/
  iptv/
    m3u_parser.py     (NEW — M3U playlist parsing)
    xtream_client.py  (NEW — Xtream Codes API client)
    xmltv_parser.py   (NEW — XMLTV streaming parser)
    scheduler.py      (NEW — APScheduler setup, refresh jobs)
  iptv_repo.py        (NEW — SQLAlchemy repos for channel/EPG/VOD models)
  models.py           (EXTEND — new ORM models for channel/EPG/VOD tables)

api/
  live_tv.py          (NEW — channel listing, EPG data, channel management)
  iptv_admin.py       (NEW — provider config, refresh triggers, EPG config)
```

### 5.3 Domain Layer

#### Channel domain (`domain/channel.py`)

```python
class ChannelStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    HIDDEN = "hidden"

@dataclass(frozen=True)
class ChannelGroup:
    id: UUID
    name: str
    provider_id: UUID | None  # None for user-created groups

@dataclass(frozen=True)
class Channel:
    id: UUID
    name: str                  # provider-supplied name
    channel_number: float      # supports sub-channels (2.1)
    group_id: UUID | None
    logo_url: str | None
    tvg_id: str | None         # from M3U/XC
    epg_channel_id: UUID | None  # matched or manually assigned
    provider_id: UUID          # which IPTV provider this channel came from
    stream_url: str            # direct stream URL
    user_agent: str | None     # per-channel UA override
    status: ChannelStatus
    is_catchup: bool = False
    catchup_days: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass(frozen=True)
class ChannelOverride:
    """User customizations that persist across provider refreshes."""
    channel_id: UUID
    name: str | None              # override display name
    channel_number: float | None  # override channel number
    group_id: UUID | None         # override group
    logo_url: str | None          # override logo
    epg_channel_id: UUID | None   # manually assigned EPG
    user_agent: str | None        # per-channel UA override
```

**Key decisions:**
- Channel uses a `status` enum (enabled/disabled/hidden) instead of separate boolean flags. `hidden` preserves the channel for re-sync but excludes it from the client-facing list.
- ChannelOverride is a separate dataclass, matching Dispatcharr's proven pattern. Provider refresh writes to Channel; user edits write to ChannelOverride. The effective value is override → channel fallback.
- `stream_url` is on Channel (not a separate Stream entity) because live channels have exactly one stream URL. Multi-stream failover (Dispatcharr's ordered ChannelStream) is a future capability.
- `user_agent` appears on both Channel and ChannelOverride — per-channel UA is part of the scope.

#### EPG domain (`domain/epg.py`)

```python
@dataclass(frozen=True)
class EPGSource:
    id: UUID
    name: str
    source_type: str          # "xmltv" only for now
    url: str | None           # remote URL
    file_path: str | None     # local file
    refresh_interval_hours: int
    priority: int             # higher wins when multiple sources match
    is_active: bool
    last_refreshed_at: datetime | None
    status: str               # idle/fetching/parsing/error/success

@dataclass(frozen=True)
class EPGChannel:
    id: UUID
    epg_source_id: UUID
    tvg_id: str               # XMLTV channel id
    name: str                 # display-name from XMLTV
    icon_url: str | None

@dataclass(frozen=True)
class Program:
    id: UUID
    epg_channel_id: UUID
    start_time: datetime
    end_time: datetime
    title: str
    sub_title: str | None
    description: str | None
    season_number: int | None
    episode_number: int | None
```

**Key decisions:**
- EPGSource → EPGChannel → Program is the same three-level model proven by Dispatcharr. Clean and sufficient.
- `source_type` is a string (not an enum) to allow future source types without domain changes. Only "xmltv" is implemented initially.
- No `EPGSourceIndex` (Dispatcharr's byte-offset index) — that's an infrastructure optimization. The domain model doesn't need it. If parsing performance requires it, it's an infrastructure-layer concern.

#### IPTV VOD domain (`domain/iptv_vod.py`)

```python
class VODType(str, Enum):
    MOVIE = "movie"
    SERIES = "series"
    TV_VOD = "tv_vod"        # air-date-based series
    UNSORTED = "unsorted"

@dataclass(frozen=True)
class VODEntry:
    """Content identity for IPTV VOD content — what the content is."""
    id: UUID
    vod_type: VODType
    cleaned_title: str
    year: int | None
    season: int | None
    episode: int | None
    air_date: date | None
    cover_art_url: str | None
    # Identity hash for cross-provider dedup
    content_hash: str        # SHA-256 of type:cleaned_title_lower:season:episode:year:air_date

@dataclass(frozen=True)
class VODStream:
    """A specific provider's stream for a VOD entry — where it comes from."""
    id: UUID
    vod_entry_id: UUID
    provider_id: UUID        # IPTV provider instance
    stream_url: str
    provider_metadata: str   # JSON blob of raw EXTINF/XC attributes
    last_seen: datetime
```

**Key decisions:**
- VODEntry/VODStream separation mirrors Kondooit's content/source distinction (ADR-0002). VODEntry = what the content is. VODStream = where it comes from.
- `content_hash` is the cross-provider dedup key, based on Vodstrm's proven approach.
- VOD content from IPTV providers becomes source candidates in the unified catalog. When a user views a movie detail page and requests sources, the system queries both debrid/usenet sources AND the IPTV VOD library for matches.
- Matching IPTV VOD to metadata-provider content is title-based fuzzy matching (same approach as channel-to-EPG matching, simpler).

### 5.4 Application Layer

#### IPTV provider ports (`application/iptv_ports.py`)

```python
class IPTVProviderPort(Protocol):
    """Interface for IPTV provider implementations."""
    async def fetch_channels(self) -> list[ChannelFetchResult]: ...
    async def fetch_vod_content(self) -> VODFetchResult: ...
    async def test_connection(self) -> bool: ...

@dataclass
class ChannelFetchResult:
    channels: list[RawChannel]
    groups: list[RawChannelGroup]
    batch_id: str

@dataclass
class VODFetchResult:
    movies: list[RawVODItem]
    series: list[RawVODItem]
    tv_vod: list[RawVODItem]
    unsorted: list[RawVODItem]
    batch_id: str
```

The application layer defines the port. Infrastructure implementations (M3U parser, Xtream client) implement it. The application service orchestrates: call provider → classify → dedup → persist → cleanup stale.

#### EPG matching service (`application/epg_service.py`)

Two-tier matching (exact + fuzzy). No ML tier.

```python
class EPGMatchingService:
    def match_channels_to_epg(
        self, channels: list[Channel], epg_channels: list[EPGChannel]
    ) -> list[ChannelEPGMatch]:
        # Tier 1: exact tvg_id match
        # Tier 2: fuzzy name match (rapidfuzz)
        ...
```

**Name normalization** (adopted from Dispatcharr):
- Lowercase
- Remove bracketed and parenthesized content (preserve CAPS call signs)
- Remove non-word characters
- Filter extraneous words: tv, channel, network, television, east, west, hd, uhd, 24/7, 1080p, 720p, film, movie, movies

**Thresholds** (simplified from Dispatcharr):
- `FUZZY_HIGH_CONFIDENCE = 85` — auto-accept
- `FUZZY_MEDIUM_CONFIDENCE = 60` — store as candidate, don't auto-accept
- Below 60 — no match

Two-mode: bulk (85/60) and single-channel (80/50). Single-channel is more aggressive because the user triggered it explicitly.

#### VOD ingestion service (`application/vod_ingestion_service.py`)

Orchestrates: parse provider → classify entries → compute content hashes → dedup across providers → persist → cleanup stale.

Classification cascade (from Vodstrm, proven):
1. `duration == "-1"` and not `force_vod` → live (skip, not VOD)
2. SxxExx pattern → series
3. Air-date pattern → tv_vod
4. 4-digit year → movie
5. Fallback → unsorted

### 5.5 Infrastructure Layer

#### M3U parser (`infrastructure/iptv/m3u_parser.py`)

Streaming line-by-line parser. Key implementation details from both projects:
- Handle `.gz`, `.xz`, `.zip` compression (magic byte detection)
- `#EXTINF` parsing: split at last quote to separate attributes from display name
- `#EXTGRP` as fallback for group-title
- `#EXTVLCOPT` accumulation (may contain http-user-agent)
- Per-line error catching, continue parsing
- Extract: `tvg-id`, `tvg-logo`, `tvg-name`, `group-title`, `tvg-chno`, `tv_archive`, `tv_archive_duration`, duration, name

#### Xtream Codes client (`infrastructure/iptv/xtream_client.py`)

HTTP client for the Xtream Player API:
- Base URL: `{server}/player_api.php`
- Params: `username`, `password`, `action`
- Endpoints: `get_live_categories`, `get_all_live_streams`, `get_vod_categories`, `get_vod_streams`, `get_series_categories`, `get_series`, `get_series_info`
- Redacted errors (never expose credentials in error messages)
- Connection pooling with retries
- User agent from provider config

For VOD series: catalog-first approach (fetch all series summaries in one call), then batch-fetch series info for episodes. The lazy on-demand approach (Vodstrm) is not needed since Kondooit ingests in the background.

#### XMLTV parser (`infrastructure/iptv/xmltv_parser.py`)

Streaming XML parser using `lxml.etree.iterparse`:
- DOCTYPE entity prepend for HTML named entities (`&eacute;` etc.)
- Two-pass: channels first, then programmes
- Per-channel programme parsing (only for channels matched to EPG entries)
- Batch bulk operations (500 at a time)
- Atomic per-channel programme swap (delete old + insert new)

#### Scheduler (`infrastructure/iptv/scheduler.py`)

APScheduler `BackgroundScheduler`:
- `coalesce=True`, `max_instances=1` per job
- Interval triggers (hours) for provider and EPG refresh
- In-process lock to prevent concurrent refresh of same source
- Jobs persist in SQLite job store (APScheduler default)

Refresh flow:
1. Scheduler triggers refresh job at configured interval
2. Acquire lock for this provider/EPG source
3. Fetch → parse → persist → cleanup stale → release lock
4. If lock is held, skip this run

### 5.6 API Layer

#### Live TV endpoints (`api/live_tv.py`)

```
GET  /api/live-tv/channels              — list channels (with effective overrides)
GET  /api/live-tv/channels/{id}         — channel detail
PATCH /api/live-tv/channels/{id}        — update override (name, number, group, EPG, UA)
POST  /api/live-tv/channels/{id}/match  — trigger single-channel EPG match
GET  /api/live-tv/channels/{id}/epg     — current program + upcoming (time-range query)
GET  /api/live-tv/groups                — list channel groups
```

#### IPTV admin endpoints (`api/iptv_admin.py`)

```
GET  /api/iptv/providers                — list IPTV providers
POST /api/iptv/providers                — add M3U or XC provider
PATCH /api/iptv/providers/{id}          — update provider (including user_agent)
POST /api/iptv/providers/{id}/refresh   — trigger manual refresh
POST /api/iptv/providers/{id}/test      — test connection
DELETE /api/iptv/providers/{id}         — remove provider

GET  /api/iptv/epg-sources              — list EPG sources
POST /api/iptv/epg-sources              — add XMLTV source (URL or file path)
PATCH /api/iptv/epg-sources/{id}        — update (refresh interval, priority)
POST /api/iptv/epg-sources/{id}/refresh — trigger manual EPG refresh
DELETE /api/iptv/epg-sources/{id}       — remove EPG source

POST /api/iptv/epg/match                — trigger bulk EPG matching
```

### 5.7 Database Schema (New Tables)

Following the project's dual-migration requirement (CLAUDE.md §20):

**New tables:**

1. `iptv_providers` — IPTV provider instances (M3U or XC credentials, config, refresh interval, user agent)
2. `channel_groups` — channel group names (provider-created or user-created)
3. `channels` — live TV channels (provider-supplied data)
4. `channel_overrides` — user customizations (1:1 to channels, all nullable)
5. `epg_sources` — XMLTV EPG source configurations
6. `epg_channels` — EPG channel entries (from XMLTV)
7. `programs` — EPG programme/schedule entries
8. `iptv_vod_entries` — IPTV VOD content identity (deduped across providers)
9. `iptv_vod_streams` — per-provider stream URLs for VOD entries

Each table needs the standard: creation migration (via `apply_migration`), update to initial schema migration (0001), and Alembic version.

**RLS policies:** All tables use `TO authenticated` since this is a single-admin household server. Standard 4 policies per table (SELECT, INSERT, UPDATE, DELETE).

### 5.8 Integration with Existing Source Discovery

IPTV VOD content integrates with the existing source discovery pipeline (v0.0.2):

When a user requests sources for a movie or episode:
1. Query debrid providers (TorBox) — existing
2. Query Usenet providers (Easynews) — existing
3. Query hash aggregators (modules) — existing
4. **Query IPTV VOD library** — NEW: search `iptv_vod_entries` by cleaned_title + year (movie) or cleaned_title + season + episode (series). Return matches as `SourceResult` with `source_type = IPTV_STREAM`.

IPTV VOD sources are marked as "In Library" (instant availability, no debrid/cache check needed). They are direct stream URLs.

The VOD library search uses the same title normalization as EPG matching (lowercase, remove extraneous words, etc.) for consistent fuzzy matching.

### 5.9 Web UI

New pages:
- **Live TV page** — channel grid with logos, channel numbers, current program. D-pad/remote friendly for TV.
- **Channel detail** — current program, upcoming programs, stream info, edit override.
- **Channel management** — admin view for editing channel numbers, assigning EPG manually, enabling/disabling channels, setting user agents.
- **IPTV provider settings** — add/edit M3U and XC providers, configure refresh intervals, set user agents, trigger manual refresh.
- **EPG source settings** — add/edit XMLTV sources, configure refresh intervals, trigger EPG matching.

Navigation: "Live TV" appears alongside "Movies" and "TV Shows" in the main navigation, per ADR-0001.

### 5.10 What Is NOT in Scope

- Stream proxy / transcoding for live TV — direct delivery only (client fetches stream URL directly)
- DVR / recording
- Connection counting / max streams enforcement
- Multi-stream failover per channel
- Schedules Direct EPG
- ML-based EPG matching
- .strm file generation
- import_selected mode (follow rules, manual import)
- HDHR / XC output protocols
- Custom stream profiles (ffmpeg/vlc commands)
- TMDB enrichment for VOD entries (Kondooit already has TMDB; VOD entries match to existing content via title)

---

## 6. Recommended Implementation Sequence

The implementation should be ordered to build each layer on the previous one:

**Phase 1: Provider Ingestion**
1. Domain entities (Channel, ChannelGroup, EPGSource, EPGChannel, Program)
2. Infrastructure: M3U parser + Xtream client
3. Infrastructure: SQLAlchemy models + repositories
4. Application: ingestion service (fetch → parse → persist → cleanup stale)
5. API: provider CRUD, manual refresh trigger
6. Database migrations
7. Scheduler setup (APScheduler, interval jobs)

**Phase 2: EPG**
1. Infrastructure: XMLTV parser
2. Application: EPG ingestion service
3. Application: EPG matching service (exact + fuzzy)
4. API: EPG source CRUD, matching trigger, program queries
5. Web UI: EPG source settings, channel EPG assignment

**Phase 3: Channel Management**
1. Application: channel override resolution (effective values)
2. API: channel listing, channel update (override), channel enable/disable
3. Web UI: Live TV page, channel grid, channel detail, channel management

**Phase 4: VOD Ingestion**
1. Domain entities (VODEntry, VODStream)
2. Infrastructure: extend M3U parser + Xtream client for VOD content
3. Application: VOD ingestion service (classify, dedup, persist)
4. Application: integrate VOD search into source discovery pipeline
5. API: VOD browsing endpoints (optional — VOD appears as sources on existing detail pages)

**Phase 5: User Agent Support**
1. Domain: add `user_agent` fields to provider and channel/override models
2. Infrastructure: use configured UA for all HTTP requests (M3U download, XC API, XMLTV fetch)
3. API: UA configuration in provider/channel settings
4. Web UI: UA fields in provider and channel settings

---

## 7. Open Questions

1. **Should IPTV providers be a new provider type or extend the existing SourceProvider abstraction?** The v0.0.2 roadmap defines SourceProvider for debrid/usenet. IPTV is fundamentally different (channels + VOD vs. search-for-content). Recommendation: IPTV is a separate capability, not another SourceProvider. The VOD search integration is a thin adapter that queries the VOD library and returns SourceResult entities, but the IPTV provider itself is its own abstraction (IPTVProviderPort). This needs an ADR.

2. **Should EPG matching use rapidfuzz or a simpler string similarity?** Dispatcharr uses rapidfuzz. It's a lightweight Python package with no heavy dependencies. Recommendation: use rapidfuzz. This needs validation that it installs cleanly in the Docker image.

3. **How should the scheduler be initialized and managed?** APScheduler runs as a BackgroundScheduler in the server process. It needs to start on server startup and shut down cleanly. This may need a small integration with the existing Litestar startup/shutdown lifecycle.

4. **Should VOD content from IPTV providers appear in the main discovery catalog or only as source results?** The roadmap says "IPTV channels and unmatched VOD content are browsable through a dedicated IPTV section." Matched VOD appears as sources on existing detail pages. Unmatched VOD needs its own browseable section. How does this interact with the provider-driven discovery model (ADR-0009)? This needs an ADR or clarification.

5. **Should channel numbers be auto-assigned or manually set on first import?** Recommendation: auto-assign using `next_available` numbering on first import, then let the user reorder via overrides. This matches Dispatcharr's approach.

---

## 8. ADRs Needed

Before implementation begins, the following ADRs should be created:

1. **IPTV provider architecture** — IPTV as a distinct provider capability (not another SourceProvider). Defines the IPTVProviderPort interface, M3U/XC as implementations, and the relationship to the source discovery pipeline.

2. **EPG and channel domain model** — Channel, ChannelGroup, ChannelOverride, EPGSource, EPGChannel, Program as domain entities. ChannelOverride pattern for user customization preservation.

3. **IPTV VOD as source candidates** — How VOD content from IPTV providers integrates with the source discovery pipeline. VODEntry/VODStream separation, content-hash dedup, and the adapter that makes VOD matches appear as SourceResult entities.

These ADRs would be created as Proposed, then moved to Accepted when the roadmap authorizes implementation.

---

## 9. Key Takeaways

- **From Dispatcharr:** ChannelOverride pattern, EPG 3-tier matching (simplified to 2-tier), stream hash-based identity, per-provider user agent, stale cleanup. Reject: Celery/Redis scheduler, stream proxy, DVR, ML matching, multi-stream failover.

- **From Vodstrm:** Content classification cascade (live → series → tv_vod → movie → unsorted), content-addressable identity for VOD dedup, `force_vod` flag, APScheduler for refresh, generate_all mode. Reject: .strm files, import_selected mode, follow rules, download queue, TMDB enrichment (already exists in Kondooit).

- **Architectural alignment:** All new domain entities are pure Python dataclasses. All parsing is infrastructure. All scheduling is infrastructure. The provider abstraction (IPTVProviderPort) follows the existing pattern (MetadataProvider, SourceProvider). VOD integration with source discovery is a thin adapter — the VOD library is queried and results are normalized to SourceResult.

- **Scope discipline:** This plan implements only the six features the user specified plus VOD ingestion. No stream proxy, no DVR, no connection counting, no ML matching, no .strm files. The architecture has clean extension points for future capabilities without implementing them.
