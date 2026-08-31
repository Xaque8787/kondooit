# ADR-0011: Provider priority and fallback behavior

- **Status:** Accepted
- **Date:** 2026-08-20
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should the aggregation layer handle multiple enabled providers — merge all results, prefer one provider, or fall back sequentially?"

## Context

ADR-0009 established provider-driven discovery. ADR-0010 established capability declaration. Neither addressed what happens when multiple enabled providers support the same capability.

The current implementation queries all enabled providers in parallel and merges results. This produces two problems:

1. **Duplicate representations.** The same movie may appear once from TMDB and again from TVDB, because deduplication is only by `provider_key:external_id`. There is no cross-provider identity resolution.

2. **Inconsistent landing page.** A landing page mixing TMDB trending movies with TVDB trending series — from different data sources with different ranking methodologies — produces an incoherent user experience.

The intended model is:

- **Search:** Query the highest-priority provider. If it returns meaningful results, use them. If not, fall back to the next provider by priority. Do not return duplicates from multiple providers.

- **Discovery:** Use the highest-priority configured provider as the primary discovery source. If TMDB is configured, the landing page should primarily look like a TMDB-powered experience. A lower-priority provider is used only when the primary provider is unavailable, disabled, unconfigured, or does not support the requested capability. The landing page is not a multi-provider aggregator.

- **Kondooit is not an imported-content catalog.** Provider APIs are the source of discovery and metadata. Users browse and search provider catalogs without importing content into Kondooit's database. The database stores Kondooit/application state (users, provider configuration, provider priority, favorites, following, eventually watch/progress state), not a local copy of the provider catalog.

- **User state is preference/state, not a content catalog.** Favorites and Following are user preference/state records. Kondooit does not import or own content metadata when a user favorites or follows a title. The database stores only the user's relationship to the content reference; metadata is always retrieved from the provider when needed.

- **Provider IDs are references, not content identity.** A user favorites "The Matrix," not "tmdb/movie/603." The provider reference is how Kondooit currently retrieves metadata, not the conceptual identity of the content.

## Decision

### Provider priority is explicit and configurable

Each provider configuration has a `priority` field (integer, lower number = higher priority). The default priority is assigned by registration order but can be changed by the user through provider configuration.

### Three distinct fallback conditions

The aggregation layer must distinguish three different conditions when interacting with a provider:

**A. Provider does not support a capability.**

The provider's `supported_discoveries()` set does not include the requested capability. Skip this provider entirely and try the next provider by priority that supports the capability. This is not an error condition — it is a normal capability mismatch.

**B. Provider supports the capability but returns zero results.**

The provider declares the capability and the request succeeds, but the response contains no results. For search, this triggers fallback to the next provider by priority. For discovery sections, this means the section is absent (no fallback to a different provider for the same section — the primary provider has authority over this capability).

**C. Provider request fails.**

The provider declares the capability but the HTTP request fails (timeout, network error, authentication failure, 5xx response). This is distinct from a legitimate zero-result response. The aggregation layer must not silently merge another provider's results with the failed provider's results as if nothing happened. Instead:

- Log the failure with enough detail to distinguish it from a zero-result response.
- For search: fall back to the next provider by priority, same as zero results.
- For discovery: the section is absent. A lower-priority provider may supply the section if it supports the capability.
- The API response may optionally include metadata about which providers were queried and whether any failed, so the UI can surface provider health information.

This three-way distinction prevents the current problem where a failed provider request silently produces an empty result that gets merged with another provider's data, making it impossible to tell whether content is genuinely unavailable or a provider is broken.

### Search uses sequential fallback

For search (title query):

1. Order enabled providers by priority (ascending).
2. Find the first provider that supports the search capability (condition A — skip providers that don't support it).
3. Query that provider.
4. If it returns meaningful results (condition B — non-empty), return those results. Do not query other providers.
5. If it returns zero results (condition B — empty) or the request fails (condition C), fall back to the next provider by priority that supports the capability.
6. Do not merge results from multiple providers for the same search query.

This prevents duplicate results and gives the user results from their preferred provider when available.

### Discovery uses a primary provider with per-section capability fallback

For the landing page and discovery sections:

1. Determine the highest-priority enabled provider. This is the primary discovery provider.
2. Use the primary provider for all discovery sections it supports. If TMDB is configured, the landing page should primarily look like a TMDB-powered experience.
3. If the primary provider does not support a particular capability (condition A), check whether the next provider by priority supports it. If so, use that provider for that specific section.
4. If the primary provider supports a capability but returns zero results (condition B), the section is absent. Do not fall back to another provider for the same section — the primary provider has authority over this capability.
5. If the primary provider's request fails (condition C), the section is absent. A lower-priority provider may supply the section if it supports the capability.
6. Each discovery section is sourced from a single provider — sections are never merged across providers.
7. Do not merge TMDB and TVDB discovery results simply because both are enabled. The goal is not to create a duplicate multi-provider catalog on the landing page.

This means the landing page is coherent: all trending content comes from one provider, all popular content comes from one provider, etc. A section may come from a different provider than other sections (when the primary provider doesn't support that capability), but no single section mixes providers.

### Kondooit is not an imported-content catalog

Provider APIs are the source of discovery and metadata. Users browse and search provider catalogs without importing content into Kondooit's database. The database stores Kondooit/application state:

- Users and authentication
- Provider configuration and priority
- Favorites and Following (user state)
- Eventually: watch/progress state
- Eventually: cached metadata, if deliberately decided to be worthwhile

The database does not store a local copy of the provider catalog. Browsing a movie on the landing page does not create a database record. The old import-driven catalog model is obsolete and will be removed from the application layer once the replacement discovery architecture is working. Existing database tables and migrations are preserved until an intentional migration determines which persistence structures remain useful.

### User state is preference/state, not a content catalog

Favorites and Following are stored as user preference/state records: `user_id + provider_key + content_type + external_id + is_favorite + is_following`. This database state exists to remember what the user wants to track. It does not import, copy, or own content metadata.

When the user's Movies/TV Shows pages need to display favorited or followed titles, Kondooit retrieves current metadata from the appropriate provider using the stored provider reference. The database stores the relationship, not the content.

This distinction is architectural: Kondooit is not building a local canonical content catalog through user state. The provider layer remains the source of content metadata. User state is a thin reference layer that connects users to provider-sourced content.

### Provider IDs are references with a documented migration path

Favorites, Following, and all user state reference content by `provider_key + content_type + external_id`. This is the current implementation reference, not the permanent identity model. The architecture must not equate "tmdb/movie/603" with "The Matrix" as an identity — it is merely how Kondooit currently knows how to retrieve metadata for that content.

**Current choice and its limitation.** Storing provider IDs directly in user state creates a known problem: if a user favorites "The Matrix" via TMDB and later switches to TVDB as their primary provider, Kondooit cannot automatically recognize that the TVDB representation is the same content. The favorite still exists, but it is bound to the TMDB reference.

**Migration path.** A lightweight Kondooit content identity/reference layer may eventually be appropriate for user state. This would be a thin mapping table:

```
Kondooit content identity
  ├── TMDB: movie 550
  ├── TVDB: movie 12345
  └── ...

favorites
  ├── user_id
  └── content_id (Kondooit identity)
```

This would let user state survive provider changes without requiring Kondooit to maintain a complete canonical catalog. It is a mapping, not a content database.

**When to migrate.** This identity layer is explicitly deferred. It becomes necessary when:
- Multiple metadata providers are simultaneously enabled and users need their state to be provider-agnostic, OR
- Source discovery and playback are implemented and content identity must be resolved across metadata and source providers.

Until then, `provider_key + content_type + external_id` is sufficient. The implementation must not hard-code assumptions that prevent this migration — the user state table structure should be designed so that a content identity column could be added later without a breaking migration.

Cross-provider identity resolution is explicitly out of scope for the current milestone.

## Rationale

The current parallel-merge approach produces duplicates and inconsistent ranking. Sequential fallback for search is simpler, avoids duplicates, and matches the user's mental model: "search my preferred source, and only check the other source if the first has nothing."

A primary provider for the landing page prevents the page from becoming a mixture of data from different sources with different ranking methodologies. If TMDB is configured, the landing page is a TMDB-powered experience. TVDB supplements only where TMDB lacks a capability. Each section is coherent and comes from one provider.

The three-way distinction between "unsupported," "zero results," and "request failed" is necessary because the current implementation conflates all three into the same empty-list path, making it impossible to distinguish legitimate "no content" from a broken provider. This causes silent failures where a provider is down but the user sees no indication of a problem.

The explicit statement that Kondooit is not an imported-content catalog prevents the architecture from drifting back toward the old import-driven model. Provider APIs are the source of discovery and metadata. The database stores application state, not provider content.

The documented migration path for user state identity ensures that the current `provider_key + external_id` choice does not paint the architecture into a corner. A future lightweight content identity layer can be added without a breaking migration, allowing user state to become provider-agnostic when that becomes necessary.

## Alternatives considered

- **Merge all providers, deduplicate by cross-provider identity.** Rejected: requires a cross-provider identity resolution system, which is explicitly out of scope. Priority-based provider selection should prevent most provider collision without identity resolution.

- **Always use only the highest-priority provider, never fall back.** Rejected: if the primary provider does not support a capability (e.g., TVDB does not support "now playing movies"), the user would never see that section even if another provider supports it. The per-section capability fallback is more useful.

- **Let the user choose per-section which provider to use.** Rejected: this is configuration complexity that does not benefit the user at this stage. Provider priority is sufficient.

- **Store favorites/following with a canonical Kondooit content UUID now.** Rejected for now: this requires identity resolution at favorite-time, which depends on cross-provider mapping. The `provider_key + external_id` reference is sufficient for the current milestone. The migration path is documented so this can be added later without a breaking migration.

- **Treat request failures the same as zero results (silent fallback).** Rejected: this makes it impossible to distinguish a broken provider from a provider that genuinely has no content. The three-way distinction enables better observability and user feedback.

- **Build a lightweight content identity layer now.** Rejected: not necessary with only TMDB + TVDB and priority-based provider selection. The identity layer becomes necessary when users need provider-agnostic state, which depends on cross-provider identity resolution — explicitly deferred.

## Consequences

- The `ProviderConfig` dataclass and `ProviderSettingModel` gain a `priority` field (integer).
- The `ProviderConfigRepository.get_all()` returns providers ordered by priority.
- `DiscoveryService` is restructured: search uses sequential fallback; landing-page discovery uses a primary provider with per-section capability fallback.
- The aggregation layer distinguishes unsupported capabilities, zero-result responses, and request failures, handling each differently.
- The `_dedup_movies` / `_dedup_series` methods are retained for safety but should rarely encounter duplicates since results come from a single provider.
- Favorites and Following store `provider_key + content_type + external_id` as a reference, not as content identity. The table structure must allow a `content_id` column to be added later without a breaking migration.
- The old import-driven catalog application code (CatalogController, CatalogService, import endpoints) will be removed from the application layer once the replacement discovery architecture is working. Database tables and migrations are preserved.
- The architecture remains ready for a future lightweight content identity layer and cross-provider identity resolution without requiring either now.

## Relationship to other ADRs

- **ADR-0009** (Provider-driven discovery): Supported. This ADR defines how multiple providers are orchestrated within the provider-driven discovery model.
- **ADR-0010** (Provider capability declaration): Supported. The per-section capability fallback uses capability declaration to determine which provider can supply a section.
- **ADR-0003** (Core owns canonical identity): Supported. This ADR reinforces that provider IDs are references, not canonical identity. The core may eventually assign canonical UUIDs through a lightweight identity layer, but that is deferred. The migration path is documented.
