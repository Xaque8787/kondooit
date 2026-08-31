import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { DiscoveredMovie, UserContentState, MovieDetail } from "../types";
import { Poster, Rating, LoadingSpinner, EmptyState, ErrorState } from "../components/ui";

type Tab = "favorites" | "following" | "search";

interface FavoriteMovieItem {
  state: UserContentState;
  detail: MovieDetail | null;
  loading: boolean;
}

export function MoviesPage() {
  const [tab, setTab] = useState<Tab>("favorites");
  const [favorites, setFavorites] = useState<FavoriteMovieItem[]>([]);
  const [following, setFollowing] = useState<FavoriteMovieItem[]>([]);
  const [searchResults, setSearchResults] = useState<DiscoveredMovie[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    loadUserState();
  }, []);

  async function loadUserState() {
    setLoading(true);
    setError("");
    try {
      const [favs, follows] = await Promise.all([
        api.listFavorites("movie"),
        api.listFollowing("movie"),
      ]);
      setFavorites(favs.map((s) => ({ state: s, detail: null, loading: true })));
      setFollowing(follows.map((s) => ({ state: s, detail: null, loading: true })));

      // Fetch details for favorites
      favs.forEach((s, idx) => {
        api.getMovieDetail(s.provider_key, s.external_id)
          .then((d) => {
            setFavorites((prev) => prev.map((item, i) => i === idx ? { ...item, detail: d, loading: false } : item));
          })
          .catch(() => {
            setFavorites((prev) => prev.map((item, i) => i === idx ? { ...item, loading: false } : item));
          });
      });

      // Fetch details for following
      follows.forEach((s, idx) => {
        api.getMovieDetail(s.provider_key, s.external_id)
          .then((d) => {
            setFollowing((prev) => prev.map((item, i) => i === idx ? { ...item, detail: d, loading: false } : item));
          })
          .catch(() => {
            setFollowing((prev) => prev.map((item, i) => i === idx ? { ...item, loading: false } : item));
          });
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!search.trim()) return;
    setTab("search");
    setSearching(true);
    setError("");
    try {
      const results = await api.searchDiscoveryMovies(search);
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "favorites", label: "Favorites" },
    { key: "following", label: "Following" },
    { key: "search", label: "Search" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-ink-100">Movies</h1>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search movies..."
            className="input w-64"
          />
          <button type="submit" disabled={searching} className="btn-primary">
            Search
          </button>
        </form>
      </div>

      <div className="flex items-center gap-1 mb-8 border-b border-ink-800">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-ink-400 hover:text-ink-200"
            }`}
          >
            {t.label}
            {t.key === "favorites" && favorites.length > 0 && (
              <span className="ml-1.5 text-xs bg-ink-800 px-1.5 py-0.5 rounded-full">{favorites.length}</span>
            )}
            {t.key === "following" && following.length > 0 && (
              <span className="ml-1.5 text-xs bg-ink-800 px-1.5 py-0.5 rounded-full">{following.length}</span>
            )}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} />}

      {tab === "favorites" && (
        <>
          {loading && <LoadingSpinner label="Loading favorites" />}
          {!loading && favorites.length === 0 && (
            <EmptyState
              title="No favorite movies"
              description="Browse movies and mark them as favorites to see them here."
              action={<Link to="/" className="btn-primary">Discover movies</Link>}
            />
          )}
          {!loading && favorites.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {favorites.map((item) => (
                <Link
                  key={`${item.state.provider_key}:${item.state.external_id}`}
                  to={`/movie/${item.state.provider_key}/${item.state.external_id}`}
                  className="group"
                >
                  <div className="card aspect-[2/3] overflow-hidden">
                    <Poster
                      path={item.detail?.poster_path ?? null}
                      alt={item.detail?.title ?? "Loading..."}
                      className="w-full h-full group-hover:scale-105 transition-transform duration-300"
                    />
                  </div>
                  <div className="mt-2">
                    <h3 className="text-sm font-medium text-ink-200 truncate group-hover:text-brand-400 transition-colors">
                      {item.detail?.title ?? "Loading..."}
                    </h3>
                    {item.detail?.release_date && (
                      <span className="text-xs text-ink-500">
                        {item.detail.release_date.substring(0, 4)}
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "following" && (
        <>
          {loading && <LoadingSpinner label="Loading followed movies" />}
          {!loading && following.length === 0 && (
            <EmptyState
              title="Not following any movies"
              description="Follow movies to track them and see them here."
              action={<Link to="/" className="btn-primary">Discover movies</Link>}
            />
          )}
          {!loading && following.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {following.map((item) => (
                <Link
                  key={`${item.state.provider_key}:${item.state.external_id}`}
                  to={`/movie/${item.state.provider_key}/${item.state.external_id}`}
                  className="group"
                >
                  <div className="card aspect-[2/3] overflow-hidden">
                    <Poster
                      path={item.detail?.poster_path ?? null}
                      alt={item.detail?.title ?? "Loading..."}
                      className="w-full h-full group-hover:scale-105 transition-transform duration-300"
                    />
                  </div>
                  <div className="mt-2">
                    <h3 className="text-sm font-medium text-ink-200 truncate group-hover:text-brand-400 transition-colors">
                      {item.detail?.title ?? "Loading..."}
                    </h3>
                    {item.detail?.release_date && (
                      <span className="text-xs text-ink-500">
                        {item.detail.release_date.substring(0, 4)}
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "search" && (
        <>
          {searching && <LoadingSpinner label="Searching" />}
          {!searching && searchResults.length === 0 && (
            <EmptyState
              title="No results"
              description="Try a different search term to find movies."
            />
          )}
          {!searching && searchResults.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {searchResults.map((m, idx) => (
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
        </>
      )}
    </div>
  );
}
