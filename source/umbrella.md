# Umbrella Kodi Addon — Repository Analysis

**Repository:** https://github.com/umbrellaplug/umbrellaplug.github.io/tree/master
**Analysis Date:** 2026-08-21
**Analyzed Version:** omega/plugin.video.umbrella (v6.7.85)
**Source of Truth:** Actual repository source code inspection via raw GitHub content
**Status:** Research only — no Kondooit implementation changes

---

## 1. Repository Structure Overview

The repository contains addon builds for multiple Kodi versions (matrix, nexus, omega). The omega build is the latest (Kodi 21). The addon root is `omega/plugin.video.umbrella/`.

### Key Directories

```
omega/plugin.video.umbrella/
├── umbrella.py                    # Entry point — delegates to router
├── service.py                     # Background service
├── addon.xml                      # Kodi addon manifest
├── resources/
│   ├── settings.xml               # Kodi settings UI definitions
│   └── lib/
│       ├── cloud_scrapers/        # Per-debrid cloud file search modules
│       │   ├── __init__.py        # Dynamic module loader with enabledCheck()
│       │   ├── rd_cloud.py        # RealDebrid cloud search
│       │   ├── pm_cloud.py        # Premiumize cloud search
│       │   ├── ad_cloud.py        # AllDebrid cloud search
│       │   ├── tb_cloud.py        # TorBox cloud search
│       │   ├── oc_cloud.py        # OffCloud cloud search
│       │   └── cloud_utils.py     # Shared cloud scraper utilities
│       ├── internal_scrapers/     # Built-in source scrapers
│       │   ├── __init__.py        # Dynamic module loader with enabledCheck()
│       │   ├── easynews.py        # Easynews Usenet search
│       │   ├── plexshare.py       # Plex share search
│       │   ├── gdrive.py          # Google Drive search
│       │   └── filepursuit.py     # FilePursuit search
│       ├── debrid/                # Debrid provider API clients
│       │   ├── realdebrid.py      # Real-Debrid API
│       │   ├── premiumize.py      # Premiumize API
│       │   ├── alldebrid.py       # AllDebrid API
│       │   ├── torbox.py          # TorBox API
│       │   ├── offcloud.py        # OffCloud API
│       │   ├── easynews.py        # Easynews account/UI management
│       │   ├── easydebrid.py      # EasyDebrid (disabled)
│       │   ├── furk.py            # Furk (legacy?)
│       │   └── premium_hosters.py # Hoster domain resolution
│       ├── modules/               # Core logic modules
│       │   ├── sources.py         # *** CENTRAL: Source discovery orchestration ***
│       │   ├── source_utils.py    # Video format/quality parsing constants
│       │   ├── scrape_utils.py    # Release title parsing, quality detection
│       │   ├── debrid.py          # Debrid resolver registry and priority
│       │   ├── player.py          # Kodi player integration
│       │   ├── router.py          # URL routing / action dispatch
│       │   ├── control.py         # Settings, paths, Kodi API wrappers
│       │   ├── trakt.py           # Trakt integration
│       │   ├── tmdb4.py           # TMDb metadata
│       │   ├── tvmaze.py          # TVMaze metadata
│       │   ├── search.py          # Search history
│       │   ├── cleantitle.py      # Title normalization
│       │   └── ...
│       ├── database/              # SQLite caching (metacache, providercache)
│       ├── indexers/              # Content browsing (movies, tvshows, episodes)
│       └── windows/               # Custom Kodi window XMLs
```

### Dependencies

- `xbmc.python` (Kodi Python API)
- `script.module.requests` (HTTP client)
- `plugin.video.youtube` (optional)
- No external scraper addon is bundled — external scrapers are loaded dynamically at runtime from a user-configured separate addon.

---

## 2. Provider/Account Configuration

### How Credentials Are Stored

All credentials are stored as Kodi addon settings (key-value pairs persisted to `settings.xml` on disk). There is no database, no encryption, no vault — Kodi's built-in settings persistence is the only mechanism.

**Setting keys observed:**

| Provider     | Token/Key Setting        | Enable Setting          | Priority Setting        |
|-------------|--------------------------|-------------------------|-------------------------|
| Real-Debrid | `realdebridtoken`        | `realdebrid.enable`     | `realdebrid.priority`   |
| Premiumize  | `premiumizetoken`        | `premiumize.enable`     | `premiumize.priority`   |
| AllDebrid   | `alldebridtoken`         | `alldebrid.enable`      | `alldebrid.priority`    |
| TorBox      | `torboxtoken`            | `torbox.enable`         | `torbox.priority`       |
| OffCloud    | `offcloudtoken`          | `offcloud.enable`       | `offcloud.priority`     |
| Easynews    | `easynews.user` / `easynews.password` | `easynews.enable` | `easynews.priority` |

### Authentication Mechanisms

**Debrid providers (RD, PM, AD, TB, OC):** Use OAuth2 device-code flow or direct API token entry. The user triggers an "Authorize" action from settings, which:
1. Requests a device code from the provider's OAuth endpoint
2. Displays a URL and code to the user
3. Polls for authorization completion
4. Stores the resulting access token in settings

**TorBox** uses a simpler bearer token approach — the user provides an API key directly, which is sent as `Authorization: Bearer <token>` on every request.

**Easynews** uses HTTP Basic Auth — username and password are base64-encoded and sent as `Authorization: Basic <encoded>`.

### Provider Priority

Priority is stored as an integer setting per provider (e.g., `torbox.priority`). The `debrid.py` module's `get_priority()` function reads this:

```python
def get_priority(cls):
    return int(getSetting((cls.__class__.__name__ + '.priority').lower()))
```

The `debrid_resolvers()` function sorts providers by priority when `order_matters=True`. Lower number = higher priority.

Priority affects:
- The order debrid resolvers are tried during source resolution
- The sort order of results in the source selection UI

### There Is No Common Provider Abstraction

**Confirmed fact:** There is no shared base class, interface, or protocol that all debrid providers implement. Each debrid module (`realdebrid.py`, `torbox.py`, etc.) is a standalone class with similar-but-not-identical method signatures.

Common methods that exist across providers (by convention, not by contract):
- `check_cache(hashList)` — check if hashes are cached
- `resolve_magnet(magnet_url, info_hash, season, episode, title)` — resolve a magnet to a playable URL
- `add_uncached_torrent(magnet_url, pack=False)` — submit uncached content
- `unrestrict_link(link)` — convert a provider link to a direct download URL
- `account_info()` / `account_info_to_dialog()` — account status display
- `user_cloud()` — list files in the user's cloud storage
- `auth()` — OAuth authorization flow

**Important for Kondooit:** The lack of a formal interface means the orchestration layer (`sources.py`) contains explicit `if debrid_provider == 'Real-Debrid':` / `elif debrid_provider == 'TorBox':` branching in several places. This is a pattern Kondooit should not reproduce.

### Connection Testing

There is no dedicated "test connection" method. Account validity is implicitly verified:
- For debrid providers: the OAuth flow succeeds or fails
- For Easynews: a request to the account info page succeeds or fails
- For TorBox: `account_info()` returns data or raises an exception

---

## 3. Searching for Content — End-to-End Flow

### Entry Point

When a user selects a movie or episode for playback, the flow begins at `Sources.play()` or `Sources.getSources()`.

### Content Identity

Content is identified using a combination of metadata IDs:

**For movies:**
```python
data = {
    'title': 'The Batman',
    'aliases': [{'title': 'Batman', 'country': 'us'}, ...],
    'year': '2022',
    'imdb': 'tt1877830',
}
```

**For TV episodes:**
```python
data = {
    'title': 'Pilot',            # episode title
    'year': '2019',
    'imdb': 'tt0944947',
    'tvdb': '121361',
    'season': '1',
    'episode': '1',
    'tvshowtitle': 'Game of Thrones',
    'aliases': [...],
    'premiered': '2011-04-17',
}
```

**Key observation:** IMDb ID is the primary identifier used for database caching and deduplication. TMDb and TVDB IDs are carried but used less centrally. The `aliases` list supports international title variations.

### Scraper Dispatch Architecture

`Sources.getConstants()` assembles three lists of source providers:

1. **External scrapers** — loaded from a user-configured external addon (e.g., CocoScrapers). The external module exposes a `sources()` function that returns a list of `(name, module)` tuples. Each module has a `source` class with a `sources(data, hostDict)` method.

2. **Internal scrapers** — discovered via `pkgutil.walk_packages()` from `internal_scrapers/`. Currently: `easynews`, `plexshare`, `gdrive`, `filepursuit`. Each module has a `source` class with `sources(data, hostDict)`.

3. **Cloud scrapers** — discovered via `pkgutil.walk_packages()` from `cloud_scrapers/`. One per debrid provider: `rd_cloud`, `pm_cloud`, `ad_cloud`, `tb_cloud`, `oc_cloud`. Each searches the user's existing cloud storage on that debrid service.

### Thread Dispatch

All scrapers run concurrently in separate threads. For TV episodes, each scraper may be invoked up to 3 times:
- Single episode search
- Season pack search (if `pack_capable`)
- Show pack search (if `pack_capable`)

```python
for i in scraperDict:
    threads.append(Thread(
        target=self.getEpisodeSource,
        args=(imdb, season, episode, data, i[0], i[1], pack)
    ))
[i.start() for i in threads]
```

A timeout (default 90 seconds, user-configurable) limits total scrape time. Results accumulate in `self.scraper_sources` as threads complete.

### Result Caching

Scraper results are cached in a SQLite database (`rel_src` table) keyed by `(source_name, imdb_id, season, episode)`. Cache expiry:
- Single episodes: 6 hours
- Season packs: 48 hours  
- Show packs: 48 hours

If cached results exist and are still valid, the scraper is not called again.

---

## 4. Third-Party Scraper Architecture

### Interface Contract

External scrapers are loaded from a separate Kodi addon specified by the user in settings (`external_provider.module` and `external_provider.name`).

The external module must expose a `sources()` function that returns:
```python
[(scraper_name: str, scraper_module)]
```

Each scraper module must have a `source` class with these attributes and methods:

**Required attributes:**
- `priority: int` — sort order (not currently used for much)
- `pack_capable: bool` — whether this scraper can search for season/show packs
- `hasMovies: bool` — supports movie search
- `hasEpisodes: bool` — supports episode search

**Required methods:**
- `sources(data: dict, hostDict: list) -> list[dict]` — single item search
- `sources_packs(data, hostDict, search_series=False, total_seasons=None, bypass_filter=False) -> list[dict]` — pack search (if `pack_capable`)

**`data` dict passed to scrapers (episode example):**
```python
{
    'title': 'Episode Title',
    'year': '2019',
    'imdb': 'tt0944947',
    'tvdb': '121361',
    'season': '1',
    'episode': '1',
    'tvshowtitle': 'Game of Thrones',
    'aliases': [{'title': '...', 'country': '...'}],
    'premiered': '2011-04-17',
    'debrid_service': 'TorBox',    # optional
    'debrid_token': '...',          # optional
}
```

**`hostDict`** is a list of supported hoster domains (populated from debrid provider `get_hosts()` calls).

### What Scrapers Return

Each scraper returns a list of source dicts. The expected structure (from actual source inspection):

```python
{
    'provider': 'scraper_name',     # e.g., 'easynews', 'tb_cloud', scraper module name
    'source': 'torrent' | 'cloud' | 'direct' | 'cached torrent' | 'uncached torrent',
    'debrid': 'TorBox' | 'Real-Debrid' | ...,  # which debrid provider (if applicable)
    'name': 'Release.Name.2022.1080p.WEB-DL.mkv',
    'name_info': '.1080p.web-dl.x264.dd5.1.',   # extracted quality/codec/audio info
    'quality': '4K' | '1080p' | '720p' | 'SD' | 'SCR' | 'CAM',
    'language': 'en',
    'url': 'magnet:?xt=...' | 'https://...' | 'torrent_id,file_id,mediatype',
    'info': '1.5 GB / 1080p / x264 / DD5.1',   # formatted display string
    'direct': True | False,         # True = no debrid cache check needed
    'debridonly': True | False,     # True = requires debrid to resolve
    'size': 1.5,                    # size in GB (float)
    'seeders': 42,                  # optional, for torrent sources
    'hash': 'abc123...',            # info_hash for torrent/magnet
    'local': True | False,          # optional, for library sources
    'episode_start': 1,             # optional, for pack sources
    'episode_end': 10,              # optional, for pack sources
    'last_season': 5,               # optional, for show packs
}
```

### What Umbrella Does NOT Know About External Scrapers

The external scraper addon's internal implementation is opaque to Umbrella. Umbrella does not know:
- What torrent indexers the scrapers query
- How search queries are constructed inside each scraper
- How results are deduplicated
- What rate limiting or retry logic exists

Umbrella only sees the returned list of source dicts.

---

## 5. Cached vs. Uncached Content

### Cache Check Flow

After all scrapers return results, `Sources.sourcesFilter()` performs cache checking. This is one of the most architecturally important flows.

**Step 1: Separate direct from torrent sources**

```python
local = [i for i in self.sources if 'local' in i and i['local'] is True]
direct = [i for i in self.sources if i['direct'] == True]
# Everything else is a torrent source that needs cache checking
```

Direct sources (Easynews, Plex, cloud files, Google Drive) skip cache checking entirely — they are already playable.

**Step 2: Extract hashes from torrent sources**

For each torrent source, the info_hash is extracted from the magnet URL or `hash` field:
```python
hashList = [i['hash'].lower() for i in torrent_sources if i.get('hash')]
```

**Step 3: Per-debrid cache check (concurrent)**

Each enabled debrid provider runs its cache check in a separate thread:

```python
threads.append(Thread(target=checkStatus, args=(self.rd_cache_chk_list, 'Real-Debrid', valid_hoster)))
threads.append(Thread(target=checkStatus, args=(self.tb_cache_chk_list, 'TorBox', valid_hoster)))
# etc.
```

Each provider's cache check method:

**Real-Debrid:** `GET /torrents/instantAvailability/<hash1>/<hash2>/...`
- Returns a dict keyed by hash, with available file variants
- Checked BEFORE submitting anything — no magnet is added

**TorBox:** `POST /torrents/checkcached` with `{"hashes": [hash1, hash2, ...]}`
- Returns list of cached hash objects
- Also checked before submission

**Premiumize:** Similar batch hash check endpoint

**Step 4: Mark cached vs. uncached**

The `checkStatus` function (inside `sourcesFilter`) processes cache check responses. For each source:
- If the hash is found in the debrid provider's cache response → source is marked as `'cached torrent'` for that provider and labeled with the debrid provider name
- If not found → source is marked as `'uncached (debrid_name) torrent'`

Multiple debrid providers may each report cache status independently, so a single hash may be cached on RealDebrid but uncached on TorBox.

**Step 5: Sort and filter**

After cache checking, sources are sorted by:
1. Debrid provider priority
2. Quality (4K > 1080p > 720p > SD)
3. Size (user-configurable: prefer larger or smaller)
4. Source type (cached > direct > uncached)

Uncached sources are separated to the bottom of the list by default but can be shown via user settings.

### Key Architectural Insight

**Cache checking is a batch operation on hashes, performed BEFORE any magnet is submitted to any debrid provider.** This is critical: it means the addon can determine availability without triggering any downloads or consuming debrid quota.

---

## 6. Sending Uncached Content to Debrid Services

### When Uncached Sources Are Used

Uncached sources are only used when:
1. The user explicitly selects an uncached source from the source list, OR
2. No cached sources are available and autoplay is enabled with uncached fallback

### Submission Flow (TorBox Example)

```
User selects uncached source
    ↓
Sources.sourcesResolve(item)
    ↓
magnet URL detected + 'uncached' in source
    ↓
TorBox.add_uncached_torrent(magnet_url)
    ↓
TorBox.create_transfer(magnet_url)
    → POST /torrents/createtorrent {magnet, seed: 3, allow_zip: false}
    → Returns torrent_id
    ↓
Poll loop: TorBox.list_transfer(torrent_id)
    → GET /torrents/mylist?id=<torrent_id>
    → Check download_state == 'completed'
    → Display progress dialog (speed, seeds, percentage)
    → User can cancel (optionally deletes from TorBox)
    ↓
When completed:
    → Return True (caller then resolves the now-cached magnet)
```

### What Is Actually Submitted

- **Magnet links** are submitted (not .torrent files, not raw hashes)
- The magnet URL is sent to the provider's "add torrent" endpoint
- TorBox: `POST /torrents/createtorrent` with `{magnet: "magnet:?xt=..."}` 
- RealDebrid: `POST /torrents/addMagnet` with `{magnet: "magnet:?xt=..."}`

### Polling and Completion

- The addon polls the transfer status endpoint at regular intervals (typically 5 seconds)
- A progress dialog shows download speed, seed count, and completion percentage
- TorBox states: `metaDL` → `downloading` → `uploading` → `completed`
- RealDebrid: checks `torrents/activeCount` until the hash is no longer in the active list
- Timeout handling varies; the user can cancel at any time

### Post-Completion Resolution

Once the transfer completes, the flow is identical to cached source resolution:
1. Get the torrent's file list from the provider
2. Filter for video files matching the requested episode/movie
3. Get a direct download URL via `unrestrict_link()`

### Store-to-Cloud Option

Each provider has a `store_to_cloud` setting. If disabled, the torrent is deleted from the user's cloud after playback URL is obtained. If enabled, it remains for future access (and will appear in cloud scraper results).

---

## 7. Easynews / Usenet Behavior

### Fundamentally Different From Debrid

**Confirmed fact:** Easynews is handled through a completely different code path from debrid providers. It is:
- An **internal scraper** (in `internal_scrapers/easynews.py`), not a debrid provider
- Its results are marked `direct: True` and `debridonly: False`
- Its results skip cache checking entirely
- Its results are immediately playable via direct HTTP download

### Authentication

Easynews uses HTTP Basic Authentication:
```python
user_info = '%s:%s' % (username, password)
auth = 'Basic ' + b64encode(user_info.encode('utf-8')).decode('utf-8')
```
Credentials: `easynews.user` and `easynews.password` settings.

### Search Flow

**As an internal scraper**, the Easynews `source.sources(data, hostDict)` method:

1. Constructs a search query:
   - Movies: `"The Batman"` (title only, year verified in post-filtering)
   - Episodes: `"Game of Thrones S01E01"` (title + season/episode handler)

2. Calls Easynews's Solr search API:
   ```
   GET https://members.easynews.com/2.0/search/solr-search/advanced
   Params: gps=<query>, pby=1000, fex=m4v,3gp,...,mkv, fty[]=VIDEO, ...
   ```

3. Processes results: Each result contains:
   - `item['0']`: post_hash
   - `item['10']`: post_title (filename)
   - `item['11']`: file extension
   - `item['14']`: duration
   - `item['rawSize']`: file size in bytes
   - `item['alangs']`: audio languages

4. Constructs a direct download URL:
   ```python
   stream_url = down_url + quote('/%s/%s/%s%s/%s%s' % (dl_farm, dl_port, post_hash, ext, post_title, ext))
   file_dl = stream_url + '|Authorization=%s' % quote(auth)
   ```

5. Returns source dicts with `provider: 'easynews'`, `source: 'direct'`, `direct: True`

### Easynews Has TWO Code Paths

There are two separate Easynews implementations:

1. **`internal_scrapers/easynews.py`** — The scraper that participates in the automated source search flow. Returns standardized source dicts.

2. **`debrid/easynews.py`** — The standalone Easynews browser/manager. Provides its own search UI, search history (SQLite), account info display, and direct playback resolution. This is used when the user navigates to Easynews as a standalone menu item.

### How Easynews Differs From Debrid Architecturally

| Aspect | Debrid Providers | Easynews |
|--------|-----------------|----------|
| Authentication | OAuth2 device code / API token | HTTP Basic Auth |
| Source discovery | External scrapers find torrents → debrid checks cache | Easynews IS the source — direct search API |
| Cache concept | Hash-based cache check | Not applicable — search returns available files |
| Playback URL | Requires unrestrict/resolve step | Direct HTTP download URL |
| `direct` flag | `False` (needs cache check) | `True` (skip cache check) |
| `debridonly` flag | `True` | `False` |
| Cloud storage | User's debrid cloud | Not applicable |

### Kondooit Implication

Easynews is evidence that "source provider" is not a single abstraction. A Usenet provider like Easynews is simultaneously:
- A search provider (queries its own index)
- A source provider (returns directly playable results)
- NOT a debrid/cache provider (no hash-based cache concept)

This supports the idea that Kondooit should define source provider capabilities independently rather than assuming all source providers share a "search + cache check + resolve" pipeline.

---

## 8. Source/Result Data Model

### Canonical Source Dict Fields

From actual source code inspection, the following fields appear in source result dicts:

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `provider` | str | Scraper module name (e.g., `'easynews'`, `'tb_cloud'`, external scraper name) | Yes |
| `source` | str | Source type: `'torrent'`, `'cached torrent'`, `'uncached (RD) torrent'`, `'cloud'`, `'direct'` | Yes |
| `debrid` | str | Debrid provider name if applicable: `'TorBox'`, `'Real-Debrid'`, etc. | Conditional |
| `name` | str | Release/file name | Yes |
| `name_info` | str | Extracted metadata from filename (codecs, quality tags) | Yes |
| `quality` | str | Normalized quality: `'4K'`, `'1080p'`, `'720p'`, `'SD'`, `'SCR'`, `'CAM'` | Yes |
| `language` | str | Language code: `'en'` | Yes |
| `url` | str | Magnet URI, direct download URL, or provider-specific reference | Yes |
| `info` | str | Formatted display string: `'1.5 GB / 1080p / x264 / DD5.1'` | Yes |
| `direct` | bool | `True` = playable without debrid resolution | Yes |
| `debridonly` | bool | `True` = requires a debrid account to access | Yes |
| `size` | float | File size in GB | Yes |
| `seeders` | int | Torrent seed count | Optional |
| `hash` | str | Torrent info_hash (lowercase hex) | Conditional |
| `local` | bool | `True` = local library file | Optional |
| `episode_start` | int | First episode in pack | Optional (packs) |
| `episode_end` | int | Last episode in pack | Optional (packs) |
| `last_season` | int | Last season number in show pack | Optional (packs) |

### Quality Detection (`scrape_utils.py`)

Quality is detected by regex matching against the release title:

```python
RES_4K = ('2160', '216o', '.4k', 'ultrahd', 'ultra.hd', '.uhd.')
RES_1080 = ('1080', '1o8o', '108o', '1o80', '.fhd.')
RES_720 = ('720', '72o')
```

### Detailed Format Parsing (`source_utils.py`)

The `getFileType()` function extracts detailed format information from filenames:

- **Video codec:** H.264/AVC, H.265/HEVC, XVID, DIVX, MPEG, MP4, MKV
- **HDR:** Dolby Vision, HDR10, HDR
- **Audio codec:** Dolby TrueHD, Dolby Digital Plus, Dolby Digital, DTS-X, DTS-HD MA, DTS-HD, AAC, FLAC, MP3
- **Audio channels:** 2CH, 6CH (5.1), 7CH (6.1), 8CH (7.1)
- **Source type:** Blu-ray, DVD, WEB, HDRIP, Screener, Cam
- **Other:** REMUX, 3D, AI Upscaled, Hardcoded subs

This parsing is done against the filename string using tuple membership checks, not regex.

---

## 9. Provider Abstraction vs. Scraper Abstraction — Boundary Analysis

### Abstractions That Actually Exist in Umbrella

Umbrella has **three distinct layers** that are separate in the code but lack formal interfaces:

#### Layer 1: Source Discovery (Scrapers)

**Responsibility:** Find potential sources for a given piece of content.

**Implementations:**
- External scrapers (torrent indexer scrapers, loaded from separate addon)
- Cloud scrapers (search user's existing debrid cloud storage)
- Internal scrapers (Easynews, Plex, Google Drive, FilePursuit)

**Interface (informal):**
```python
class source:
    priority: int
    pack_capable: bool
    hasMovies: bool
    hasEpisodes: bool
    
    def sources(self, data: dict, hostDict: list) -> list[dict]: ...
    def sources_packs(self, data, hostDict, ...) -> list[dict]: ...  # if pack_capable
    def resolve(self, url: str) -> str: ...  # for cloud/internal scrapers
```

**Output:** List of source dicts (see section 8).

#### Layer 2: Cache Verification (Debrid Providers)

**Responsibility:** Check if a given hash is already cached/available on a debrid provider.

**Implementations:** RealDebrid, Premiumize, AllDebrid, TorBox, OffCloud

**Operations:**
- `check_cache(hashList)` — batch cache availability check
- Returns which hashes are instantly available

#### Layer 3: Source Resolution (Debrid Providers)

**Responsibility:** Convert a magnet/hash into a playable direct URL.

**Operations:**
- `resolve_magnet(magnet_url, info_hash, season, episode, title)` — cached resolution
- `add_uncached_torrent(magnet_url)` — uncached submission + polling
- `unrestrict_link(link)` — convert provider link to direct download

### Which Responsibilities Are Combined

**Debrid providers combine layers 2 and 3** — the same class (`RealDebrid`, `TorBox`, etc.) handles both cache checking and source resolution. This is reasonable because both operations require the same authentication and API access.

**Cloud scrapers bridge layers 1 and 3** — they search the user's debrid cloud (layer 1: discovery) but use the debrid provider's API (layer 3: resolution). For example, `tb_cloud.py` imports `TorBox` and calls `TorBox().user_cloud()` for discovery, and its `resolve()` method calls `TorBox().unrestrict_link()` for resolution.

**`sources.py` is the orchestrator** — it ties all three layers together but contains excessive provider-specific branching because there are no formal interfaces.

### Which Responsibilities Are Separated

- **Metadata** is completely separate from source discovery. Umbrella uses Trakt, TMDb, TVMaze for metadata, and they have no relationship to the scraper/debrid layer.
- **Scraper search** is separate from **cache checking** — scrapers return ALL potential sources (cached and uncached), and cache checking happens afterwards as a separate step.
- **Quality/format parsing** is centralized in `scrape_utils.py` and `source_utils.py`, used by all scrapers.

### Boundaries That Are Useful for Kondooit

1. **Metadata Provider ≠ Source Provider** — Already established in Kondooit's architecture and confirmed by Umbrella's design.

2. **Source Discovery ≠ Cache Verification ≠ Source Resolution** — These are three distinct capabilities that happen to be combined in some implementations but are conceptually separate.

3. **The scraper interface (`sources(data, hostDict) -> list[dict]`)** — A simple, uniform contract that allows heterogeneous source providers (torrent indexers, Usenet, cloud storage, direct hosters) to participate in the same search pipeline.

4. **Batch cache checking** — Cache status should be determined as a batch operation on hashes, not per-source sequentially. This is a performance-critical design decision.

5. **Direct sources vs. debrid sources** — A fundamental branching point: direct sources (Easynews, local files, IPTV) are immediately playable; debrid sources require cache check → resolution.

### Patterns Worth Adapting

1. **Uniform source result structure** — All source providers return the same dict structure regardless of whether they search torrents, Usenet, cloud storage, or direct links. Kondooit should define a canonical `SourceResult` domain entity.

2. **Capability-based provider dispatch** — `hasMovies`, `hasEpisodes`, `pack_capable` are capability flags that determine which search operations a scraper participates in. This aligns with Kondooit's existing capability declaration architecture.

3. **Concurrent scraping with timeout** — Multiple source providers searched simultaneously with a configurable timeout. The user sees results accumulating in real-time.

4. **Source caching by content identity** — Scraper results cached by `(scraper_name, imdb_id, season, episode)` with configurable expiry. Avoids re-searching for frequently accessed content.

5. **Post-search filtering pipeline** — Quality filters, language filters, format filters, size filters applied AFTER scraping, not during. This keeps scrapers simple and filtering centralized.

### Patterns to Explicitly Avoid

1. **No formal provider interface** — Umbrella's duck-typing approach works for a single-developer Kodi addon but would be fragile in Kondooit. Provider interfaces should be explicit.

2. **Provider-specific branching in the orchestrator** — `sources.py` contains dozens of `if provider == 'Real-Debrid':` branches. Kondooit should use polymorphism through defined interfaces instead.

3. **Settings-as-database** — Kodi settings are a flat key-value store with no structure, validation, or migration. Kondooit already has proper database infrastructure.

4. **`eval()` for deserialization** — Umbrella uses `eval(db_row[4])` to deserialize cached source results. This is a security risk and should not be reproduced.

5. **Two implementations of the same provider** — Easynews has code in both `internal_scrapers/` and `debrid/` with duplicated logic. Kondooit should have a single implementation per provider with different entry points.

6. **Thread-based concurrency** — Umbrella uses raw `Thread` objects with shared mutable lists and `control.sleep()` polling. Kondooit (Python + asyncio via Litestar) should use async/await patterns instead.

---

## 10. Proposed Concept Mapping to Kondooit

**These are analytical observations, not implementation decisions. An ADR should be written before any of these become architecture.**

### Concept Mapping

| Umbrella Concept | Kondooit Equivalent | Notes |
|-----------------|--------------------|----|
| External scraper addon | Source Discovery Provider (plugin interface) | Kondooit owns the interface; providers implement it |
| Cloud scraper | Debrid Cloud Source | A capability of debrid providers, not a separate scraper type |
| Internal scraper (Easynews) | Direct Source Provider | Different capability profile from debrid providers |
| Debrid provider class | Source Resolution Provider | Formal interface with cache check + resolve capabilities |
| Source dict | `SourceResult` domain entity | Canonical, provider-independent representation |
| `sources.py` orchestrator | Source Discovery Service (application layer) | Coordinates discovery, cache check, resolution |
| `source_utils.py` / `scrape_utils.py` | Release Parsing Service | Title/quality/format extraction |
| Hash cache check | Source Availability Check | Provider capability: can check availability by hash |
| `unrestrict_link()` | Source Resolution | Provider capability: convert reference to playable URL |
| `add_uncached_torrent()` | Source Acquisition | Provider capability: initiate download/transfer |

### Suggested Capability Taxonomy

Based on the research, source providers could declare capabilities from this set:

- `SEARCH` — Can search for sources given content identity
- `CLOUD_SEARCH` — Can search user's existing cloud/library
- `CACHE_CHECK` — Can batch-check hash availability
- `RESOLVE` — Can convert a cached reference to a playable URL
- `ACQUIRE` — Can initiate download of uncached content
- `DIRECT_STREAM` — Results are immediately playable (no resolution needed)

**Example capability profiles:**

| Provider | SEARCH | CLOUD_SEARCH | CACHE_CHECK | RESOLVE | ACQUIRE | DIRECT_STREAM |
|----------|--------|-------------|-------------|---------|---------|--------------|
| TorBox | - | Yes | Yes | Yes | Yes | - |
| Real-Debrid | - | Yes | Yes | Yes | Yes | - |
| Easynews | Yes | - | - | - | - | Yes |
| Torrent Indexer Scraper | Yes | - | - | - | - | - |
| Local Files | - | Yes | - | - | - | Yes |
| IPTV Provider | - | Yes | - | - | - | Yes |

### The Full Playback Pipeline (Conceptual)

```
User selects Movie/Episode
    ↓
Source Discovery Service
    ├── Query all enabled source providers (by capability)
    │   ├── Torrent indexer scrapers → magnet results
    │   ├── Easynews → direct results
    │   ├── Debrid cloud scrapers → cloud file results
    │   ├── Local file scanner → local results
    │   └── IPTV provider → stream results
    ↓
Normalize all results → SourceResult entities
    ↓
Cache Check Service (for results with hashes)
    ├── TorBox.check_cache(hashes)
    ├── RealDebrid.check_cache(hashes)
    └── ... (concurrent, per enabled debrid provider)
    ↓
Annotate each SourceResult with availability per provider
    ↓
Filter + Sort (quality, size, cached status, provider priority)
    ↓
Present to user (or auto-select)
    ↓
Source Resolution
    ├── Direct sources → play immediately
    ├── Cached debrid sources → resolve to playable URL
    └── Uncached debrid sources → initiate acquisition, poll, then resolve
```

---

## 11. External Scraper Internals — CocoScrapers Analysis

**Source:** `coco_lib_research.txt` — full source dump of the CocoScrapers library
**Status:** This section answers the questions previously listed as "cannot be determined."

CocoScrapers is the external scraper addon that Umbrella loads via dynamic import. It provides torrent indexer scrapers that participate in Umbrella's source discovery pipeline.

### 11.1 CocoScrapers Repository Structure

```
coco_lib/cocoscrapers/
├── __init__.py                         # Dynamic module loader, sources(), enabledCheck()
├── sources_cocoscrapers/
│   └── torrents/                       # One module per torrent indexer
│       ├── 1337x.py
│       ├── bitcq.py
│       ├── bitlord.py
│       ├── bitsearch.py
│       ├── comet.py                    # Stremio Comet addon bridge
│       ├── eztv.py                     # TV-only site
│       ├── isohunt2.py
│       ├── kickass2.py
│       ├── knaben.py                   # Torrent aggregator
│       ├── mediafusion.py              # Stremio MediaFusion addon bridge
│       ├── nyaa.py                     # Anime-focused
│       ├── piratebay.py
│       ├── torrentdownload.py
│       ├── torrentfunk.py
│       ├── torrentgalaxy.py
│       ├── torrentio.py                # Stremio Torrentio addon bridge
│       ├── torrentproject2.py
│       ├── torrentquest.py
│       ├── yourbittorrent.py
│       └── ytsmx.py                    # Movies only, uses IMDb ID query
├── modules/
│   ├── cache.py                        # SQLite result caching with TTL
│   ├── cleantitle.py                   # Title normalization
│   ├── client.py                       # HTTP client wrapper
│   ├── source_utils.py                 # Quality/format detection
│   ├── Thread_pool.py                  # Thread pool singleton
│   ├── workers.py                      # Worker thread management
│   ├── undesirables.py                 # Known-bad release group filter
│   ├── prowlarr.py                     # Prowlarr API integration
│   ├── mediafusion.py                  # MediaFusion shared client
│   ├── dom_parser.py                   # HTML DOM parsing utilities
│   ├── log_utils.py                    # Logging
│   ├── control.py                      # Settings/path helpers
│   └── cfscrape/                       # Cloudflare bypass infrastructure
│       ├── __init__.py                 # CloudScraper session (extends requests.Session)
│       ├── cloudflare.py               # CF challenge detection and solving
│       ├── exceptions.py               # Exception hierarchy
│       ├── captcha/                    # Third-party captcha solving
│       │   ├── 2captcha.py
│       │   ├── 9kw.py
│       │   ├── anticaptcha.py
│       │   ├── capmonster.py
│       │   └── deathbycaptcha.py
│       ├── interpreters/               # JS challenge solvers
│       │   ├── native.py               # Pure Python (pyparsing + AST)
│       │   ├── nodejs.py               # Node.js subprocess
│       │   ├── js2py.py                # js2py library
│       │   ├── chakracore.py           # ChakraCore via ctypes
│       │   └── v8.py                   # V8 via v8eval
│       └── user_agent/                 # Browser fingerprint management
│           └── browsers.json           # UA strings and cipher suites
├── help/                               # User documentation
│   ├── torrentInfo.txt                 # Scraper speed tiers and status
│   ├── undesirablesFilter.txt          # Bad release group list
│   ├── packScrapers.txt                # Pack scraping docs
│   └── EasyNews_titleCheck.txt         # Easynews title matching docs
└── windows/                            # Kodi UI XML
```

### 11.2 Scraper Speed Tiers

CocoScrapers classifies scrapers by how many HTTP requests they require per search, which directly affects speed:

**Tier 1 — API-based (fast, priority 1-2):**
- `bitlord` (priority 1) — API endpoint
- `piratebay` (priority 2) — API endpoint
- `ytsmx` (priority 2) — uses IMDb ID query, movies only

**Tier 2 — Single-request HTML parsed (medium, priority 3-5):**
- `bitsearch` (priority 3)
- `knaben` (priority 3) — torrent aggregator
- `torrentdownload` (priority 3)
- `eztv` (priority 4) — TV shows only, no packs
- `kickass2` (priority 4) — intermittent availability
- `nyaa` (priority 5) — anime

**Tier 3 — Two-request HTML parsed (slow, priority 6-9):**
- `1337x` (priority 8) — requires search page + detail page per result
- `isohunt2` (priority 7)
- `torrentfunk` (priority 7)
- `torrentproject2` (priority 6)
- `yourbittorrent` (priority 9)

**Special — Stremio addon bridges:**
- `torrentio` — queries the Torrentio Stremio addon API
- `mediafusion` — queries the MediaFusion Stremio addon API
- `comet` — queries the Comet Stremio addon API

**Cloudflare-protected sites** use the `cfscrape` module (cloudscraper): `torrentgalaxy`

### 11.3 How Individual Scrapers Work

Each scraper module follows a consistent pattern (by convention, not enforced by a base class):

```python
class source:
    priority = 3
    pack_capable = True
    hasMovies = True
    hasEpisodes = True
    
    def __init__(self):
        self.language = ['en']
        self.base_link = 'https://...'      # site URL
        self.search_link = '/search/...'     # search endpoint pattern
    
    def sources(self, data, hostDict):
        # 1. Extract title, year, IMDb ID from data dict
        # 2. Construct search URL (title-based keyword search)
        # 3. HTTP GET the search page
        # 4. Parse HTML or JSON response
        # 5. For each result:
        #    a. Extract magnet link or info_hash
        #    b. Extract file size, seeders
        #    c. Verify title match via cleantitle comparison
        #    d. Detect quality from title (source_utils)
        #    e. Build source dict
        # 6. Return list of source dicts
    
    def sources_packs(self, data, hostDict, search_series=False, ...):
        # Similar but searches for "Title S01" or "Title Complete"
```

**Search query construction** varies by scraper:
- Most scrapers: `title + year` for movies, `title + S##E##` for episodes
- `ytsmx`: Uses IMDb ID directly via API
- `torrentio`/`mediafusion`/`comet`: Pass IMDb ID to Stremio addon API
- Pack searches: `title + S##` for season packs, `title + Complete` for show packs

**Title verification** is a critical post-search step. After retrieving results, each scraper calls `cleantitle.get()` to normalize both the search title and each result title, then compares them. This filters out false matches from broad keyword searches. Some scrapers (like Easynews) allow disabling title checks via settings to get more results at the cost of potential false matches.

### 11.4 Prowlarr Integration

CocoScrapers includes a `prowlarr.py` module that can delegate indexer searching to a running Prowlarr instance rather than scraping sites directly.

**What this means:** Prowlarr is an indexer aggregator from the *arr ecosystem (Sonarr, Radarr, etc.). It maintains connections to many torrent indexers and provides a unified search API. CocoScrapers can optionally use Prowlarr as a "meta-scraper" — sending one search request to Prowlarr, which fans out to its configured indexers and returns aggregated results.

**Kondooit implication:** This is an example of an ecosystem workaround becoming a feature. Prowlarr exists because the *arr applications each need indexer access but don't want to duplicate indexer management. CocoScrapers integrating with Prowlarr means it can piggyback on an existing Prowlarr installation. In a unified system like Kondooit, indexer management would be built in — there would be no need for a separate Prowlarr instance. However, the pattern of "query a single aggregator API rather than N individual sites" is a valid architectural pattern regardless.

### 11.5 Stremio Addon Bridges (Torrentio, MediaFusion, Comet)

Three scrapers are bridges to Stremio ecosystem addons:

- **`torrentio.py`** — Queries the Torrentio addon, which itself aggregates results from multiple torrent indexers and debrid providers
- **`mediafusion.py`** — Queries the MediaFusion addon, a similar aggregator
- **`comet.py`** — Queries the Comet addon

These bridges work by:
1. Calling the Stremio addon's `/stream/{type}/{imdbId}.json` endpoint
2. Parsing the returned stream objects (which contain magnet links, quality info, etc.)
3. Converting them to CocoScrapers' source dict format

**Kondooit implication:** This is a clear ecosystem workaround. These Stremio addons exist as standalone services because Stremio's architecture is addon-based. CocoScrapers bridges to them because they provide access to indexers and caches that CocoScrapers doesn't directly support. In Kondooit, the underlying capabilities (indexer search, cache check) would be built in directly — there is no need to bridge to external Stremio addons. The existence of these bridges is evidence of ecosystem fragmentation, not of a capability Kondooit should reproduce.

### 11.6 Cloudflare Bypass Infrastructure

The `cfscrape` module is a substantial piece of infrastructure (over 2000 lines) dedicated to bypassing Cloudflare's anti-bot protection on torrent sites.

**What it does:**
- Detects Cloudflare v1 IUAM (I'm Under Attack Mode) challenges
- Detects Cloudflare v2 challenges (which it cannot solve in the open-source version)
- Detects Cloudflare captcha challenges (reCaptcha, hCaptcha)
- Solves v1 JS challenges via multiple JavaScript interpreter backends (native Python, Node.js, js2py, ChakraCore, V8)
- Delegates captcha solving to third-party paid services (2captcha, 9kw, anticaptcha, capmonster, deathbycaptcha)
- Manages browser-like TLS fingerprinting (cipher suites, user-agent rotation, Brotli decompression)

**Kondooit implication:** This is entirely an implementation detail and ecosystem workaround. Cloudflare bypass is necessary because torrent indexer websites use Cloudflare to prevent automated scraping. The bypass code is:
1. Fragile — it breaks whenever Cloudflare updates their challenge mechanism (the code documents many scrapers removed because CF v2 defeated them)
2. An arms race — not a sustainable architectural foundation
3. Irrelevant if Kondooit uses API-based indexer access (like Prowlarr's approach) or provider APIs that don't require scraping web pages

This should NOT become a Kondooit domain concept. If Kondooit needs to access web-based indexers, the HTTP client layer may need to handle site-specific challenges, but this belongs purely in infrastructure, not in the domain or application layers.

### 11.7 Result Caching

CocoScrapers has its own SQLite-based cache (`cache.py`), separate from Umbrella's provider cache:

- Cache key: MD5 hash of `function_name + args`
- Cache value: `repr()` of the function's return value (stored as text, deserialized via `literal_eval()`)
- Expiry: configurable per call site, measured in hours
- Concurrency: `timeout=60` on SQLite connections for thread safety
- Pragmas: `synchronous=OFF`, `journal_mode=OFF` for performance (at the cost of crash safety)

**Stale cache fallback:** If a fresh scrape returns no results (site down, etc.), the cache returns the old (expired) results rather than nothing. This is a pragmatic resilience pattern.

### 11.8 Undesirables Filter

CocoScrapers maintains a hardcoded list of known-bad release groups and keywords that indicate garbage results:

```
UNDESIRABLES = ['400p.octopus', '720p.octopus', 'alexfilm', 'audiobook',
'bonus.disc', '.cbr', '.cbz', '.exe', 'extras.only', 'rifftrax', 
'sample', 'soundtrack', 'subtitle.only', 'teaser', 'trailer', ...]
```

These are filtered out of results before returning to Umbrella. The list is primarily:
- Foreign-language-only release groups (Russian dubbing teams)
- Non-video content (audiobooks, comics, soundtracks, executables)
- Incomplete content (samples, teasers, trailers, extras)

**Kondooit implication:** Source result filtering by content quality/validity is a genuine domain capability. However, the specific filter list is an implementation detail that would need to be maintained and configurable. It should not be hardcoded into the domain.

### 11.9 Dynamic Scraper Discovery and Enable/Disable

The `__init__.py` loader discovers scrapers at runtime:

```python
def sources(specified_folders=None, ret_all=False):
    for loader, module_name, is_pkg in walk_packages([sourceFolderLocation]):
        if ret_all or enabledCheck(module_name):
            module = loader.find_spec(module_name).loader.load_module(module_name)
            append((module_name, module.source))

def enabledCheck(module_name):
    return getSetting('provider.' + module_name) == 'true'
```

Each scraper can be individually enabled/disabled via a Kodi setting (`provider.1337x`, `provider.piratebay`, etc.). The `pack_sources()` function filters to only scrapers where `module.source.pack_capable == True`.

**Kondooit implication:** This confirms that scraper-level enable/disable and capability flags (`pack_capable`, `hasMovies`, `hasEpisodes`) are used in practice. Kondooit's existing provider capability declaration architecture (ADR-0010) aligns with this pattern.

### 11.10 Scraper Internal Provider Abstraction

**Confirmed: CocoScrapers has NO formal scraper interface.** Each scraper module independently implements the expected `source` class with `sources()` and optionally `sources_packs()`. There is no base class, no abstract interface, no shared contract enforcement. The convention is enforced only by what Umbrella's `sources.py` expects to call.

The thread pool (`Thread_pool.py`) is the closest thing to shared infrastructure — it provides a singleton thread pool that multiple scrapers use for concurrent HTTP requests within a single scrape operation.

---

## 12. Complete Ecosystem Architecture — How Everything Connects

With both Umbrella and CocoScrapers analyzed, the full picture of how these systems work together is:

```
User selects content in Kodi
    ↓
Umbrella (sources.py) — Orchestrator
    ├── Loads CocoScrapers via dynamic import
    │   └── CocoScrapers discovers and loads enabled torrent scrapers
    │       ├── Direct site scrapers (1337x, piratebay, eztv, ...)
    │       │   └── Some use cfscrape for Cloudflare bypass
    │       ├── Prowlarr bridge (if Prowlarr configured)
    │       │   └── Prowlarr fans out to its configured indexers
    │       └── Stremio bridges (torrentio, mediafusion, comet)
    │           └── These query external Stremio addon APIs
    ├── Loads internal scrapers (Easynews, Plex, GDrive, FilePursuit)
    └── Loads cloud scrapers (rd_cloud, tb_cloud, pm_cloud, ad_cloud, oc_cloud)
        └── These search the user's existing debrid cloud storage
    ↓
All scrapers run concurrently in threads (90s timeout)
    ↓
Results accumulate → list of source dicts
    ↓
Cache check phase (torrent sources only)
    ├── Extract info_hashes from all torrent sources
    ├── RealDebrid.check_cache(hashes) — concurrent
    ├── TorBox.check_cache(hashes) — concurrent
    ├── Premiumize.check_cache(hashes) — concurrent
    └── etc.
    ↓
Mark each source as cached/uncached per debrid provider
    ↓
Filter + Sort (quality, size, cache status, provider priority)
    ↓
Present source list to user (or auto-select)
    ↓
Resolution phase
    ├── Direct sources (Easynews, cloud, GDrive) → play immediately
    ├── Cached torrent → debrid.resolve_magnet() → playable URL
    └── Uncached torrent → debrid.add_uncached_torrent() → poll → resolve
```

### Ecosystem Fragmentation Evidence

The analysis reveals significant ecosystem fragmentation:

1. **CocoScrapers bridges to Prowlarr** — which is itself an indexer aggregator from the *arr ecosystem. This means CocoScrapers sometimes delegates to Prowlarr rather than scraping directly.

2. **CocoScrapers bridges to Stremio addons** (Torrentio, MediaFusion, Comet) — these are standalone services in the Stremio ecosystem that aggregate torrent sources. CocoScrapers queries them as if they were torrent indexers.

3. **Umbrella bridges to CocoScrapers** — which is a separately maintained addon with its own update cycle, settings, and module discovery.

4. **Each layer has its own caching** — Umbrella caches scraper results in SQLite, CocoScrapers has its own SQLite cache for HTTP responses, and debrid providers have their own server-side caches.

5. **Configuration is spread across systems** — Debrid credentials in Umbrella settings, scraper enable/disable in CocoScrapers settings, Prowlarr URL/API key in CocoScrapers settings, Stremio addon URLs in CocoScrapers settings.

**This fragmentation is exactly what Kondooit should eliminate.** The underlying capabilities are:
- Search torrent indexers for content
- Check debrid cache availability
- Resolve cached content to playable URLs
- Search Usenet for content
- Stream directly from certain providers

These capabilities do not inherently require 5+ separate applications, 3 separate caching layers, and bridges between ecosystems.

---

## 13. Remaining Information Gaps

1. **TorBox API response schemas** — Exact response formats are inferred from how the code parses them, but the official API documentation would provide authoritative schemas.

2. **Debrid provider rate limits** — Whether providers enforce rate limits on cache check or resolve endpoints. The code includes some retry/semaphore logic (RealDebrid uses `Semaphore(3)`) suggesting awareness of limits.

3. **Easynews search quality** — How well Easynews's Solr search performs for different types of content. The code sends a simple keyword query with video file type filtering.

4. **OffCloud behavior** — The OffCloud implementation was not inspected in detail during this analysis pass.

5. **Service.py background tasks** — The background service module was not inspected. It likely handles pre-scraping, library updates, or periodic tasks.

6. **Individual scraper internals** — While the general pattern is documented above, each scraper's specific HTML parsing, pagination logic, and error handling was not individually analyzed. The source code is available in the research file if needed.

---

## 14. Summary of Findings for Kondooit

### Genuine Domain Capabilities Identified

1. **Content Source Discovery** — Searching multiple indexers/providers for sources matching a content identity (title + year + external IDs)
2. **Batch Cache Availability Check** — Determining which discovered sources are instantly available on debrid providers
3. **Source Resolution** — Converting a cached reference (hash/magnet) into a playable URL
4. **Source Acquisition** — Initiating download of uncached content and monitoring progress
5. **Direct Source Access** — Accessing sources that are immediately playable without debrid (Usenet, local files, IPTV)
6. **Release Quality/Format Parsing** — Extracting quality, codec, audio, and format metadata from release titles
7. **Source Result Filtering** — Filtering by quality, size, language, and content validity
8. **Provider Capability Declaration** — Each provider declares what it can do (search, cache check, resolve, direct stream)

### Implementation Details NOT to Reproduce

1. **Cloudflare bypass** — An arms race, not a sustainable capability
2. **Stremio addon bridges** — Ecosystem workaround for fragmented infrastructure
3. **Prowlarr delegation** — Necessary only because indexer management is in a separate application
4. **Duck-typed scraper interface** — Works for single-developer addons, not for a formal system
5. **Settings-as-database** — Kodi-specific limitation
6. **`eval()`/`literal_eval()` deserialization** — Security risk
7. **Raw thread concurrency with shared mutable state** — Use async/await in Kondooit
8. **Separate caching at every layer** — Unify caching in a single, coherent layer
9. **Hardcoded undesirables list** — Should be configurable, not baked into source code

### Ecosystem Workarounds Identified

1. **CocoScrapers as a separate addon** — Exists because Kodi's addon architecture requires separate packages. Not needed in a unified system.
2. **Prowlarr integration** — Exists because indexer management is separated into its own application. In Kondooit, indexer management is a built-in capability.
3. **Stremio bridges** — Exist because Stremio is a separate ecosystem with its own addon model. These bridge two ecosystems that Kondooit unifies.
4. **Cloudflare bypass module** — Exists because torrent indexer web UIs use anti-bot protection. API-based access (where available) or Kondooit-managed indexer connections avoid this.
5. **Dual Easynews implementation** — Exists because Umbrella's scraper architecture doesn't cleanly accommodate a provider that is simultaneously a search source and a direct stream source.
6. **Per-application caching** — Exists because Umbrella and CocoScrapers are separate applications with no shared state. Unified system = unified cache.

---

## 15. Magneto Scraper Library — Comparative Analysis

**Source:** `magneto_lib_research.txt` — full source dump of the Magneto scraper library
**Analysis Date:** 2026-08-22
**Status:** Research only — no Kondooit implementation changes

Magneto is a fork/descendant of CocoScrapers (originally FenomScrapers) used as an alternative external scraper addon. It shares the same infrastructure layer (cfscrape/CloudScraper, client.py, dom_parser.py) but introduces several architecturally significant patterns not present in CocoScrapers.

### 15.1 Structural Differences from CocoScrapers

Magneto adds:
- A dedicated **player subsystem** (`player/`) with source selection windowed UI, navigator, and aioStreams integration
- A **health check module** (`modules/health.py`) for provider monitoring
- **Additional Stremio-protocol providers:** TorrentsDB (alongside the existing Torrentio, MediaFusion)
- References to **hash-database indexers** (bitmagnet, zilean, dmm) and **newer aggregators** (torz, meteor) — these were declared in routing but implementations were not included in the code dump

### 15.2 Stremio Addon Bridge Pattern (Expanded)

Magneto reveals that the Stremio addon bridge pattern is more significant than CocoScrapers alone suggested. Three providers use the identical Stremio stream protocol:

| Provider | Base URL | Backing Sources |
|----------|----------|----------------|
| Torrentio | `torrentio.strem.fun` | YTS, EZTV, RARBG, 1337x, PirateBay, KickassTorrents, TorrentGalaxy, NyaaSi, Rutor, and others |
| MediaFusion | `mediafusionfortheweebs.midnightignite.me` | Unknown, self-hosted scraping infrastructure |
| TorrentsDB | `torrentsdb.com` | YTS, EZTV, 1337x, TorrentCSV, 1lou, Nyaa, LimeTorrent, RARBG, Knaben, PirateBay, KickassTorrents, AnimeTosho, YggTorrent, Rutor, Rutracker, Torrent9, and ~20 others |

All three use the same API shape:

```
GET /stream/movie/{imdb_id}.json         -> {"streams": [...]}
GET /stream/series/{imdb_id}:{s}:{e}.json -> {"streams": [...]}
```

Each stream object contains:
```json
{
  "infoHash": "abc123...",
  "title": "Release.Name.2022.1080p\n💾 1.5 GB\n👤 42",
  "description": "Release.Name.2022.1080p\n┈➤ file.mkv\n💾 1.5 GB\n👤 42"
}
```

Metadata (size, seeders) is embedded in the title/description strings using emoji delimiters and must be regex-parsed.

**Key insight:** These Stremio-protocol aggregators are priority 1 (highest) because they are pre-indexed — they return results instantly from a database rather than scraping sites in real-time. They effectively replace the need for many individual site scrapers, providing the same hashes from a single fast API call.

**Kondooit implication (updated):** While the CocoScrapers analysis concluded that Stremio bridges were purely ecosystem workarounds, Magneto's usage reveals a more nuanced picture. The Stremio stream protocol (`/stream/{type}/{id}.json`) has become a de facto standard for torrent hash aggregation services. Several independent services (Torrentio, MediaFusion, TorrentsDB) expose this protocol with different backing indexer sets. Rather than bridging to Stremio addons specifically, Kondooit could consume these as what they actually are: **pre-indexed hash aggregation APIs**. The protocol is trivial (HTTP GET, JSON with infoHash), making it a low-risk integration target with high value (access to 20+ indexers via a single request).

### 15.3 Queue-Based Result Sharing Pattern

Magneto introduces an optimization not present in CocoScrapers for Stremio-protocol providers:

```python
class source:
    _queue = queue.SimpleQueue()
    
    def sources(self, data, hostDict):
        # Fetch from API once
        results = client.request(url)
        files = jsloads(results)['streams']
        # Put results into queue for pack queries to consume
        self._queue.put_nowait(files)  # for season packs
        self._queue.put_nowait(files)  # for show packs
        # Process individual episode matches...
    
    def sources_packs(self, data, hostDict, ...):
        # Consume shared results instead of making duplicate API call
        files = self._queue.get(timeout=self.timeout + 1)
        # Process pack matches from same data...
```

**Why this matters:** The Stremio stream API returns ALL available hashes for a given IMDB ID regardless of season/episode granularity. Both the single-episode search and the pack search operate on the same dataset. Rather than calling the API twice (once for `sources()`, once for `sources_packs()`), the first call shares its results via a queue.

**Kondooit implication:** When implementing source discovery, if a single API call returns results relevant to multiple query types (episode + season pack + show pack), the system should fetch once and filter multiple ways rather than making redundant requests. This is a standard optimization but worth noting because it contradicts the simple "one call per capability invocation" model.

### 15.4 Health Check / Provider Monitoring

Magneto includes a health check module (`modules/health.py`) that validates provider availability:

**How it works:**
1. User triggers health check from settings menu
2. System uses a known movie as a test case (X-Men, 2000, tt0120903)
3. All enabled providers are instantiated and run concurrently via `ThreadPoolExecutor`
4. Each provider's `sources(data, {})` is called with the test data
5. Response time is measured per provider
6. Results are counted by quality tier (4K, 1080p, 720p, SD)
7. Results are displayed in a sorted list (fastest first, fatal errors last)

**Provider states:**
- Working: returns results with timing
- Empty: returns 0 results (site may be down or blocking)
- Fatal: raises an exception

**Kondooit implication:** Provider health monitoring is a genuine operational capability. Knowing whether a source provider is functional, slow, or broken allows the system to:
- Skip known-broken providers to reduce latency
- Alert the user when a configured provider stops working
- Inform provider priority decisions

This capability should be noted but is not needed until source providers are actually implemented.

### 15.5 Provider Class Metadata (Formalized)

Magneto makes provider metadata more explicit than CocoScrapers:

```python
class source:
    timeout = 10          # Per-provider timeout (Stremio bridges)
    priority = 1          # Numeric priority (1 = highest)
    pack_capable = True   # Supports season/show pack queries
    hasMovies = True      # Supports movie search
    hasEpisodes = True    # Supports episode search
    _queue = queue.SimpleQueue()  # Result sharing (Stremio bridges only)
```

**Priority distribution observed:**
- Priority 1: Pre-indexed aggregators (Torrentio, MediaFusion, TorrentsDB)
- Priority 3: Single-request site scrapers (Knaben, TorrentDownload)
- Priority 4-5: Standard HTML scrapers (Kickass2)
- Priority 6: Multi-request scrapers (TorrentProject2)

**Timeout patterns:**
- Stremio bridge providers: `timeout = 10` (class-level, used for both HTTP request and queue.get)
- Traditional scrapers: `timeout=5` or `timeout=7` (per-request, inline in client.request call)

### 15.6 Content Filtering Pipeline (Confirmed Across Both Libraries)

Both CocoScrapers and Magneto apply the same filtering pipeline in the same order within every scraper:

```
1. source_utils.check_title(title, aliases, name, hdlr, year)
   -> Validates the result actually matches the requested content
   -> Compares normalized titles, checks year/handler match
   -> REJECT if title doesn't match

2. source_utils.info_from_name(name, title, year, hdlr, episode_title)
   -> Extracts format/quality metadata from the release name
   -> Returns a metadata string used for subsequent checks

3. source_utils.remove_lang(name_info, check_foreign_audio)
   -> Filters results tagged as foreign-language-only audio
   -> REJECT if foreign audio detected and setting enabled

4. source_utils.remove_undesirables(name_info, undesirables)
   -> Filters results matching known-bad release groups/keywords
   -> REJECT if undesirable keyword found

5. Episode-in-movie filter (movies only):
   -> Regex check for S##E## patterns in results
   -> REJECT if episode markers found in a movie query result

6. source_utils.get_release_quality(name_info, url)
   -> Determines quality tier: 4K, 1080p, 720p, SD

7. source_utils._size(size_string)
   -> Parses human-readable size to numeric bytes
```

**Kondooit implication:** This pipeline is uniform across ALL providers in both libraries. It represents a genuine domain concern (validating and classifying source results) that belongs in a centralized service, not duplicated per-provider. The ordering matters: title validation first (cheapest, highest rejection rate), then format extraction, then successive filters.

### 15.7 Referenced But Unimplemented Providers

Magneto's entry point references several providers whose implementations were not in the code dump:

| Provider | Likely Purpose | Evidence |
|----------|---------------|----------|
| bitmagnet | DHT hash database with API | Known open-source project: self-hosted DHT indexer that catalogs torrent hashes from the BitTorrent DHT network |
| zilean | DMM hash scraping service | Known project: scrapes Debrid Media Manager shared libraries for hashes |
| dmm | Debrid Media Manager integration | Known project: web app for managing debrid library, exposes shared hash lists |
| torz | Unknown aggregator | No public documentation found |
| meteor | Unknown aggregator | No public documentation found |

**What these represent architecturally:**

Bitmagnet and Zilean represent a **third category of source discovery** not documented in the CocoScrapers analysis:

1. **Traditional scrapers** — Query torrent indexer websites, parse HTML/API responses
2. **Pre-indexed aggregators** — Query Stremio-protocol services that maintain their own indexes
3. **Hash databases** — Query services that maintain databases of known torrent hashes without being traditional indexers

Hash databases differ from traditional indexers because:
- They don't scrape sites in real-time
- They don't provide seeder counts (or provide stale ones)
- They may source hashes from DHT crawling (bitmagnet) or from scraping debrid user libraries (zilean/dmm)
- They are typically self-hosted by the user
- They provide massive hash catalogs but with less metadata per hash

**Kondooit implication:** The source discovery capability should accommodate hash-database providers alongside traditional indexers and pre-indexed aggregators. The key difference is that hash-database results may lack quality metadata (seeders, accurate size) that traditional scrapers provide. The cache check step becomes more important for these providers since they can return many hashes with no liveness information.

### 15.8 Revised Source Provider Taxonomy

Based on both CocoScrapers and Magneto analysis, source providers can be categorized into five distinct types:

| Type | Discovery Method | Result Quality | Speed | Examples |
|------|-----------------|---------------|-------|----------|
| **Pre-indexed Aggregator** | JSON API by IMDB ID | High (hash + size + seeders) | Fast (single request) | Torrentio, MediaFusion, TorrentsDB |
| **API Indexer** | JSON/REST API by keyword | High | Fast | PirateBay API, BitLord API, YTS |
| **HTML Scraper** | HTTP + DOM parsing | Medium | Slow (1-2 requests + parsing) | 1337x, Knaben, KickAss, TorrentDownload |
| **Hash Database** | JSON API by IMDB ID or title | Low (hash only, maybe size) | Fast | Bitmagnet, Zilean, DMM |
| **Direct Source** | Provider-specific API | High | Medium | Easynews (Solr search) |

**Key observation:** The trend in this ecosystem is moving from Type 3 (HTML scrapers) toward Type 1 (pre-indexed aggregators) and Type 4 (hash databases). HTML scrapers are fragile (Cloudflare, site layout changes, domain changes) while API-first services are stable and fast.

**Kondooit implementation priority recommendation:**
1. Pre-indexed aggregators (trivial protocol, high value, stable)
2. Hash databases (if user self-hosts bitmagnet/zilean)
3. Debrid APIs for cache check + resolution (required for the end of the pipeline)
4. Easynews (direct source, simple integration)
5. API-based indexers (stable but limited catalog)
6. HTML scrapers (fragile, high maintenance — implement last or not at all)

### 15.9 Updated Architecture Evidence

Magneto confirms and extends the architectural observations from CocoScrapers:

**Confirmed:**
- The three-layer pipeline (discovery -> cache check -> resolution) is universal
- Capability-based provider dispatch (`hasMovies`, `hasEpisodes`, `pack_capable`) is used by all providers
- The source dict schema is stable across both libraries
- Provider priority affects dispatch ordering
- Content filtering is applied uniformly post-discovery

**New evidence:**
- Pre-indexed aggregators should be treated as first-class provider types (not ecosystem workarounds)
- Hash databases are a distinct provider category requiring different handling
- Provider health monitoring is a viable operational capability
- Single-fetch-multiple-filter is a practical optimization pattern
- Per-provider timeout configuration is needed (aggregators tolerate 10s; scrapers should timeout at 5-7s)

---

## 16. Updated Summary of Findings for Kondooit

### Revised Capability List (Post-Magneto Analysis)

1. **Content Source Discovery** — Searching multiple indexers/providers for sources matching a content identity
2. **Batch Cache Availability Check** — Determining which discovered sources are instantly available on debrid providers
3. **Source Resolution** — Converting a cached reference (hash/magnet) into a playable URL
4. **Source Acquisition** — Initiating download of uncached content and monitoring progress
5. **Direct Source Access** — Accessing sources that are immediately playable without debrid
6. **Release Quality/Format Parsing** — Extracting quality, codec, audio, and format metadata from release titles
7. **Source Result Filtering** — Filtering by quality, size, language, and content validity
8. **Provider Capability Declaration** — Each provider declares what it can do
9. **Provider Health Monitoring** — Validating provider availability and performance (NEW from Magneto)
10. **Source Result Caching** — Caching discovery results by content identity with TTL expiry

### Revised Provider Integration Priority

Based on stability, implementation complexity, and value:

| Priority | Provider Type | Rationale |
|----------|--------------|-----------|
| 1 | Debrid APIs (TorBox, Real-Debrid) | Required for cache check + resolution — the end of the pipeline |
| 2 | Pre-indexed hash aggregators (Torrentio-protocol) | Single HTTP GET returns dozens of hashes from 20+ indexers. Trivial to implement, extremely high value-to-effort ratio |
| 3 | Easynews | Direct source, simple HTTP Basic Auth + Solr search, immediately playable results |
| 4 | Self-hosted hash databases (bitmagnet, zilean) | API-based, user-controlled, no fragility concerns |
| 5 | API-based indexers (PirateBay, YTS) | Stable but limited catalog |
| 6 | HTML scrapers | High maintenance, Cloudflare risk — implement last or not at all |

### Revised Patterns to Avoid

1. **Cloudflare bypass** — Arms race, fragile
2. **HTML scraping as a primary strategy** — Prefer API-based sources
3. **Duck-typed interfaces** — Use formal contracts
4. **Raw thread concurrency** — Use async/await
5. **eval() deserialization** — Security risk
6. **Hardcoded filter lists** — Make configurable
7. **Duplicate API calls for same data** — Fetch once, filter multiple ways
8. **Treating pre-indexed aggregators as workarounds** — They are legitimate, stable, high-value data sources regardless of their ecosystem origin
