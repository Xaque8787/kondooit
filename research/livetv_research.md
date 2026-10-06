# Live TV Research — Dispatcharr & Vodstrm Analysis and Implementation Plan

**Date:** 2026-10-05
**Status:** Research (pre-implementation)
**Sources analyzed:** [Dispatcharr](https://github.com/dispatcharr/dispatcharr.git), [Vodstrm](https://github.com/Xaque8787/vodstrm.git)
**Source code:** Analyzed from cloned repositories (since removed). GitHub links: [Dispatcharr](https://github.com/dispatcharr/dispatcharr.git), [Vodstrm](https://github.com/Xaque8787/vodstrm.git)

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
- Kondooit should implement: system default UA, per-provider UA override. Per-channel UA is over-engineering for initial scope — per-provider covers the common case. (Later superseded by user direction: the plan includes household, profile, provider, and channel levels — see §5.11.5.)
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
- Dispatcharr's shared multi-client stream proxy is out of scope. ADR-0014 establishes direct delivery as the default, with proxy as fallback. For live TV, Kondooit applies that chain per viewer (direct, then FFmpeg remux/convert through the server when a device cannot play the stream) — see §5.11.3.
- The multi-client shared-buffer proxy is a future optimization.
- Connection counting (max_streams enforcement) is adopted in simplified form: a user-set per-provider connection limit enforced before playback, with no preemption and no stream sharing — see §5.11.4.

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
| Connection counting / preemption | Implementation choice | Partial — user-set limit enforced before playback (§5.11.4); no preemption |
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
| .strm file generation | Ecosystem workaround | No — Kondooit stores stream URLs in the database directly; it does not need .strm files since it IS the media server |
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
    quality_label: str | None   # detected quality (e.g. "4K", "1080p", "SD")
    batch_id: str           # current refresh batch — used for stale cleanup
    last_seen: datetime
```

**Key decisions:**
- VODEntry/VODStream separation mirrors Kondooit's content/source distinction (ADR-0002). VODEntry = what the content is. VODStream = where it comes from.
- `content_hash` is the cross-provider dedup key, based on Vodstrm's proven approach.
- VOD content from IPTV providers is exclusively source candidates — they are NOT browseable as standalone catalog entries. All content discovery in Kondooit goes through a single unified search pipeline. When a user views a movie or episode detail page and requests sources, the system queries all configured providers (debrid, Usenet, hash aggregators, AND the IPTV VOD library) and returns results through one unified source list.
- `unsorted` entries (titles that cannot be parsed into movie/series/tv_vod) are a catch-all dump for unparseable content. They are NOT browseable and NOT included in source search results. They are retained in the database for diagnostic purposes only.
- Matching IPTV VOD to metadata-provider content is title-based fuzzy matching (same approach as channel-to-EPG matching, simpler).
- No .strm files are created. Kondooit stores stream URLs directly in the database (on VODStream) and serves them through its own API. The .strm file format is an ecosystem artifact for external media servers (Jellyfin/Plex/Stremio) — Kondooit IS the media server and has no need for this intermediary.

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

Orchestrates: parse provider → apply title filters → classify entries → compute content hashes → dedup across providers → detect quality → persist with batch_id → cleanup stale streams → cleanup orphaned entries.

Classification cascade (from Vodstrm, proven):
1. `duration == "-1"` and not `force_vod` → live (skip, not VOD)
2. SxxExx pattern → series
3. Air-date pattern → tv_vod
4. 4-digit year → movie
5. Fallback → unsorted (retained as diagnostic dump only — NOT browseable, NOT included in source search results)

Quality detection runs after classification. It scans the raw title for quality keywords (4K, 2160p, 1080p, 720p, 480p, HEVC, HDR, etc.) and stores the result as `quality_label` on VODStream. Provider-level `quality_terms` can refine this — see §5.10.3.

Title filtering runs before classification. It applies the provider's configured filter rules and the global default filters to clean up poorly parsed titles — see §5.10.4.

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
GET  /api/live-tv/guide                 — guide grid data for a time window (§5.11.1)
POST /api/live-tv/channels/{id}/play    — create live stream handle; also used to report failures and escalate (§5.11.2–5.11.3)
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

1. `iptv_providers` — IPTV provider instances (M3U or XC credentials, config, refresh interval, user agent, `max_connections` nullable = no limit)
2. `channel_groups` — channel group names (provider-created or user-created)
3. `channels` — live TV channels (provider-supplied data, including cached stream probe info: `probe_container`, `probe_video_codec`, `probe_audio_codec`, `probed_at`)
4. `channel_overrides` — user customizations (1:1 to channels, all nullable)
5. `epg_sources` — XMLTV EPG source configurations
6. `epg_channels` — EPG channel entries (from XMLTV)
7. `programs` — EPG programme/schedule entries
8. `iptv_vod_entries` — IPTV VOD content identity (deduped across providers)
9. `iptv_vod_streams` — per-provider stream URLs for VOD entries (includes `quality_label`, `batch_id` for stale cleanup)
10. `iptv_filters` — per-provider filter rules (exclude and title replacement rules)

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

**Single unified search pipeline:** All content discovery in Kondooit goes through one search mechanism. There is no dedicated IPTV browse section for VOD content. IPTV VOD is exclusively a source provider — its results appear alongside debrid, Usenet, and hash aggregator results when a user searches for sources on a movie or episode detail page. This is a deliberate design choice: one search pipeline, multiple provider types contributing results.

### 5.9 Web UI

New pages:
- **Live TV page** — guide view (EPG grid, default) and compact channel grid view. D-pad/remote friendly for TV. See §5.11.1.
- **Live player** — live mode of the existing player: info overlay, channel up/down, mini-guide, automatic compatibility fallback. See §5.11.2–5.11.3.
- **Channel detail** — current program, upcoming programs, stream info, edit override.
- **Channel management** — admin view for editing channel numbers, assigning EPG manually, enabling/disabling channels, setting user agents.
- **IPTV provider settings** — add/edit M3U and XC providers, configure refresh intervals, set user agents, trigger manual refresh.
- **EPG source settings** — add/edit XMLTV sources, configure refresh intervals, trigger EPG matching.

Navigation: "Live TV" appears alongside "Movies" and "TV Shows" in the main navigation, per ADR-0001. There is NO dedicated IPTV VOD browse section — IPTV VOD content appears exclusively as source results on existing movie and episode detail pages through the unified source search pipeline.

### 5.10 VOD Lifecycle Management

This section details four features that govern how VOD content is kept clean and correctly prioritized in the database. These are inspired by Vodstrm's proven approaches but simplified for Kondooit's architecture. All four operate during the VOD ingestion refresh cycle (§5.4 VOD ingestion service).

#### 5.10.1 Stale Content Cleanup (Batch-Based Reconciliation)

**Problem:** When a provider drops content from their playlist, the stale entries must be removed from the database. Without this, the VOD library accumulates dead links that produce errors when a user tries to play them.

**Approach (from Vodstrm):** Each provider refresh generates a unique `batch_id`. All streams ingested during that refresh are tagged with this batch_id. After the refresh completes, any streams from that provider with an older batch_id are deleted — they were not seen in this refresh, so the provider no longer offers them.

**Kondooit's implementation:**

1. At the start of a provider refresh, generate a new `batch_id` (UUID string)
2. Parse all VOD content from the provider
3. For each VODStream, upsert with the current `batch_id` and update `last_seen`
4. After all content is persisted, delete all VODStreams from this provider where `batch_id != current_batch_id`
5. After stale streams are deleted, check for orphaned VODEntries — any VODEntry that has zero remaining VODStreams is deleted (no provider offers this content anymore)
6. `unsorted` entries follow the same cleanup logic — they are also batch-tagged and cleaned up

**What about content temporarily unavailable?** A provider might have a transient outage that causes content to disappear for one refresh cycle, then reappear. This is an acceptable trade-off — the content will be re-ingested on the next refresh when it reappears. Adding grace periods would add complexity for marginal benefit. The refresh interval (typically 1-6 hours) means the window of data loss is short.

**Provider deletion:** When a provider is entirely removed (DELETE /api/iptv/providers/{id}), all VODStreams for that provider are deleted, followed by orphaned VODEntry cleanup. Same for channel data.

**Provider deactivation:** When a provider is deactivated (is_active = false), its VODStreams are NOT deleted — they remain in the database but are excluded from source search results. If the provider is reactivated, the next refresh will reconcile via batch_id. This allows temporary deactivation without data loss.

#### 5.10.2 Provider Priority for Duplicate Entries

**Problem:** Multiple IPTV providers may offer the same movie or episode. Kondooit needs to present these intelligently — the user should see the best provider's result first, but all options should be available.

**Approach:** Unlike Vodstrm (which selects one "winner" per entry for .strm file generation), Kondooit keeps ALL streams from ALL providers in the database. This is because Kondooit's unified source search pipeline can present multiple source options to the user — there is no need to pick a single winner.

**Kondooit's implementation:**

1. Each IPTV provider has a `priority` field (integer, lower = higher priority). This follows ADR-0011 (Provider Priority and Fallback).
2. When the source search pipeline queries the VOD library, it returns all matching VODStreams for the requested content, sorted by:
   a. Provider priority (lower number first)
   b. Quality label (4K > 1080p > 720p > SD)
   c. Most recently seen (fresher is better)
3. All streams are returned as separate SourceResult entries — the user sees all available IPTV sources and can choose any one
4. The first result in the sorted list is effectively the "primary" — it appears at the top of the IPTV source group

**No winner selection is needed.** Vodstrm needs winner selection because it writes one .strm file per entry. Kondooit stores all streams in the database and presents them all through the API. This is simpler and more flexible — the user can choose a non-primary source if they prefer a different provider or quality.

**Default priority:** New providers are assigned priority 100 by default. The admin can adjust priorities in the IPTV provider settings page.

#### 5.10.3 Quality Terms

**Problem:** IPTV providers often include quality indicators in stream titles (e.g., "Movie Title 4K HDR", "Series Name S01E01 1080p HEVC"). These need to be detected and stored so the source search pipeline can rank and filter by quality.

**Approach (from Vodstrm):** Vodstrm stores `quality_terms` as a JSON field on each provider. This allows per-provider quality keyword configuration.

**Kondooit's implementation:**

Quality detection is a two-level system:

**Level 1 — Global defaults (auto-applied):**

A built-in quality detection map that runs on all providers without configuration. These are reasonable defaults that cover the vast majority of IPTV stream titles:

| Pattern (regex, case-insensitive) | Quality Label |
|---|---|
| `\b(4k|2160p|uhd)\b` | `4K` |
| `\b(1080p|fhd|full hd)\b` | `1080p` |
| `\b(720p|hd)\b` | `720p` |
| `\b(480p|576p|sd)\b` | `SD` |
| `\b(hevc|h265|x265)\b` | adds `HEVC` codec tag |
| `\b(hdr|hdr10|dolby vision|dv)\b` | adds `HDR` tag |

The highest matching quality wins (4K > 1080p > 720p > SD). Codec and HDR tags are appended. If no pattern matches, `quality_label` is `None` (unknown quality).

**Level 2 — Provider-level quality terms (optional override):**

Each IPTV provider can optionally specify `quality_terms` — a list of custom regex patterns and their corresponding labels. These are merged with the global defaults (provider terms take precedence on conflict). This handles providers that use non-standard quality naming.

**Why keep it simple:** Vodstrm's quality_terms are primarily used to decide which stream to write to a .strm file. Since Kondooit keeps all streams and presents them ranked, quality terms are used for ranking, not for winner selection. The global defaults cover the common cases. Provider-level override is available for edge cases but is not required for normal operation.

**UI:** The IPTV provider settings page shows the global defaults and allows the admin to add provider-specific quality patterns. This is an advanced setting — most users will never need to touch it.

#### 5.10.4 Title Filter Mechanism

**Problem:** IPTV providers often have messy titles with extra metadata, prefixes, suffixes, or junk that interferes with classification and matching. Examples: "[US] Movie Title 4K", "Movie Title (2022) - Premium", "VOD: Series Name S01E01 HD". Without filtering, the classification cascade misfires and the content_hash produces poor matches.

**Approach (from Vodstrm):** Vodstrm has a filter engine with four operations: replace, remove, exclude, include_only. This is powerful but complex. Kondooit simplifies this while keeping the essential capabilities.

**Kondooit's implementation:**

Three filter types, applied in order during ingestion (before classification):

**1. Title cleanup rules (replace/remove) — auto-applied defaults:**

A built-in set of regex replacements that clean up common title junk. These run on every provider without configuration:

| Rule | Pattern | Replacement | Purpose |
|---|---|---|---|
| Remove bracketed prefixes | `^\[.+?\]\s*` | `` | Removes `[US]`, `[VOD]`, `[Premium]` etc. |
| Remove VOD: prefix | `^VOD:\s*` | `` | Common IPTV prefix |
| Remove trailing quality | `\s+(4K|2160p|1080p|720p|480p|HEVC|HDR|UHD)(?:\s|$)+` | `` | Quality is detected separately |
| Remove trailing codec tags | `\s+(H264|H265|X264|X265|x264|x265)(?:\s|$)+` | `` | Codec is detected separately |
| Collapse multiple spaces | `\s{2,}` | ` ` | Clean formatting |
| Strip trailing dashes | `\s*[-–—]\s*# Live TV Research — Dispatcharr & Vodstrm Analysis and Implementation Plan

#### 5.10.5 Summary of VOD Lifecycle

``Provider Refresh Triggered``
         ↓
``Generate batch_id``
         ↓
``Fetch content from provider (M3U or XC)``
         ↓
``Apply title cleanup defaults``
         ↓
``Apply provider-level title replacement rules``
         ↓
``Apply provider-level exclude filters``
         ↓
``Classify entries (live → series → tv_vod → movie → unsorted)``
         ↓
``Detect quality from raw title``
         ↓
``Compute content_hash for each entry``
         ↓
``Upsert VODEntry (by content_hash) and VODStream (by entry + provider, tagged with batch_id)``
         ↓
``Delete stale VODStreams (old batch_id for this provider)``
         ↓
``Delete orphaned VODEntries (zero remaining streams)``
         ↓
``Refresh complete``

When source search queries the VOD library:
``Query iptv_vod_entries by cleaned_title + year/season/episode``
         ↓
``Get all matching VODStreams (from all active providers)``
         ↓
``Sort by provider priority → quality → last_seen``
         ↓
``Return as SourceResult list (all streams, best first)``

### 5.11 Live TV Guide and Channel Playback

This section defines the guide view (EPG grid), the flow from selecting a channel to watching it, and the compatibility fallback that ensures a channel which cannot play natively on a device is repackaged or converted by the server. It applies the existing delivery decisions (ADR-0014 fallback chain, ADR-0015 stream handles, ADR-0016 HLS remux) to live channels; it does not replace them.

#### 5.11.1 Guide View (EPG Grid)

The guide is the primary Live TV screen. The channel grid from §5.9 remains as an alternate compact view ("Channels"); the guide is the default view ("Guide").

**Layout:**
- Rows are channels, ordered by effective channel number (override first, then provider number). Each row header shows channel number, logo, and name.
- Columns are time, in 30-minute slots. A header row shows slot times; a vertical "now" line marks the current time and moves as time passes.
- Programme blocks are sized by duration and show title and time. The currently airing programme in each row is visually highlighted; elapsed portion shown as a subtle progress fill.
- Channels with no matched EPG show a single full-width "No guide information" block. They remain fully playable.

**Navigation:**
- Default window on open: 30 minutes before now to 3 hours after now, scrolled so "now" is near the left edge.
- Horizontal scroll moves through time; further data loads in 3-hour chunks as the user scrolls, up to the furthest programme available in the EPG (typically 1–7 days, provider-dependent). Past programmes are shown back to the start of the current day only (no catch-up in scope).
- Vertical scroll is virtualized (only visible rows rendered) because providers commonly supply hundreds to thousands of channels.
- "Jump to now" control returns the window to the current time.
- Group filter (channel groups from §5.3) narrows the rows; "All channels" is default. Disabled channels never appear.
- D-pad/remote: arrow keys move focus between programme blocks (left/right through time, up/down through channels, keeping the focused time position), Enter activates, Back closes overlays. Focus is always visible.

**Selecting things in the guide:**
- **Channel row header** → starts playback of that channel immediately.
- **Currently airing programme** → starts playback of that channel immediately.
- **Future or past programme** → opens a programme detail drawer (title, time range, description, episode info, channel). The drawer offers "Watch channel now" (plays the channel live). No reminders or recording (out of scope).

**Guide API:** one bulk request returns everything needed for a time window, avoiding one request per channel.

```
GET /api/live-tv/guide?start=<iso>&end=<iso>&group_id=<optional>&offset=&limit=
→ {
    window: { start, end },
    channels: [
      { id, number, name, logo_url, group_id, has_epg,
        programs: [ { id, title, start, end, description, episode_info } ] }
    ],
    total_channels
  }
```

- Window capped at 12 hours per request; programmes overlapping the window edges are included.
- Channel pagination (`offset`/`limit`, default 100) supports virtualized vertical scrolling.
- Uses effective channel values (overrides applied) — same resolution as the channel list endpoint.

#### 5.11.2 Channel Playback Flow

```
User selects channel (guide, channel grid, or channel detail)
         ↓
Client: POST /api/live-tv/channels/{id}/play
        { client_capabilities, previous_stream_id?, failure? }
         ↓
Server: resolve effective channel (override → stream URL, user agent)
         ↓
Server: choose delivery tier (§5.11.3) using cached probe info,
        client capabilities, admin "force proxy", and any reported failure
         ↓
Server: create stream handle (ADR-0015) marked live
         ↓
Client: mode "direct" → play URL     mode "proxy" → play /hls/{stream_id}/master.m3u8
         ↓
Live player opens
```

**Live player behavior** (live mode of the existing player page, not a separate player):
- No seek bar, no resume position, no watch-progress reporting — live content has no resume point.
- Overlay (shown on open, on input, auto-hides after a few seconds): channel number/logo/name, current programme with progress, next programme.
- Channel up/down (keys, remote buttons, on-screen controls) switches to the adjacent channel by number within the current group filter. Switching ends the previous stream session before starting the next.
- Mini-guide overlay: a compact list of channels with "now" programmes for quick switching without leaving the player.
- While the server is preparing a compatible stream, the player shows "Preparing stream for this device…" rather than a blank screen.

**Stream session lifecycle for live:** a live handle never "finishes". Direct-mode live sessions are released when the client stops or switches channel. Proxy-mode sessions are released on stop or when the client stops requesting playlist/segments for the staleness timeout (ADR-0016's existing cleanup), which kills the FFmpeg process and deletes temporary segments.

#### 5.11.3 Format Compatibility and Fallback Chain

**Why this is needed (confirmed from research):** IPTV live streams are most commonly MPEG-TS over HTTP, sometimes provider-hosted HLS. Codecs are usually H.264 + AAC, but MPEG-2 video, HEVC, and AC-3 / E-AC-3 / MP2 audio are common on some providers. Browsers cannot play MPEG-TS directly, cannot decode AC-3/MP2 audio in most cases, and often cannot decode HEVC or MPEG-2. Native players (Android/Fire TV, ADR-0018) handle far more but still fail on some combinations.

**Additional browser constraints (assumption, to verify during implementation):**
- Most IPTV providers do not send CORS headers, so a browser cannot fetch their streams or HLS playlists directly from another origin.
- Many providers serve plain `http://`; a Kondooit web UI served over `https://` is blocked from loading them (mixed content).
- Browsers cannot set a custom User-Agent header, so channels that require one (§5.5 per-provider/per-channel UA) cannot be fetched directly by a browser.

In practice the web client will use the proxy path for nearly all IPTV live channels. Native clients will use direct delivery for most channels.

**Delivery tiers** (ADR-0014 order, with one added low-cost step):

| Tier | What the server does | Server CPU | When used |
|---|---|---|---|
| 1. Direct | Nothing; client plays the provider URL | None | Client can play container + codecs natively, and can reach the URL (CORS/https/UA not a problem) |
| 2. Remux | FFmpeg copies audio and video into HLS (fMP4 segments) — existing ADR-0016 path | Near zero | Container or reachability is the problem; codecs are fine |
| 3. Audio convert | FFmpeg copies video, converts audio to AAC | Low | Video codec is fine, audio codec (AC-3, E-AC-3, MP2) is not |
| 4. Full transcode | FFmpeg converts video to H.264 and audio to AAC | High (≈1+ CPU core per viewer) | Video codec (MPEG-2, HEVC on unsupported clients) is not playable |

**Confirmed fact (server HLS endpoint source):** the existing on-demand HLS playback path already performs tiers 2–4 — it probes the source, then remuxes, remuxes video while converting audio to AAC, or fully transcodes video to H.264, depending on what the browser supports. Live TV reuses this path and its codec-selection logic; the new work is live-specific input handling (UA, reconnect, no end of stream), failure-driven escalation, and choosing direct delivery when a device can play the stream itself.

Tier 3 is a specialisation of ADR-0014's "transcode" tier (re-encoding only the incompatible stream), not a new delivery mode. In ADR-0015 terms tiers 2–4 are all `mode: "proxy"` with `processing` of `remux` or `transcode` and a `transcode_profile` describing which streams are converted.

**Choosing the starting tier (before playback):**
1. If the admin "force proxy" setting is on, start at tier 2 or higher.
2. If a User-Agent is configured for the channel (§5.11.5) and the client cannot send custom headers (all browsers), start at tier 2 or higher. Native clients receive the User-Agent in the handle's `headers` field and can stay direct.
3. Use the channel's cached **probe info** (container, video codec, audio codec) and the client's reported capabilities to select the lowest tier that should work.
4. If probe info is missing, probe the stream with FFmpeg's probe tool (short timeout, ~5 seconds, using the channel's UA) and cache the result on the channel. If probing fails or times out, start at tier 2 (ADR-0014's safe default for unknown formats).

Probe info is cached per channel and refreshed when older than 24 hours, when the channel's stream URL changes on provider refresh, or after a format failure on that channel.

**Escalating when a stream fails to play (after playback starts):**

Failures are classified by the client into two kinds, using the player's own error reporting (browser media errors / hls.js error types; native player decoder vs. network errors):

- **Format failure** — decoder or "source not supported" errors, or a **stall watchdog**: no new video frames within 15 seconds of starting. → Client calls the play endpoint again with `previous_stream_id` and `failure: "format"`. Server escalates to the next tier above the one that failed.
- **Network failure** — connection dropped, provider error, timeout. → Client retries the **same** tier once (live streams drop occasionally). A second consecutive network failure is shown to the user; network failures do not escalate tiers, because remuxing or converting cannot fix an unreachable provider.

The server can also escalate on its own: if FFmpeg exits with a codec/container error during remux (tier 2), the server restarts that session at tier 3 or 4 without a client round trip.

Escalation is automatic and requires no user action. Each tier is attempted at most once per playback attempt. If tier 4 fails, the player shows a clear error ("This channel couldn't be played on this device") with "Try again".

**Remembering what works:** the server remembers the tier that succeeded per channel and client type (web, Android, etc.), so the next time that channel is played on that kind of device it starts at the working tier instead of repeating failures. This memory is held in memory, and is cleared when probe info is refreshed or the channel's stream URL changes.

**Manual override (progressive disclosure):** the player's settings menu offers "Playback mode: Automatic (default) / Original / Compatible / Converted", mapping to automatic selection, tier 1, tier 2, and tier 4. A manual choice applies to the current playback only.

**Live-specific FFmpeg behavior** (infrastructure detail, recorded for implementation):
- Pass the channel's effective User-Agent to FFmpeg for upstream requests.
- Enable FFmpeg's reconnect options for HTTP inputs so short upstream drops do not end the session.
- Sliding-window HLS playlist with old segments deleted, so long viewing sessions do not grow disk usage.
- Full transcode targets H.264 at a fast encoder preset with AAC stereo audio, resolution capped at the source resolution. Hardware-accelerated encoding is a future enhancement.
- One FFmpeg process and one upstream connection per viewer. Two viewers of the same channel use two provider connections. Sharing one upstream between viewers is deliberately not done (see §5.11.4).

**Probe info storage:** add nullable columns to `channels`: `probe_container`, `probe_video_codec`, `probe_audio_codec`, `probed_at`. Provider-supplied data on the channel, not an override; refreshed by the server, never edited by users.

**Relationship to the roadmap:** the roadmap's v0.0.1/v0.0.2 "No transcoding" exclusions and its "Transcoding" future-milestone entry predate the implemented HLS playback path, which already remuxes and transcodes under ADR-0014/ADR-0016. The roadmap is out of date on this point and should be corrected separately; this plan introduces no new transcoding capability, only applies the existing one to live channels.

#### 5.11.4 Provider Connection Limits

**Problem:** IPTV subscriptions allow a fixed number of simultaneous streams. When the limit is exceeded the provider typically fails the new stream, kills an existing one, or flags the account. Kondooit should prevent this rather than rely on the provider.

**Setting:** each IPTV provider has an optional, user-set **connection limit** (`max_connections`; empty = no limit). Set in IPTV provider settings. Xtream Codes providers report `max_connections` in their account info; when available it is shown as a suggested value, but the user's setting is what is enforced.

**What counts as a connection:** every active stream session whose upstream is that provider — live channels and IPTV VOD movies/episodes alike, in every delivery tier (direct, remux, converted), on every device and profile. Direct-mode sessions count even though bytes do not pass through the server, because the provider still sees a connection from the household.

**Enforcement (before playback):**
1. The play request identifies the channel's (or VOD stream's) provider.
2. If the requesting device is switching channel or retrying, its previous session is released first, so switching at the limit works.
3. If active sessions for that provider are below the limit, the session is created.
4. Otherwise playback is refused with a clear message: "All 2 connections for <provider> are in use", listing what is using them (profile, device, channel or title). No stream is started, so the provider never sees an over-limit attempt.

There is no automatic preemption. The message offers "Stop a stream" so the user can end one of the listed sessions and then play.

**IPTV VOD in source search:** sources from a provider at its limit are still listed but marked "Provider busy", and selecting one shows the same message. Other providers' sources for the same title remain available, so provider priority (§5.10.2) naturally falls through to a free provider.

**Accurate session tracking:**
- Proxy-mode sessions end when the device stops requesting the stream (existing staleness cleanup), on explicit stop, or on channel switch.
- Direct-mode sessions are invisible to the server once started, so the player sends a heartbeat every 30 seconds; a session with no heartbeat for 90 seconds is released. Players also send an explicit stop on close or channel change.
- Session counts are in memory (consistent with ADR-0015's ephemeral handle store). After a server restart all counts reset to zero; this is acceptable because devices re-request playback and are counted again.

**Explicitly rejected:** sharing one provider connection among several viewers of the same channel (restreaming or reusing an existing transcode) to exceed the subscription's limit. Each viewer always uses their own provider connection and counts against the limit.

#### 5.11.5 User-Agent Settings

**What it is:** the User-Agent is a short text label every HTTP request carries, identifying the app making the request (e.g. "VLC/3.0.20"). Some IPTV providers only serve streams to requests that identify as an approved player, and some block unknown ones. This is the "device identity" referred to earlier — they are the same thing.

**Levels** (most specific wins):

| Level | Set where | Typical use |
|---|---|---|
| 1. Channel | Channel management (override), or supplied by the provider in the playlist (`#EXTVLCOPT:http-user-agent`) | A single channel that needs a different identity |
| 2. IPTV provider | IPTV provider settings | The provider requires a specific player identity |
| 3. Profile | Profile settings | A household member wants their playback to identify as a specific player |
| 4. Household | IPTV settings (applies to the whole server) | One identity for all IPTV playback |
| 5. Built-in default | — | Used for server-side requests only when nothing above is set |

Precedence rationale: channel and provider settings exist because a specific provider requires them, so they outrank personal preference. A profile setting applies only to channels and providers that have no requirement of their own. This ordering can be revisited if the profile should take priority.

**Scope:** applies to IPTV live channels and IPTV VOD playback, and to server-side IPTV requests (playlist and guide downloads, probing, remux/transcode). Profile-level settings apply only to playback, since background refreshes are not tied to a profile. Not applied to TorBox, Easynews, or scraper sources.

**Presets:** the settings fields offer common presets (VLC, Kodi, TiviMate, a browser identity) plus a custom value.

**How it reaches playback (decision: option (a) from §8):**
- **Proxy delivery (tiers 2–4):** the server sends the effective User-Agent on its upstream requests.
- **Direct delivery to native apps:** the stream handle carries an optional `headers` field (`{"User-Agent": "..."}`) that the app sends when fetching the stream. Requires an ADR superseding ADR-0015.
- **Direct delivery to browsers:** not possible when any User-Agent is configured at levels 1–4, because browsers cannot change it. Such channels use proxy delivery in the browser. Channels with no configured User-Agent can still be delivered directly.

**Storage:** `user_agent` on `iptv_providers`, `channels`, and `channel_overrides` (already planned); add nullable `iptv_user_agent` to `profiles` and a household-level `iptv_user_agent` server setting.

### 5.12 What Is NOT in Scope

- Shared upstream / multi-viewer stream buffering for live TV (one upstream connection per viewer)
- Hardware-accelerated transcoding
- Pause/rewind of live TV (timeshift) and catch-up/archive playback of past programmes
- Programme reminders
- DVR / recording
- Automatic preemption (stopping someone's stream to start another)
- Sharing one provider connection among multiple viewers to exceed a provider's connection limit (deliberately rejected, §5.11.4)
- Multi-stream failover per channel
- Schedules Direct EPG
- ML-based EPG matching
- .strm file generation — Kondooit stores stream URLs in the database directly; it does not need .strm files since it IS the media server
- Dedicated IPTV VOD browse section — all content discovery goes through the single unified source search pipeline; IPTV VOD is exclusively a source provider, not a browseable catalog
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
3. Web UI: channel grid, channel detail, channel management

**Phase 4: VOD Ingestion**
1. Domain entities (VODEntry, VODStream with batch_id and quality_label, FilterRule)
2. Infrastructure: extend M3U parser + Xtream client for VOD content
3. Application: title cleanup defaults + quality detection map
4. Application: VOD ingestion service (filter → classify → detect quality → dedup → persist → stale cleanup → orphan cleanup)
5. Application: integrate VOD search into source discovery pipeline (sort by priority → quality → freshness)
6. API: filter configuration endpoints (per-provider exclude and replacement rules)
7. API: quality terms configuration endpoints (per-provider, optional)
8. UI: filter and quality settings in IPTV provider configuration page

**Phase 5: User Agent Support**
1. Domain: add `user_agent` fields to provider and channel/override models
2. Infrastructure: use configured UA for all HTTP requests (M3U download, XC API, XMLTV fetch)
3. API: UA configuration in provider/channel settings
4. Web UI: UA fields in provider and channel settings, profile settings, and household IPTV settings, with presets
5. Application: effective UA resolution (channel → provider → profile → household → built-in), included in direct-mode handles as `headers` for native clients

**Phase 6: Guide and Live Playback** (requires Phases 1–3 and 5)
1. API: guide endpoint (bulk time-window query, channel pagination)
2. Web UI: guide view with virtualized rows, time scrolling, jump to now, group filter, programme detail drawer, D-pad navigation
3. Infrastructure: stream probing with caching on channel (probe columns migration)
4. Application: live delivery-tier selection (direct → remux → audio convert → full transcode) and per-channel/client-type memory of working tier
5. Infrastructure: extend the existing HLS session manager with live input options (UA, reconnect, sliding window) and the audio-convert / full-transcode profiles
6. API: channel play endpoint with failure reporting and escalation
7. Web UI: live mode of the player (overlay, channel up/down, mini-guide, stall watchdog, failure classification, automatic retry/escalation, manual playback mode menu)
8. Provider connection limits: `max_connections` setting, session counting across live and VOD, heartbeat and stop for direct sessions, "connections in use" message with stop option, "Provider busy" marking in source search
9. Tests: tier selection rules, escalation order, network-vs-format failure handling, session cleanup, connection limit enforcement including channel switching at the limit

---

## 7. Resolved Questions

All five open questions from the initial research have been resolved through review. The resolutions below are authoritative and will guide implementation.

### 7.1 IPTV providers are a separate capability (RESOLVED)

**Decision:** IPTV is a separate capability with its own interface (`IPTVProviderPort`), not an extension of the existing `SourceProvider` abstraction.

**Rationale:** The v0.0.2 roadmap defines `SourceProvider` for debrid/usenet services that search for content by title/IMDB ID. IPTV is fundamentally different — it provides channels and VOD content organized by categories, not search-by-title results. The VOD search integration is a thin adapter that queries the IPTV VOD library and returns `SourceResult` entities when a user searches for sources, but the IPTV provider itself is its own abstraction with its own port.

**Will be recorded as:** ADR (Proposed) — "IPTV provider architecture."

### 7.2 EPG matching uses rapidfuzz (RESOLVED)

**Decision:** Use rapidfuzz for fuzzy name matching between channels and EPG entries.

**Rationale:** rapidfuzz is a lightweight Python package with no heavy dependencies (unlike Dispatcharr's ML tier which requires sentence-transformers and model downloads). It provides good quality string similarity scoring. Needs validation that it installs cleanly in the Docker image during implementation.

### 7.3 Scheduler integrated into Litestar lifecycle (RESOLVED — with follow-up)

**Decision:** The scheduler should be integrated into Litestar's startup/shutdown lifecycle — start on server startup, stop on shutdown.

**Rationale:** APScheduler's `BackgroundScheduler` runs in-process. Litestar has lifecycle hooks for startup and shutdown that are the natural place to initialize and tear down the scheduler. This keeps everything in one process without requiring a separate worker.

**Follow-up:** The user identified a need to explore whether Litestar's lifecycle alone is sufficient, or whether the scheduler should also support cron-style or timezone-aware scheduling (which APScheduler provides independently of Litestar). This should be investigated during implementation to determine if the interval-based approach (simple hour intervals) is sufficient or if cron-style scheduling is needed for more flexible refresh timing. This is an implementation detail, not an architectural question.

### 7.4 IPTV VOD is source-only — no dedicated browse section (RESOLVED)

**Decision:** All content discovery in Kondooit goes through a single unified search pipeline. IPTV VOD content appears exclusively as source results on existing movie and episode detail pages. There is NO dedicated IPTV VOD browse section. Unmatched VOD (content that cannot be parsed into movie/series/tv_vod) is retained as a diagnostic dump only — it is NOT browseable and NOT included in source search results.

**Rationale:** Kondooit's design principle is a single search mechanism with multiple results/sources from any configured providers. Adding a dedicated IPTV browse section would fragment the content discovery experience. The roadmap statement "IPTV channels and unmatched VOD content are browsable through a dedicated IPTV section" is superseded by this decision — IPTV VOD is source-only. Live TV channels remain browseable through the Live TV page (that is the channel guide, not VOD).

**Note:** This decision updates the v0.0.2 roadmap's IPTV description. The roadmap should be updated to reflect that IPTV VOD is source-only and does not have a dedicated browse section. This is a scope refinement, not an architectural change.

**Will be recorded as:** ADR (Proposed) — "IPTV VOD as source candidates only."

### 7.5 Channel numbers: provider-first, next-available fallback (RESOLVED)

**Decision:** Auto-assign channel numbers on first import using the provider's channel number when available (`tvg-chno` from M3U or `num` from XC), falling back to next-available numbering for channels without a provider number. Users can then override channel numbers via ChannelOverride.

**Rationale:** This combines the best of both approaches — provider-supplied numbers are usually meaningful (the provider's intended channel ordering), and next-available fills gaps cleanly. This matches Dispatcharr's `provider` numbering mode with `next_available` fallback.

---

## 8. ADRs Needed

Before implementation begins, the following ADRs should be created as Proposed:

1. **IPTV provider architecture** — IPTV as a distinct provider capability (not another SourceProvider). Defines the `IPTVProviderPort` interface, M3U/XC as implementations, and the relationship to the source discovery pipeline. (Resolves question 7.1.)

2. **EPG and channel domain model** — Channel, ChannelGroup, ChannelOverride, EPGSource, EPGChannel, Program as domain entities. ChannelOverride pattern for user customization preservation. Provider-first channel numbering with next-available fallback. (Resolves question 7.5.)

3. **IPTV VOD as source candidates only** — VOD content from IPTV providers is exclusively a source provider in the unified search pipeline. No dedicated browse section. VODEntry/VODStream separation, content-hash dedup, unsorted as diagnostic dump. Kondooit stores stream URLs in the database — no .strm file generation. (Resolves question 7.4.)

4. **Live TV playback and failure-driven fallback** — applies ADR-0014/0015/0016 to live channels; adds the audio-only conversion step within the transcode tier; client-reported format failures escalate tiers while network failures do not; per-channel/client-type memory of the working tier; stream probing and caching; user-set per-provider connection limits enforced before playback, with no connection sharing. Open item to resolve in this ADR: ADR-0015's direct-mode handle has no field for request headers, so native clients cannot be told a channel's required User-Agent. Decided: (a) add an optional `headers` field to direct-mode handles, via a new ADR superseding ADR-0015 (rejected alternative: always proxy channels that need a custom User-Agent). Also records the household/profile/provider/channel User-Agent levels and precedence (§5.11.5).

These ADRs would be created as Proposed, then moved to Accepted when the roadmap authorizes implementation.

---

## 9. Key Takeaways

- **From Dispatcharr:** ChannelOverride pattern, EPG 3-tier matching (simplified to 2-tier), stream hash-based identity, per-provider user agent, stale cleanup. Reject: Celery/Redis scheduler, stream proxy, DVR, ML matching, multi-stream failover.

- **From Vodstrm:** Content classification cascade (live → series → tv_vod → movie → unsorted), content-addressable identity for VOD dedup, `force_vod` flag, APScheduler for refresh, generate_all mode. Reject: .strm files (Kondooit stores stream URLs in the database directly), import_selected mode, follow rules, download queue, TMDB enrichment (already exists in Kondooit).

- **Architectural alignment:** All new domain entities are pure Python dataclasses. All parsing is infrastructure. All scheduling is infrastructure. The provider abstraction (IPTVProviderPort) follows the existing pattern (MetadataProvider, SourceProvider). VOD integration with source discovery is a thin adapter — the VOD library is queried and results are normalized to SourceResult.

- **VOD lifecycle management:** Stale content is cleaned up via batch-based reconciliation (content dropped by a provider is removed). Duplicate entries across providers are handled by provider priority (all streams kept, ranked by priority → quality → freshness). Quality terms detect quality from stream titles (global defaults auto-applied, per-provider overrides optional). Title filters clean up poorly parsed titles (global cleanup defaults auto-applied, per-provider exclude and replacement rules user-configured).

- **Guide and live playback:** A time-based guide grid is the default Live TV view; selecting a channel or airing programme starts playback. Live channels use the existing direct → remux → transcode chain with an added audio-only conversion step, start at the tier predicted by cached stream probing, and automatically escalate when the device reports a format failure. The working tier is remembered per channel and device type.

- **Scope discipline:** This plan implements only the six features the user specified plus VOD ingestion with full lifecycle management, and the guide/live playback with compatibility fallback. No shared multi-viewer stream buffering, no DVR, no preemption, no ML matching, no .strm files, no dedicated IPTV VOD browse section. The architecture has clean extension points for future capabilities without implementing them.
