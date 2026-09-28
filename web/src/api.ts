import type {
  BootstrapAdminResponse,
  Episode,
  Genre,
  LoginResponse,
  SourceResult,
  Movie,
  ProviderConfig,
  ProviderInfo,
  Season,
  SeasonDetail,
  Series,
  SourceProviderConfig,
  SourceProviderInfo,
  TestConnectionResponse,
  User,
  UserContentState,
  DiscoveredMovie,
  DiscoveredSeries,
  DiscoveryGenre,
  DiscoverySection,
  MovieDetail,
  SeriesDetail,
  ProviderCapabilities,
  WatchProgressResponse,
} from "./types";

const API_BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("kondooit_token");
}

function getProfileId(): string | null {
  try {
    const stored = localStorage.getItem("kondooit_profile");
    if (stored) {
      const parsed = JSON.parse(stored);
      return parsed?.id ?? null;
    }
  } catch { /* ignore */ }
  return null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const profileId = getProfileId();
  if (profileId) {
    headers["X-Profile-Id"] = profileId;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Health
  health: () => request<{ status: string }>("/health"),

  // Auth
  login: (username: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  bootstrap: (username: string, email: string, password: string) =>
    request<BootstrapAdminResponse>("/auth/bootstrap", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    }),

  me: () => request<User>("/auth/me"),

  // Catalog (legacy — will be removed once discovery replaces it)
  listMovies: (limit = 20, offset = 0) =>
    request<Movie[]>(`/catalog/movies?limit=${limit}&offset=${offset}`),

  searchMovies: (q: string) =>
    request<Movie[]>(`/catalog/movies/search?q=${encodeURIComponent(q)}`),

  getMovie: (id: string) => request<Movie>(`/catalog/movies/${id}`),

  listSeries: (limit = 20, offset = 0) =>
    request<Series[]>(`/catalog/series?limit=${limit}&offset=${offset}`),

  searchSeries: (q: string) =>
    request<Series[]>(`/catalog/series/search?q=${encodeURIComponent(q)}`),

  getSeries: (id: string) => request<Series>(`/catalog/series/${id}`),

  listSeasons: (seriesId: string) =>
    request<Season[]>(`/catalog/series/${seriesId}/seasons`),

  listEpisodes: (seasonId: string) =>
    request<Episode[]>(`/catalog/seasons/${seasonId}/episodes`),

  listGenres: () => request<Genre[]>("/catalog/genres"),

  // Providers
  listProviders: () => request<ProviderInfo[]>("/providers/"),

  getProviderConfig: (key: string) =>
    request<ProviderConfig>(`/providers/${key}`),

  saveProviderConfig: (key: string, apiKey: string, status: string, priority: number = 100) =>
    request<ProviderConfig>(`/providers/${key}`, {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey, status, priority }),
    }),

  deleteProviderConfig: (key: string) =>
    request<{ deleted: boolean }>(`/providers/${key}`, { method: "DELETE" }),

  testProvider: (key: string) =>
    request<TestConnectionResponse>(`/providers/${key}/test`, {
      method: "POST",
    }),

  // Discovery
  getLandingPage: () =>
    request<DiscoverySection[]>("/discovery/landing"),

  getDiscoverySection: (sectionKey: string, page: number = 1) =>
    request<DiscoverySection>(`/discovery/section/${sectionKey}?page=${page}`),

  searchAll: (q: string) =>
    request<(DiscoveredMovie | DiscoveredSeries)[]>(`/discovery/search?q=${encodeURIComponent(q)}`),

  searchDiscoveryMovies: (q: string) =>
    request<DiscoveredMovie[]>(`/discovery/search/movies?q=${encodeURIComponent(q)}`),

  searchDiscoverySeries: (q: string) =>
    request<DiscoveredSeries[]>(`/discovery/search/series?q=${encodeURIComponent(q)}`),

  getDiscoveryGenres: (contentType?: string) =>
    request<DiscoveryGenre[]>(`/discovery/genres${contentType ? `?content_type=${contentType}` : ""}`),

  discoverByGenre: (genreIds: number[], contentType: string = "all", page: number = 1) =>
    request<(DiscoveredMovie | DiscoveredSeries)[]>(
      `/discovery/discover?genre_ids=${genreIds.join(",")}&content_type=${contentType}&page=${page}`
    ),

  getMovieDetail: (providerKey: string, externalId: number) =>
    request<MovieDetail>(`/discovery/movie/${providerKey}/${externalId}`),

  getSeriesDetail: (providerKey: string, externalId: number) =>
    request<SeriesDetail>(`/discovery/series/${providerKey}/${externalId}`),

  getSeasonDetail: (providerKey: string, seriesId: number, seasonNumber: number) =>
    request<SeasonDetail>(`/discovery/season/${providerKey}/${seriesId}/${seasonNumber}`),

  getProviderCapabilities: () =>
    request<ProviderCapabilities[]>("/discovery/capabilities"),

  // User State (favorites/following)
  toggleFavorite: (providerKey: string, contentType: string, externalId: number) =>
    request<UserContentState>("/user-state/favorite", {
      method: "POST",
      body: JSON.stringify({ provider_key: providerKey, content_type: contentType, external_id: externalId }),
    }),

  toggleFollowing: (providerKey: string, contentType: string, externalId: number) =>
    request<UserContentState>("/user-state/following", {
      method: "POST",
      body: JSON.stringify({ provider_key: providerKey, content_type: contentType, external_id: externalId }),
    }),

  getContentState: (providerKey: string, contentType: string, externalId: number) =>
    request<UserContentState>(`/user-state/state/${providerKey}/${contentType}/${externalId}`),

  listFavorites: (contentType?: string) =>
    request<UserContentState[]>(`/user-state/favorites${contentType ? `?content_type=${contentType}` : ""}`),

  listFollowing: (contentType?: string) =>
    request<UserContentState[]>(`/user-state/following${contentType ? `?content_type=${contentType}` : ""}`),

  // Source providers
  listSourceProviders: () =>
    request<SourceProviderInfo[]>("/source-providers/"),

  getSourceProviderConfig: (key: string) =>
    request<SourceProviderConfig>(`/source-providers/${key}`),

  saveSourceProviderConfig: (key: string, credentials: Record<string, string>, status: string, priority: number) =>
    request<SourceProviderConfig>(`/source-providers/${key}`, {
      method: "PUT",
      body: JSON.stringify({ credentials, status, priority }),
    }),

  deleteSourceProviderConfig: (key: string) =>
    request<void>(`/source-providers/${key}`, { method: "DELETE" }),

  testSourceProvider: (key: string) =>
    request<TestConnectionResponse>(`/source-providers/${key}/test`, { method: "POST" }),

  searchSources: (title: string, year?: number, season?: number, episode?: number, tmdb_id?: number, content_type?: string) =>
    request<SourceResult[]>("/source-providers/search", {
      method: "POST",
      body: JSON.stringify({
        title,
        year: year ?? null,
        season: season ?? null,
        episode: episode ?? null,
        tmdb_id: tmdb_id ?? null,
        content_type: content_type ?? "movie",
      }),
    }),

  autoPlay: (title: string, year?: number, season?: number, episode?: number, tmdb_id?: number, content_type?: string) =>
    request<{ success: boolean; detail: string; stream_id: string | null; source: SourceResult | null; auto_play_session: string | null }>("/source-providers/auto-play", {
      method: "POST",
      body: JSON.stringify({
        title,
        year: year ?? null,
        season: season ?? null,
        episode: episode ?? null,
        tmdb_id: tmdb_id ?? null,
        content_type: content_type ?? "movie",
      }),
    }),

  autoPlayNext: (autoPlaySession: string, failedStreamId: string) =>
    request<{ success: boolean; detail: string; stream_id: string | null; source: SourceResult | null; auto_play_session: string | null }>("/source-providers/auto-play/next", {
      method: "POST",
      body: JSON.stringify({ auto_play_session: autoPlaySession, failed_stream_id: failedStreamId }),
    }),

  addTorrent: (info_hash: string, provider_key: string = "torbox") =>
    request<{ success: boolean; detail: string }>("/source-providers/add-torrent", {
      method: "POST",
      body: JSON.stringify({ info_hash, provider_key }),
    }),

  resolveStream: (info_hash: string, provider_key: string = "torbox", file_index?: number, season?: number, episode?: number) =>
    request<{ success: boolean; detail: string; stream_id: string | null }>("/source-providers/resolve", {
      method: "POST",
      body: JSON.stringify({ info_hash, provider_key, file_index: file_index ?? null, season: season ?? null, episode: episode ?? null }),
    }),

  // Scraper modules
  listScraperModules: () =>
    request<import("./types").ScraperModule[]>("/source-providers/scrapers"),

  installScraperModule: (sourcePath: string) =>
    request<import("./types").ModuleInstallResponse>("/source-providers/scrapers/install", {
      method: "POST",
      body: JSON.stringify({ source_path: sourcePath }),
    }),

  uninstallScraperModule: (moduleId: string) =>
    request<void>(`/source-providers/scrapers/${moduleId}`, { method: "DELETE" }),

  toggleScraper: (key: string, enabled: boolean, config?: Record<string, string> | null) =>
    request<import("./types").ScraperInfo>(`/source-providers/scrapers/${key}`, {
      method: "PUT",
      body: JSON.stringify({ enabled, config: config ?? null }),
    }),

  // Profiles
  listProfiles: () =>
    request<import("./types").Profile[]>("/profiles/"),

  createProfile: (data: {
    display_name: string;
    avatar_color?: string;
  }) =>
    request<import("./types").Profile>("/profiles/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProfile: (profileId: string) =>
    request<import("./types").Profile>(`/profiles/${profileId}`),

  updateProfile: (profileId: string, data: {
    display_name?: string;
    avatar_color?: string;
    max_resolution?: number;
    allow_direct_play?: boolean;
    allow_remux?: boolean;
    allow_transcode?: boolean;
    auto_play?: boolean;
    client_video_codecs?: string;
    client_audio_codecs?: string;
  }) =>
    request<import("./types").Profile>(`/profiles/${profileId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProfile: (profileId: string) =>
    request<void>(`/profiles/${profileId}`, { method: "DELETE" }),

  // Watch progress
  reportProgress: (data: {
    provider_key: string;
    content_type: string;
    external_id: number;
    position_seconds: number;
    duration_seconds: number;
    series_external_id?: number;
    season_number?: number;
    episode_number?: number;
  }) =>
    request<WatchProgressResponse>("/watch-progress/report", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  beaconProgress: (data: {
    provider_key: string;
    content_type: string;
    external_id: number;
    position_seconds: number;
    duration_seconds: number;
    series_external_id?: number;
    season_number?: number;
    episode_number?: number;
  }) => {
    const token = getToken();
    const profileId = getProfileId();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (profileId) headers["X-Profile-Id"] = profileId;
    try {
      fetch(`${API_BASE}/watch-progress/beacon`, {
        method: "POST",
        headers,
        body: JSON.stringify(data),
        keepalive: true,
      });
    } catch { /* best-effort on teardown */ }
  },

  markWatched: (data: {
    provider_key: string;
    content_type: string;
    external_id: number;
    series_external_id?: number;
    season_number?: number;
    episode_number?: number;
  }) =>
    request<WatchProgressResponse>("/watch-progress/mark-watched", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  markUnwatched: (data: {
    provider_key: string;
    content_type: string;
    external_id: number;
  }) =>
    request<WatchProgressResponse>("/watch-progress/mark-unwatched", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getWatchProgress: (providerKey: string, contentType: string, externalId: number) =>
    request<WatchProgressResponse>(`/watch-progress/get/${providerKey}/${contentType}/${externalId}`),

  getContinueWatching: (limit = 20) =>
    request<WatchProgressResponse[]>(`/watch-progress/continue-watching?limit=${limit}`),

  getWatched: (contentType?: string, limit = 100) =>
    request<WatchProgressResponse[]>(`/watch-progress/watched?limit=${limit}${contentType ? `&content_type=${contentType}` : ""}`),

  getSeriesProgress: (providerKey: string, seriesExternalId: number) =>
    request<WatchProgressResponse[]>(`/watch-progress/series/${providerKey}/${seriesExternalId}`),

  // Remote Access
  remoteAccessStatus: () =>
    request<{ enabled: boolean; online: boolean; endpoint_id: string | null; relay_connected: boolean }>("/remote-access/status"),

  remoteAccessEnable: () =>
    request<{ enabled: boolean; online: boolean }>("/remote-access/enable", { method: "POST" }),

  remoteAccessDisable: () =>
    request<{ enabled: boolean; online: boolean }>("/remote-access/disable", { method: "POST" }),

  remoteAccessConnectionUrl: () =>
    request<{ url: string }>("/remote-access/connection-url"),
};
