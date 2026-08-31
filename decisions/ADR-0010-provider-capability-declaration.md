# ADR-0010: Provider capability declaration

- **Status:** Accepted
- **Date:** 2026-08-18
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should the provider abstraction handle providers that support different sets of discovery operations?"

## Context

The current `MetadataProvider` interface defines a fixed set of methods (search_movies, search_series, get_trending_movies, get_trending_series, get_genres, get_movie, get_series) that every provider must implement. TVDB does not support "trending movies" or "now playing" — the current implementation returns an empty list for `get_trending_movies`, which is an honest but informal workaround.

TMDB provides substantially richer discovery functionality than TVDB: discover (with 30+ filters), now playing, upcoming, popular, trending (all/movie/tv), and genre-specific endpoints. TVDB provides search, series details, movie details, and a series filter endpoint, but no equivalent of discover, now playing, or upcoming.

Forcing every provider to implement every method leads to one of two problems:
1. Providers implement fake/empty equivalents of capabilities they do not have.
2. The abstraction is weakened to the lowest common denominator, dropping useful capabilities that only some providers support.

Neither is acceptable. The vision states: "The provider abstraction should represent capabilities, rather than forcing every provider to implement artificial equivalents of functionality it does not support."

## Decision

Providers **declare which discovery capabilities they support**. The aggregation layer queries each provider only for capabilities it declares.

Capability declaration is explicit:

```python
class MetadataProvider(Protocol):
    def supported_discoveries(self) -> set[DiscoveryCapability]:
        ...
```

Where `DiscoveryCapability` is an enum of discovery operations:

- `SEARCH_MOVIES` — search for movies by query
- `SEARCH_SERIES` — search for TV series by query
- `TRENDING_MOVIES` — trending/popular movies
- `TRENDING_SERIES` — trending/popular TV series
- `NOW_PLAYING_MOVIES` — movies currently in theaters
- `UPCOMING_MOVIES` — upcoming movie releases
- `POPULAR_MOVIES` — popular movies (distinct from trending)
- `POPULAR_SERIES` — popular TV series
- `DISCOVER_MOVIES` — discover movies with filters
- `DISCOVER_SERIES` — discover TV series with filters
- `GENRES_MOVIE` — movie genre list
- `GENRES_TV` — TV genre list
- `MOVIE_DETAILS` — full movie metadata by ID
- `SERIES_DETAILS` — full TV series metadata by ID (including seasons/episodes)

A provider returns the set of capabilities it actually supports. The aggregation layer calls a provider's method only if the corresponding capability is declared. If no enabled provider supports a capability, that discovery section is simply absent from the UI.

## Rationale

TMDB and TVDB have genuinely different capabilities. TMDB has discover, now playing, upcoming, and popular endpoints. TVDB has search, series details, and a series filter. Forcing TVDB to implement `get_now_playing_movies()` would require either a fake empty result or an artificial approximation. Forcing TMDB to drop discover because TVDB cannot support it would discard a valuable capability.

Capability declaration lets each provider be honest about what it can do. The aggregation layer adapts. The UI shows what is available.

## Alternatives considered

- **Keep the current fixed interface, providers return empty lists for unsupported operations.** Rejected: this is an informal workaround that makes it impossible to distinguish "this provider supports this capability but returned no results" from "this provider does not support this capability at all." It also forces providers to implement methods they cannot meaningfully fulfill.

- **Create separate interfaces for each capability (e.g., `TrendingCapable`, `DiscoverCapable`).** Rejected: this fragments the provider interface into many small protocols and makes registration and aggregation more complex. A single interface with capability declaration is simpler and sufficient.

- **Make all methods optional (return `None` or raise `NotImplementedError`).** Rejected: this is functionally similar to returning empty lists but with worse ergonomics. Explicit capability declaration is clearer for both the provider implementor and the aggregation layer.

## Consequences

- The `MetadataProvider` interface gains a `supported_discoveries()` method that returns a set of `DiscoveryCapability` values.
- Each provider implementation declares only the capabilities it actually supports.
- The aggregation layer checks `supported_discoveries()` before calling a provider's discovery method.
- The UI shows discovery sections based on what the enabled providers collectively support. If no provider supports "now playing," that section does not appear.
- TVDB no longer needs to return `[]` for `get_trending_movies` — it simply does not declare `TRENDING_MOVIES` as a supported capability.
- New providers can be added that support only a subset of capabilities without implementing fake methods.

## Relationship to other ADRs

- **ADR-0002** (Provider vs. source): Supported. This ADR applies to metadata providers. Source providers (future) will have their own capability declarations.
- **ADR-0009** (Provider-driven discovery): Supported. Capability declaration is the mechanism that makes provider-driven discovery work when providers have different capabilities.
