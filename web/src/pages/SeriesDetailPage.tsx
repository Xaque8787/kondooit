import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import type { SeriesDetail, SeasonDetail, UserContentState } from "../types";
import {
  Backdrop,
  Poster,
  Rating,
  GenreBadges,
  LoadingSpinner,
  ErrorState,
} from "../components/ui";
import { SourceSearchPanel } from "../components/SourceSearchPanel";

export function SeriesDetailPage() {
  const { provider, id } = useParams<{ provider: string; id: string }>();
  const [series, setSeries] = useState<SeriesDetail | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [seasonDetail, setSeasonDetail] = useState<SeasonDetail | null>(null);
  const [loadingEpisodes, setLoadingEpisodes] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [contentState, setContentState] = useState<UserContentState | null>(null);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (!provider || !id) return;
    setLoading(true);
    api
      .getSeriesDetail(provider, parseInt(id, 10))
      .then((s) => {
        setSeries(s);
        if (s.seasons.length > 0) setSelectedSeason(s.seasons[0].season_number);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

    api
      .getContentState(provider, "series", parseInt(id, 10))
      .then(setContentState)
      .catch(() => setContentState(null));
  }, [provider, id]);

  useEffect(() => {
    if (!provider || !id || selectedSeason === null) return;
    setLoadingEpisodes(true);
    setSeasonDetail(null);
    api
      .getSeasonDetail(provider, parseInt(id, 10), selectedSeason)
      .then(setSeasonDetail)
      .catch(() => setSeasonDetail(null))
      .finally(() => setLoadingEpisodes(false));
  }, [provider, id, selectedSeason]);

  const handleToggleFavorite = async () => {
    if (!provider || !id || toggling) return;
    setToggling(true);
    try {
      const result = await api.toggleFavorite(provider, "series", parseInt(id, 10));
      setContentState(result);
    } catch {
      // silently fail
    } finally {
      setToggling(false);
    }
  };

  const handleToggleFollowing = async () => {
    if (!provider || !id || toggling) return;
    setToggling(true);
    try {
      const result = await api.toggleFollowing(provider, "series", parseInt(id, 10));
      setContentState(result);
    } catch {
      // silently fail
    } finally {
      setToggling(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading series" />;
  if (error) return <ErrorState message={error} />;
  if (!series) return <ErrorState message="Series not found" />;

  const episodes = seasonDetail?.episodes ?? [];

  return (
    <div>
      <div className="relative h-[40vh] min-h-[300px] overflow-hidden">
        <Backdrop
          path={series.backdrop_path}
          alt={series.title}
          className="w-full h-full"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/60 to-transparent" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-32 relative">
        <Link
          to="/series"
          className="text-sm text-ink-400 hover:text-ink-100 mb-4 inline-block"
        >
          &larr; Back to TV shows
        </Link>
        <div className="flex flex-col sm:flex-row gap-6">
          <div className="w-40 sm:w-48 shrink-0">
            <div className="card aspect-[2/3] overflow-hidden">
              <Poster
                path={series.poster_path}
                alt={series.title}
                className="w-full h-full"
              />
            </div>
          </div>
          <div className="flex-1 pt-2">
            <h1 className="text-3xl font-bold text-ink-100 mb-3">
              {series.title}
            </h1>
            <div className="flex flex-wrap items-center gap-3 mb-4">
              {series.first_air_date && (
                <span className="text-sm text-ink-400">
                  {series.first_air_date.substring(0, 4)}
                </span>
              )}
              {series.status && (
                <span className="text-sm text-ink-400">{series.status}</span>
              )}
              <Rating value={series.vote_average} />
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
              genres={series.genres.map((g) => ({
                id: g.id.toString(),
                name: g.name,
                tmdb_id: null,
                tvdb_id: null,
              }))}
            />
            <p className="mt-4 text-ink-300 leading-relaxed max-w-3xl">
              {series.overview || "No overview available."}
            </p>

            <SourceSearchPanel
              title={series.title}
              year={series.first_air_date ? parseInt(series.first_air_date.substring(0, 4), 10) : undefined}
            />
          </div>
        </div>

        {series.seasons.length > 0 && (
          <div className="mt-10">
            <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
              {series.seasons.map((s) => (
                <button
                  key={s.season_number}
                  onClick={() => setSelectedSeason(s.season_number)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    selectedSeason === s.season_number
                      ? "bg-brand-600 text-white"
                      : "bg-ink-800 text-ink-300 hover:bg-ink-700"
                  }`}
                >
                  {s.name || `Season ${s.season_number}`}
                </button>
              ))}
            </div>

            {loadingEpisodes && (
              <div className="flex items-center gap-2 text-ink-400 text-sm py-4">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading episodes...
              </div>
            )}

            {!loadingEpisodes && episodes.length > 0 && (
              <div className="space-y-3">
                {episodes.map((ep) => (
                  <Link
                    key={ep.external_id}
                    to={`/series/${provider}/${id}/season/${ep.season_number}/episode/${ep.episode_number}`}
                    className="card p-4 flex gap-4 items-start hover:border-ink-700 transition-colors block"
                  >
                    <div className="w-24 sm:w-32 shrink-0">
                      <div className="card aspect-video overflow-hidden">
                        {ep.still_path ? (
                          <img
                            src={ep.still_path}
                            alt={ep.name}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <div className="w-full h-full bg-ink-800 flex items-center justify-center text-ink-600 text-xs">
                            No image
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-ink-500">
                          E{ep.episode_number}
                        </span>
                        <h4 className="text-sm font-medium text-ink-200 truncate">
                          {ep.name || `Episode ${ep.episode_number}`}
                        </h4>
                      </div>
                      <p className="text-xs text-ink-500 line-clamp-2">
                        {ep.overview || "No overview available."}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5">
                        {ep.air_date && (
                          <span className="text-xs text-ink-600">
                            {ep.air_date}
                          </span>
                        )}
                        {ep.runtime_minutes && (
                          <span className="text-xs text-ink-600">
                            {ep.runtime_minutes} min
                          </span>
                        )}
                        <Rating value={ep.vote_average} />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}

            {!loadingEpisodes && episodes.length === 0 && (
              <p className="text-sm text-ink-500">No episodes found for this season.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
