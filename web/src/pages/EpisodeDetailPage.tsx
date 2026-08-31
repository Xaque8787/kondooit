import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import type { SeasonDetail } from "../types";
import { LoadingSpinner, ErrorState, Rating } from "../components/ui";
import { SourceSearchPanel } from "../components/SourceSearchPanel";

export function EpisodeDetailPage() {
  const { provider, seriesId, season, episode } = useParams<{
    provider: string;
    seriesId: string;
    season: string;
    episode: string;
  }>();
  const [seasonData, setSeasonData] = useState<SeasonDetail | null>(null);
  const [seriesTitle, setSeriesTitle] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

          <SourceSearchPanel
            title={seriesTitle}
            season={ep.season_number}
            episode={ep.episode_number}
            tmdbId={seriesIdNum}
            contentType="series"
          />
        </div>
      </div>
    </div>
  );
}
