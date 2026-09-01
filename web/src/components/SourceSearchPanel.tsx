import { useState } from "react";
import { api } from "../api";
import type { SourceResult } from "../types";

function formatSize(bytes: number): string {
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + " GB";
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(0) + " MB";
  return (bytes / 1024).toFixed(0) + " KB";
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

interface SourceSearchPanelProps {
  title: string;
  year?: number;
  season?: number;
  episode?: number;
  tmdbId?: number;
  contentType?: string;
}

export function SourceSearchPanel({ title, year, season, episode, tmdbId, contentType }: SourceSearchPanelProps) {
  const [results, setResults] = useState<SourceResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [addingHash, setAddingHash] = useState<string | null>(null);
  const [addedHashes, setAddedHashes] = useState<Set<string>>(new Set());
  const [resolvingHash, setResolvingHash] = useState<string | null>(null);
  const [streamUrls, setStreamUrls] = useState<Record<string, string>>({});

  const handleSearch = async () => {
    setSearching(true);
    setError("");
    setResults(null);
    setAddedHashes(new Set());
    setStreamUrls({});
    try {
      const res = await api.searchSources(title, year, season, episode, tmdbId, contentType);
      setResults(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const handleAddTorrent = async (infoHash: string) => {
    setAddingHash(infoHash);
    try {
      const res = await api.addTorrent(infoHash);
      if (res.success) {
        setAddedHashes(prev => new Set(prev).add(infoHash));
      } else {
        setError(res.detail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add torrent");
    } finally {
      setAddingHash(null);
    }
  };

  const handleResolve = async (infoHash: string, providerKey: string) => {
    setResolvingHash(infoHash);
    setError("");
    try {
      const res = await api.resolveStream(infoHash, providerKey, undefined, season, episode);
      if (res.success && res.stream_url) {
        setStreamUrls(prev => ({ ...prev, [infoHash]: res.stream_url! }));
      } else {
        setError(res.detail || "Failed to get stream URL");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resolve stream");
    } finally {
      setResolvingHash(null);
    }
  };

  const instantResults = results?.filter(r =>
    r.source_type === "cached_torrent" || r.source_type === "direct" || r.source_type === "in_library"
  ) ?? [];
  const uncachedResults = results?.filter(r => r.source_type === "uncached_torrent") ?? [];

  return (
    <div className="mt-8 card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-ink-300">Sources</h3>
        <button
          onClick={handleSearch}
          disabled={searching}
          className="btn-secondary text-xs px-3 py-1.5"
        >
          {searching ? (
            <span className="flex items-center gap-1.5">
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Searching...
            </span>
          ) : (
            "Find sources"
          )}
        </button>
      </div>

      {error && <p className="text-sm text-error-400 mb-3">{error}</p>}

      {results !== null && results.length === 0 && (
        <p className="text-sm text-ink-500">
          No sources found. Make sure a source provider is enabled with valid credentials.
        </p>
      )}

      {results !== null && results.length > 0 && (
        <div className="space-y-4">
          {instantResults.length > 0 && (
            <div>
              <p className="text-xs text-emerald-400 font-medium mb-2">
                {instantResults.length} instant source{instantResults.length !== 1 ? "s" : ""}
              </p>
              <div className="space-y-2">
                {instantResults.map((r, i) => (
                  <SourceRow
                    key={`instant-${i}`}
                    result={r}
                    onResolve={r.info_hash ? () => handleResolve(r.info_hash!, r.provider_key) : undefined}
                    resolving={r.info_hash === resolvingHash}
                    streamUrl={r.stream_url || (r.info_hash ? streamUrls[r.info_hash] : undefined)}
                  />
                ))}
              </div>
            </div>
          )}

          {uncachedResults.length > 0 && (
            <div>
              <p className="text-xs text-ink-500 mb-2">
                {uncachedResults.length} available source{uncachedResults.length !== 1 ? "s" : ""} (not cached)
              </p>
              <div className="space-y-2">
                {uncachedResults.map((r, i) => (
                  <SourceRow
                    key={`uncached-${i}`}
                    result={r}
                    onAdd={r.info_hash ? () => handleAddTorrent(r.info_hash!) : undefined}
                    adding={r.info_hash === addingHash}
                    added={r.info_hash ? addedHashes.has(r.info_hash) : false}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {results === null && !searching && !error && (
        <p className="text-sm text-ink-500">
          Click "Find sources" to search enabled source providers.
        </p>
      )}
    </div>
  );
}

function SourceRow({ result: r, onAdd, adding, added, onResolve, resolving, streamUrl }: {
  result: SourceResult;
  onAdd?: () => void;
  adding?: boolean;
  added?: boolean;
  onResolve?: () => void;
  resolving?: boolean;
  streamUrl?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (streamUrl) {
      navigator.clipboard.writeText(streamUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const hasPreResolvedUrl = !!r.stream_url;
  const resolvedUrl = streamUrl;
  const needsResolve = !hasPreResolvedUrl && onResolve && !resolvedUrl;

  return (
    <div className="flex flex-col gap-2 p-3 rounded-lg bg-ink-900/50 border border-ink-800/50">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-ink-200 truncate" title={r.filename}>
            {r.filename}
          </p>
          <div className="flex flex-wrap items-center gap-2 mt-1.5">
            {r.quality && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-brand-600/20 text-brand-400">
                {r.quality}
              </span>
            )}
            {r.codec && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-ink-800 text-ink-400">
                {r.codec}
              </span>
            )}
            {r.is_season_pack && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-violet-600/20 text-violet-400">
                Season Pack &middot; {r.file_count} episodes
              </span>
            )}
            {r.source_type === "in_library" && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-sky-600/20 text-sky-400">
                In Library
              </span>
            )}
            {r.source_type === "cached_torrent" && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-600/20 text-emerald-400">
                Cached
              </span>
            )}
            {r.source_type === "uncached_torrent" && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-600/20 text-amber-400">
                Uncached
              </span>
            )}
            {r.size_bytes > 0 && (
              <span className="text-[10px] text-ink-500">
                {formatSize(r.size_bytes)}
              </span>
            )}
            {r.duration_seconds != null && r.duration_seconds > 0 && (
              <span className="text-[10px] text-ink-500">
                {formatDuration(r.duration_seconds)}
              </span>
            )}
            {r.seeders != null && r.seeders > 0 && (
              <span className="text-[10px] text-ink-500">
                {r.seeders} seeders
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-ink-800/80 text-ink-400 border border-ink-700/50">
              {r.provider_key}
            </span>
            {r.scraper_source && (
              <span className="text-[10px] text-ink-600">
                found by {r.scraper_source}
              </span>
            )}
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {needsResolve && (
            <button
              onClick={onResolve}
              disabled={resolving}
              className="text-[11px] font-medium px-2.5 py-1.5 rounded transition-colors bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30"
            >
              {resolving ? (
                <span className="flex items-center gap-1">
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Resolving...
                </span>
              ) : (
                "Stream"
              )}
            </button>
          )}
          {onAdd && (
            <button
              onClick={onAdd}
              disabled={adding || added}
              className={`text-[11px] font-medium px-2.5 py-1.5 rounded transition-colors ${
                added
                  ? "bg-emerald-600/20 text-emerald-400 cursor-default"
                  : "bg-brand-600/20 text-brand-400 hover:bg-brand-600/30"
              }`}
            >
              {adding ? (
                <span className="flex items-center gap-1">
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                </span>
              ) : added ? (
                "Added"
              ) : (
                "Add"
              )}
            </button>
          )}
        </div>
      </div>

      {resolvedUrl && (
        <div className="flex items-center gap-3 px-2 py-2 rounded bg-emerald-950/40 border border-emerald-800/30">
          <button
            onClick={handleCopy}
            className="text-[11px] font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            {copied ? "Copied!" : "Copy URL"}
          </button>
          <a
            href={resolvedUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] font-medium text-ink-400 hover:text-ink-200 transition-colors"
          >
            Open in browser
          </a>
        </div>
      )}
    </div>
  );
}
