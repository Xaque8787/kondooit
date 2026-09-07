import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { MovieDetail, UserContentState, WatchProgressResponse } from "../types";
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
  const navigate = useNavigate();
  const [movie, setMovie] = useState<MovieDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contentState, setContentState] = useState<UserContentState | null>(null);
  const [watchProgress, setWatchProgress] = useState<WatchProgressResponse | null>(null);
  const [toggling, setToggling] = useState(false);
  const [watchToggling, setWatchToggling] = useState(false);
  const [autoPlaying, setAutoPlaying] = useState(false);
  const [autoPlayError, setAutoPlayError] = useState("");

  const handleAutoPlay = useCallback(async () => {
    if (!movie || !provider || !id || autoPlaying) return;
    setAutoPlaying(true);
    setAutoPlayError("");
    try {
      const year = movie.release_date ? parseInt(movie.release_date.substring(0, 4), 10) : undefined;
      const res = await api.autoPlay(movie.title, year, undefined, undefined, movie.external_id, "movie");
      if (res.success && res.stream_id) {
        const p = new URLSearchParams({
          stream: res.stream_id,
          title: movie.title,
          type: "movie",
        });
        if (provider) p.set("provider", provider);
        if (movie.external_id) p.set("eid", String(movie.external_id));
        if (res.auto_play_session) p.set("aps", res.auto_play_session);
        navigate(`/player?${p.toString()}`);
      } else {
        setAutoPlayError(res.detail || "No playable source found");
      }
    } catch (err) {
      setAutoPlayError(err instanceof Error ? err.message : "Auto-play failed");
    } finally {
      setAutoPlaying(false);
    }
  }, [movie, provider, id, autoPlaying, navigate]);

  useEffect(() => {
    if (!provider || !id) return;
    const eid = parseInt(id, 10);
    setLoading(true);
    api
      .getMovieDetail(provider, eid)
      .then(setMovie)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

    api
      .getContentState(provider, "movie", eid)
      .then(setContentState)
      .catch(() => setContentState(null));

    api
      .getWatchProgress(provider, "movie", eid)
      .then(setWatchProgress)
      .catch(() => setWatchProgress(null));
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

            {autoPlayError && (
              <p className="text-sm text-red-400 mb-2">{autoPlayError}</p>
            )}

            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={handleAutoPlay}
                disabled={autoPlaying}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-brand-600 text-white hover:bg-brand-500 disabled:opacity-60"
              >
                {autoPlaying ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Finding best source...
                  </>
                ) : (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                      <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                    </svg>
                    Play
                  </>
                )}
              </button>
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
              <button
                onClick={async () => {
                  if (!provider || !id || watchToggling) return;
                  setWatchToggling(true);
                  try {
                    const eid = parseInt(id, 10);
                    if (watchProgress?.watched) {
                      const result = await api.markUnwatched({ provider_key: provider, content_type: "movie", external_id: eid });
                      setWatchProgress(result);
                    } else {
                      const result = await api.markWatched({ provider_key: provider, content_type: "movie", external_id: eid });
                      setWatchProgress(result);
                    }
                  } catch { /* retry on next click */ }
                  finally { setWatchToggling(false); }
                }}
                disabled={watchToggling}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  watchProgress?.watched
                    ? "bg-emerald-600/20 text-emerald-400 border border-emerald-600/40"
                    : "bg-ink-800 text-ink-300 border border-ink-700 hover:bg-ink-700"
                }`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                </svg>
                {watchProgress?.watched ? "Watched" : "Mark Watched"}
              </button>
            </div>

            {/* Progress bar */}
            {watchProgress && watchProgress.position_seconds > 0 && !watchProgress.watched && (
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-ink-400">
                    {Math.floor(watchProgress.position_seconds / 60)}m of{" "}
                    {Math.floor(watchProgress.duration_seconds / 60)}m watched
                  </span>
                  <span className="text-xs text-ink-500">({watchProgress.progress_percent}%)</span>
                </div>
                <div className="w-full max-w-xs h-1.5 bg-ink-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-500 rounded-full transition-all"
                    style={{ width: `${watchProgress.progress_percent}%` }}
                  />
                </div>
              </div>
            )}

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
              providerKey={provider}
              externalId={movie.external_id}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
