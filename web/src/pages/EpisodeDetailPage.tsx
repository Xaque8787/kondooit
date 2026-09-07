import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { SeasonDetail, WatchProgressResponse } from "../types";
import { LoadingSpinner, ErrorState, Rating } from "../components/ui";
import { SourceSearchPanel } from "../components/SourceSearchPanel";

export function EpisodeDetailPage() {
  const { provider, seriesId, season, episode } = useParams<{
    provider: string;
    seriesId: string;
    season: string;
    episode: string;
  }>();
  const navigate = useNavigate();
  const [seasonData, setSeasonData] = useState<SeasonDetail | null>(null);
  const [seriesTitle, setSeriesTitle] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [watchProgress, setWatchProgress] = useState<WatchProgressResponse | null>(null);
  const [watchToggling, setWatchToggling] = useState(false);
  const [autoPlaying, setAutoPlaying] = useState(false);
  const [autoPlayError, setAutoPlayError] = useState("");

  const seasonNum = parseInt(season || "0", 10);
  const episodeNum = parseInt(episode || "0", 10);
  const seriesIdNum = parseInt(seriesId || "0", 10);

  useEffect(() => {
    if (!provider || !seriesId || !season) return;
    setLoading(true);

    Promise.all([
      api.getSeasonDetail(provider, seriesIdNum, seasonNum),
      api.getSeriesDetail(provider, seriesIdNum),
    ])
      .then(([sd, series]) => {
        setSeasonData(sd);
        setSeriesTitle(series.title);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [provider, seriesId, season, seriesIdNum, seasonNum]);

  useEffect(() => {
    if (!provider || !seriesId || !season || !episode) return;
    const ep = seasonData?.episodes.find((e) => e.episode_number === episodeNum);
    if (!ep) return;
    api
      .getWatchProgress(provider, "episode", ep.external_id)
      .then(setWatchProgress)
      .catch(() => setWatchProgress(null));
  }, [provider, seriesId, season, episode, seasonData, episodeNum]);

  const handleAutoPlay = useCallback(async (epData: { season_number: number; episode_number: number; external_id: number }) => {
    if (!seriesTitle || !provider || autoPlaying) return;
    setAutoPlaying(true);
    setAutoPlayError("");
    try {
      const res = await api.autoPlay(seriesTitle, undefined, epData.season_number, epData.episode_number, seriesIdNum, "episode");
      if (res.success && res.stream_id) {
        const p = new URLSearchParams({
          stream: res.stream_id,
          title: seriesTitle,
          type: "episode",
        });
        if (provider) p.set("provider", provider);
        if (epData.external_id) p.set("eid", String(epData.external_id));
        p.set("series_eid", String(seriesIdNum));
        p.set("season", String(epData.season_number));
        p.set("episode", String(epData.episode_number));
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
  }, [seriesTitle, provider, autoPlaying, seriesIdNum, navigate]);

  if (loading) return <LoadingSpinner label="Loading episode" />;
  if (error) return <ErrorState message={error} />;
  if (!seasonData) return <ErrorState message="Season not found" />;

  const ep = seasonData.episodes.find((e) => e.episode_number === episodeNum);
  if (!ep) return <ErrorState message="Episode not found" />;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link
        to={`/series/${provider}/${seriesId}`}
        className="text-sm text-ink-400 hover:text-ink-100 mb-6 inline-block transition-colors"
      >
        &larr; Back to series
      </Link>

      <div className="flex flex-col md:flex-row gap-6">
        <div className="md:w-80 shrink-0">
          <div className="card aspect-video overflow-hidden">
            {ep.still_path ? (
              <img
                src={ep.still_path}
                alt={ep.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full bg-ink-800 flex items-center justify-center text-ink-600">
                No image available
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm text-ink-500 mb-2">
            <span>Season {ep.season_number}</span>
            <span className="text-ink-700">&middot;</span>
            <span>Episode {ep.episode_number}</span>
          </div>

          <h1 className="text-2xl font-bold text-ink-100 mb-4">
            {ep.name || `Episode ${ep.episode_number}`}
          </h1>

          <div className="flex flex-wrap items-center gap-4 mb-6">
            {ep.air_date && (
              <div className="flex items-center gap-1.5 text-sm text-ink-400">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {ep.air_date}
              </div>
            )}
            {ep.runtime_minutes && (
              <div className="flex items-center gap-1.5 text-sm text-ink-400">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {ep.runtime_minutes} min
              </div>
            )}
            <Rating value={ep.vote_average} />
          </div>

          <p className="text-ink-300 leading-relaxed">
            {ep.overview || "No overview available for this episode."}
          </p>

          {autoPlayError && (
            <p className="text-sm text-red-400 mt-3">{autoPlayError}</p>
          )}

          <div className="flex items-center gap-3 mt-4 mb-2">
            <button
              onClick={() => handleAutoPlay({ season_number: ep.season_number, episode_number: ep.episode_number, external_id: ep.external_id })}
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
              onClick={async () => {
                if (!provider || watchToggling) return;
                setWatchToggling(true);
                try {
                  if (watchProgress?.watched) {
                    const result = await api.markUnwatched({ provider_key: provider, content_type: "episode", external_id: ep.external_id });
                    setWatchProgress(result);
                  } else {
                    const result = await api.markWatched({
                      provider_key: provider, content_type: "episode", external_id: ep.external_id,
                      series_external_id: seriesIdNum, season_number: ep.season_number, episode_number: ep.episode_number,
                    });
                    setWatchProgress(result);
                  }
                } catch { /* retry */ }
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

          <SourceSearchPanel
            title={seriesTitle}
            season={ep.season_number}
            episode={ep.episode_number}
            tmdbId={seriesIdNum}
            contentType="episode"
            providerKey={provider}
            externalId={ep.external_id}
            seriesExternalId={seriesIdNum}
          />
        </div>
      </div>
    </div>
  );
}
