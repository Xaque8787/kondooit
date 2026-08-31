import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";
import type { DiscoverySection, DiscoveryGenre, DiscoveredMovie, DiscoveredSeries } from "../types";
import { Poster, Rating, LoadingSpinner, ErrorState, EmptyState } from "../components/ui";

type MediaFilter = "all" | "movie" | "series";

export function DashboardPage() {
  const { user } = useAuth();
  const [sections, setSections] = useState<DiscoverySection[]>([]);
  const [genres, setGenres] = useState<DiscoveryGenre[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>("all");
  const [selectedGenreId, setSelectedGenreId] = useState<number | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<(DiscoveredMovie | DiscoveredSeries)[]>([]);
  const [searching, setSearching] = useState(false);
  const [isSearchMode, setIsSearchMode] = useState(false);

  const [discoverResults, setDiscoverResults] = useState<(DiscoveredMovie | DiscoveredSeries)[]>([]);
  const [discovering, setDiscovering] = useState(false);

  useEffect(() => {
    Promise.all([
      api.getLandingPage(),
      api.getDiscoveryGenres(),
    ])
      .then(([s, g]) => {
        setSections(s);
        setGenres(g);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredGenres = genres.filter((g) => {
    if (mediaFilter === "all") return true;
    return g.content_type === mediaFilter;
  });

  const uniqueGenres = filteredGenres.reduce<DiscoveryGenre[]>((acc, g) => {
    if (!acc.some((existing) => existing.external_id === g.external_id && existing.name === g.name)) {
      acc.push(g);
    }
    return acc;
  }, []);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setIsSearchMode(false);
      setSearchResults([]);
      return;
    }
    setIsSearchMode(true);
    setSearching(true);
    try {
      let results: (DiscoveredMovie | DiscoveredSeries)[];
      if (mediaFilter === "movie") {
        results = await api.searchDiscoveryMovies(searchQuery);
      } else if (mediaFilter === "series") {
        results = await api.searchDiscoverySeries(searchQuery);
      } else {
        results = await api.searchAll(searchQuery);
      }
      setSearchResults(results);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSearching(false);
    }
  }, [searchQuery, mediaFilter]);

  useEffect(() => {
    if (selectedGenreId === null) {
      setDiscoverResults([]);
      return;
    }
    setDiscovering(true);
    api
      .discoverByGenre([selectedGenreId], mediaFilter)
      .then(setDiscoverResults)
      .catch((e) => setError(e.message))
      .finally(() => setDiscovering(false));
  }, [selectedGenreId, mediaFilter]);

  const handleMediaFilterChange = (f: MediaFilter) => {
    setMediaFilter(f);
    setSelectedGenreId(null);
    if (isSearchMode && searchQuery.trim()) {
      setTimeout(() => handleSearch(), 0);
    }
  };

  const handleGenreSelect = (genreId: number | null) => {
    setSelectedGenreId(genreId);
    if (genreId !== null) {
      setIsSearchMode(false);
      setSearchQuery("");
      setSearchResults([]);
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const handleSearchClear = () => {
    setSearchQuery("");
    setIsSearchMode(false);
    setSearchResults([]);
  };

  const filteredSections = sections.filter((section) => {
    if (mediaFilter === "all") return true;
    if (mediaFilter === "movie") return section.movies.length > 0;
    if (mediaFilter === "series") return section.series.length > 0;
    return true;
  });

  const isGenreFiltering = selectedGenreId !== null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-3xl font-bold text-ink-100 mb-2">
        Welcome back, {user?.username}
      </h1>
      <p className="text-ink-400 mb-6">
        Discover movies and TV shows from your configured metadata providers.
      </p>

      {/* Search */}
      <div className="relative mb-6">
        <input
          type="text"
          placeholder="Search movies and TV shows..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          className="w-full bg-ink-900 border border-ink-700 rounded-lg px-4 py-3 pr-20 text-ink-100 placeholder-ink-500 focus:outline-none focus:border-brand-500 transition-colors"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {searchQuery && (
            <button
              onClick={handleSearchClear}
              className="p-1.5 text-ink-400 hover:text-ink-200 transition-colors"
              aria-label="Clear search"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <button
            onClick={handleSearch}
            className="p-2 text-ink-400 hover:text-brand-400 transition-colors"
            aria-label="Search"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Media type toggle */}
      <div className="flex items-center gap-2 mb-4">
        {(["all", "movie", "series"] as MediaFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => handleMediaFilterChange(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mediaFilter === f
                ? "bg-brand-600 text-white"
                : "bg-ink-800 text-ink-300 hover:bg-ink-700"
            }`}
          >
            {f === "all" ? "All" : f === "movie" ? "Movies" : "TV Shows"}
          </button>
        ))}
      </div>

      {/* Genre filter */}
      {uniqueGenres.length > 0 && (
        <div className="mb-10">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-ink-500 uppercase tracking-wide mr-1">Genre</span>
            <button
              onClick={() => handleGenreSelect(null)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                selectedGenreId === null
                  ? "bg-ink-700 text-ink-100"
                  : "bg-ink-800/60 text-ink-400 hover:bg-ink-800 hover:text-ink-200"
              }`}
            >
              All
            </button>
            {uniqueGenres.map((g) => (
              <button
                key={`${g.external_id}-${g.content_type}`}
                onClick={() => handleGenreSelect(g.external_id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  selectedGenreId === g.external_id
                    ? "bg-brand-600 text-white"
                    : "bg-ink-800/60 text-ink-400 hover:bg-ink-800 hover:text-ink-200"
                }`}
              >
                {g.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && <LoadingSpinner label="Loading discovery" />}
      {error && <ErrorState message={error} />}

      {/* Search results */}
      {isSearchMode && !loading && (
        <div className="mb-10">
          <h2 className="text-xl font-semibold text-ink-100 mb-4">
            Search results for &ldquo;{searchQuery}&rdquo;
          </h2>
          {searching ? (
            <LoadingSpinner label="Searching" />
          ) : searchResults.length === 0 ? (
            <EmptyState title="No results found" description="Try a different search term." />
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {searchResults.map((item, idx) => {
                const isMovie = "release_date" in item;
                const link = isMovie
                  ? `/movie/${item.provider_key}/${item.external_id}`
                  : `/series/${item.provider_key}/${item.external_id}`;
                return (
                  <Link key={`${item.provider_key}:${item.external_id}:${idx}`} to={link} className="group">
                    <div className="card aspect-[2/3] overflow-hidden">
                      <Poster
                        path={item.poster_path}
                        alt={item.title}
                        className="w-full h-full group-hover:scale-105 transition-transform duration-300"
                      />
                    </div>
                    <div className="mt-2">
                      <h3 className="text-sm font-medium text-ink-200 truncate group-hover:text-brand-400 transition-colors">
                        {item.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        {isMovie && (item as DiscoveredMovie).release_date && (
                          <span className="text-xs text-ink-500">
                            {(item as DiscoveredMovie).release_date!.substring(0, 4)}
                          </span>
                        )}
                        {!isMovie && (item as DiscoveredSeries).first_air_date && (
                          <span className="text-xs text-ink-500">
                            {(item as DiscoveredSeries).first_air_date!.substring(0, 4)}
                          </span>
                        )}
                        <Rating value={item.vote_average} />
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Genre discover results */}
      {isGenreFiltering && !isSearchMode && !loading && (
        <div className="mb-10">
          <h2 className="text-xl font-semibold text-ink-100 mb-4">
            {uniqueGenres.find((g) => g.external_id === selectedGenreId)?.name || "Filtered"} results
          </h2>
          {discovering ? (
            <LoadingSpinner label="Discovering" />
          ) : discoverResults.length === 0 ? (
            <EmptyState title="No results" description="No content found for this genre." />
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {discoverResults.map((item, idx) => {
                const isMovie = "release_date" in item;
                const link = isMovie
                  ? `/movie/${item.provider_key}/${item.external_id}`
                  : `/series/${item.provider_key}/${item.external_id}`;
                return (
                  <Link key={`${item.provider_key}:${item.external_id}:${idx}`} to={link} className="group">
                    <div className="card aspect-[2/3] overflow-hidden">
                      <Poster
                        path={item.poster_path}
                        alt={item.title}
                        className="w-full h-full group-hover:scale-105 transition-transform duration-300"
                      />
                    </div>
                    <div className="mt-2">
                      <h3 className="text-sm font-medium text-ink-200 truncate group-hover:text-brand-400 transition-colors">
                        {item.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        {isMovie && (item as DiscoveredMovie).release_date && (
                          <span className="text-xs text-ink-500">
                            {(item as DiscoveredMovie).release_date!.substring(0, 4)}
                          </span>
                        )}
                        {!isMovie && (item as DiscoveredSeries).first_air_date && (
                          <span className="text-xs text-ink-500">
                            {(item as DiscoveredSeries).first_air_date!.substring(0, 4)}
                          </span>
                        )}
                        <Rating value={item.vote_average} />
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Default discovery sections (when not searching/filtering) */}
      {!isSearchMode && !isGenreFiltering && !loading && !error && (
        <>
          {filteredSections.length === 0 ? (
            <EmptyState
              title="No content available"
              description="Configure and enable a metadata provider to start discovering content."
              action={
                <Link to="/providers" className="btn-primary">
                  Configure providers
                </Link>
              }
            />
          ) : (
            <div className="space-y-12">
              {filteredSections.map((section) => (
                <section key={section.title}>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-ink-100">
                      {section.title}
                    </h2>
                    {section.section_key && (
                      <Link
                        to={`/discover/${section.section_key}`}
                        className="text-sm text-brand-400 hover:text-brand-300 transition-colors"
                      >
                        See All &rarr;
                      </Link>
                    )}
                  </div>
                  {section.movies.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                      {section.movies.slice(0, 10).map((m, idx) => (
                        <Link
                          key={`${m.provider_key}:${m.external_id}:${idx}`}
                          to={`/movie/${m.provider_key}/${m.external_id}`}
                          className="group"
                        >
                          <div className="card aspect-[2/3] overflow-hidden">
                            <Poster
                              path={m.poster_path}
                              alt={m.title}
                              className="w-full h-full group-hover:scale-105 transition-transform duration-300"
                            />
                          </div>
                          <div className="mt-2">
                            <h3 className="text-sm font-medium text-ink-200 truncate group-hover:text-brand-400 transition-colors">
                              {m.title}
                            </h3>
                            <div className="flex items-center gap-2 mt-1">
                              {m.release_date && (
                                <span className="text-xs text-ink-500">
                                  {m.release_date.substring(0, 4)}
                                </span>
                              )}
                              <Rating value={m.vote_average} />
                            </div>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                  {section.series.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                      {section.series.slice(0, 10).map((s, idx) => (
                        <Link
                          key={`${s.provider_key}:${s.external_id}:${idx}`}
                          to={`/series/${s.provider_key}/${s.external_id}`}
                          className="group"
                        >
                          <div className="card aspect-[2/3] overflow-hidden">
                            <Poster
                              path={s.poster_path}
                              alt={s.title}
                              className="w-full h-full group-hover:scale-105 transition-transform duration-300"
                            />
                          </div>
                          <div className="mt-2">
                            <h3 className="text-sm font-medium text-ink-200 truncate group-hover:text-brand-400 transition-colors">
                              {s.title}
                            </h3>
                            <div className="flex items-center gap-2 mt-1">
                              {s.first_air_date && (
                                <span className="text-xs text-ink-500">
                                  {s.first_air_date.substring(0, 4)}
                                </span>
                              )}
                              <Rating value={s.vote_average} />
                            </div>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
