import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import type { MovieDetail, UserContentState } from "../types";
import {
  Backdrop,
  Poster,
  Rating,
  GenreBadges,
  LoadingSpinner,
  ErrorState,
} from "../components/ui";
import { SourceSearchPanel } from "../components/SourceSearchPanel";

export function MovieDetailPage() {
  const { provider, id } = useParams<{ provider: string; id: string }>();
  const [movie, setMovie] = useState<MovieDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contentState, setContentState] = useState<UserContentState | null>(null);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (!provider || !id) return;
    setLoading(true);
    api
      .getMovieDetail(provider, parseInt(id, 10))
      .then(setMovie)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

    api
      .getContentState(provider, "movie", parseInt(id, 10))
      .then(setContentState)
      .catch(() => setContentState(null));
  }, [provider, id]);

  const handleToggleFavorite = async () => {
    if (!provider || !id || toggling) return;
    setToggling(true);
    try {
      const result = await api.toggleFavorite(provider, "movie", parseInt(id, 10));
      setContentState(result);
    } catch {
      // silently fail — user can retry
    } finally {
      setToggling(false);
    }
  };

  const handleToggleFollowing = async () => {
    if (!provider || !id || toggling) return;
    setToggling(true);
    try {
      const result = await api.toggleFollowing(provider, "movie", parseInt(id, 10));
      setContentState(result);
    } catch {
      // silently fail — user can retry
    } finally {
      setToggling(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading movie" />;
  if (error) return <ErrorState message={error} />;
  if (!movie) return <ErrorState message="Movie not found" />;

  return (
    <div>
      <div className="relative h-[40vh] min-h-[300px] overflow-hidden">
        <Backdrop
          path={movie.backdrop_path}
          alt={movie.title}
          className="w-full h-full"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/60 to-transparent" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-32 relative">
        <Link
          to="/movies"
          className="text-sm text-ink-400 hover:text-ink-100 mb-4 inline-block"
        >
          &larr; Back to movies
        </Link>
        <div className="flex flex-col sm:flex-row gap-6">
          <div className="w-40 sm:w-48 shrink-0">
            <div className="card aspect-[2/3] overflow-hidden">
              <Poster
                path={movie.poster_path}
                alt={movie.title}
                className="w-full h-full"
              />
            </div>
          </div>
          <div className="flex-1 pt-2">
            <h1 className="text-3xl font-bold text-ink-100 mb-3">{movie.title}</h1>
            <div className="flex flex-wrap items-center gap-3 mb-4">
              {movie.release_date && (
                <span className="text-sm text-ink-400">
                  {movie.release_date.substring(0, 4)}
                </span>
              )}
              {movie.runtime_minutes && (
                <span className="text-sm text-ink-400">
                  {movie.runtime_minutes} min
                </span>
              )}
              <Rating value={movie.vote_average} />
            </div>

            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={handleToggleFavorite}
                disabled={toggling}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  contentState?.is_favorite
                    ? "bg-amber-600/20 text-amber-400 border border-amber-600/40"
                    : "bg-ink-800 text-ink-300 border border-ink-700 hover:bg-ink-700"
                }`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" />
                </svg>
                {contentState?.is_favorite ? "Favorited" : "Favorite"}
              </button>
              <button
                onClick={handleToggleFollowing}
                disabled={toggling}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  contentState?.is_following
                    ? "bg-brand-600/20 text-brand-400 border border-brand-600/40"
                    : "bg-ink-800 text-ink-300 border border-ink-700 hover:bg-ink-700"
                }`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path d="M10 12.5a.75.75 0 01-.75-.75V2.75a.75.75 0 011.5 0v9a.75.75 0 01-.75.75z" />
                  <path d="M10 12.5a.75.75 0 01-.53-.22l-3.25-3.25a.75.75 0 011.06-1.06L10 10.69l2.72-2.72a.75.75 0 111.06 1.06l-3.25 3.25a.75.75 0 01-.53.22z" />
                  <path d="M3.5 14.25a.75.75 0 01.75.75v1.5a.25.25 0 00.25.25h11a.25.25 0 00.25-.25V15a.75.75 0 011.5 0v1.5A1.75 1.75 0 0115.5 18.25h-11A1.75 1.75 0 012.75 16.5V15a.75.75 0 01.75-.75z" />
                </svg>
                {contentState?.is_following ? "Following" : "Follow"}
              </button>
            </div>

            <GenreBadges
              genres={movie.genres.map((g) => ({
                id: g.id.toString(),
                name: g.name,
                tmdb_id: null,
                tvdb_id: null,
              }))}
            />
            <p className="mt-4 text-ink-300 leading-relaxed max-w-3xl">
              {movie.overview || "No overview available."}
            </p>

            <SourceSearchPanel
              title={movie.title}
              year={movie.release_date ? parseInt(movie.release_date.substring(0, 4), 10) : undefined}
              tmdbId={movie.external_id}
              contentType="movie"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
