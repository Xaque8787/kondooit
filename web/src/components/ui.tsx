import type { ReactNode } from "react";

export function Poster({
  path,
  alt,
  className = "",
}: {
  path: string | null;
  alt: string;
  className?: string;
}) {
  const TMDB_IMG = "https://image.tmdb.org/t/p/w500";
  const fallback = "/poster-placeholder.svg";

  return (
    <img
      src={path ? `${TMDB_IMG}${path}` : fallback}
      alt={alt}
      className={`object-cover ${className}`}
      loading="lazy"
      onError={(e) => {
        (e.target as HTMLImageElement).src = fallback;
      }}
    />
  );
}

export function Backdrop({
  path,
  alt,
  className = "",
}: {
  path: string | null;
  alt: string;
  className?: string;
}) {
  const TMDB_IMG = "https://image.tmdb.org/t/p/w1280";
  const fallback = "/backdrop-placeholder.svg";

  return (
    <img
      src={path ? `${TMDB_IMG}${path}` : fallback}
      alt={alt}
      className={`object-cover ${className}`}
      loading="lazy"
      onError={(e) => {
        (e.target as HTMLImageElement).src = fallback;
      }}
    />
  );
}

export function Rating({ value }: { value: number | null }) {
  if (value == null) return null;
  return (
    <span className="badge bg-accent-500/20 text-accent-400">
      ★ {value.toFixed(1)}
    </span>
  );
}

export function GenreBadges({ genres }: { genres: { name: string }[] }) {
  if (!genres.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {genres.map((g) => (
        <span key={g.name} className="badge bg-ink-800 text-ink-300">
          {g.name}
        </span>
      ))}
    </div>
  );
}

export function LoadingSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
        <span className="text-sm text-ink-400">{label}...</span>
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <h3 className="text-lg font-medium text-ink-200 mb-2">{title}</h3>
      <p className="text-sm text-ink-500 max-w-md mb-6">{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-12 h-12 rounded-full bg-error-500/20 flex items-center justify-center mb-4">
        <span className="text-error-400 text-xl">!</span>
      </div>
      <p className="text-sm text-ink-400">{message}</p>
    </div>
  );
}
