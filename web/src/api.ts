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
} from "./types";

const API_BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("kondooit_token");
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

  addTorrent: (info_hash: string, provider_key: string = "torbox") =>
    request<{ success: boolean; detail: string }>("/source-providers/add-torrent", {
      method: "POST",
      body: JSON.stringify({ info_hash, provider_key }),
    }),

  resolveStream: (info_hash: string, provider_key: string = "torbox", file_index?: number) =>
    request<{ success: boolean; detail: string; stream_url: string | null }>("/source-providers/resolve", {
      method: "POST",
      body: JSON.stringify({ info_hash, provider_key, file_index: file_index ?? null }),
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

  toggleScraper: (key: string, enabled: boolean) =>
    request<import("./types").ScraperInfo>(`/source-providers/scrapers/${key}`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),
};
