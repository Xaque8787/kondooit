import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import type { DiscoverySection } from "../types";
import { Poster, Rating, LoadingSpinner, ErrorState, EmptyState } from "../components/ui";

export function DiscoverySectionPage() {
  const { sectionKey } = useParams<{ sectionKey: string }>();
  const [section, setSection] = useState<DiscoverySection | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sectionKey) return;
    setLoading(true);
    api
      .getDiscoverySection(sectionKey, page)
      .then(setSection)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sectionKey, page]);

  if (loading) return <LoadingSpinner label="Loading content" />;
  if (error) return <ErrorState message={error} />;
  if (!section) return <EmptyState title="Section not found" description="This discovery section is not available." />;

  const hasMovies = section.movies.length > 0;
  const hasSeries = section.series.length > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link to="/" className="text-sm text-ink-400 hover:text-ink-100 mb-4 inline-block">
        &larr; Back to home
      </Link>
      <h1 className="text-3xl font-bold text-ink-100 mb-8">{section.title}</h1>

      {hasMovies && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-8">
          {section.movies.map((m, idx) => (
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
                    <span className="text-xs text-ink-500">{m.release_date.substring(0, 4)}</span>
                  )}
                  <Rating value={m.vote_average} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {hasSeries && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-8">
          {section.series.map((s, idx) => (
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
                    <span className="text-xs text-ink-500">{s.first_air_date.substring(0, 4)}</span>
                  )}
                  <Rating value={s.vote_average} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="flex items-center justify-center gap-4 mt-8">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-ink-800 text-ink-300 hover:bg-ink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Previous
        </button>
        <span className="text-sm text-ink-400">Page {page}</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={!hasMovies && !hasSeries}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-ink-800 text-ink-300 hover:bg-ink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
}
