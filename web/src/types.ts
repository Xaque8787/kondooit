export interface Genre {
  id: string;
  name: string;
  tmdb_id: number | null;
  tvdb_id: number | null;
}

export interface Collection {
  id: string;
  name: string;
  description: string;
  poster_url: string | null;
  backdrop_url: string | null;
  tmdb_id: number | null;
}

export interface Movie {
  id: string;
  title: string;
  overview: string;
  release_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  runtime_minutes: number | null;
  vote_average: number | null;
  genres: Genre[];
  collection_id: string | null;
  tmdb_id: number | null;
  tvdb_id: number | null;
}

export interface Season {
  id: string;
  series_id: string;
  season_number: number;
  name: string;
  overview: string;
  poster_path: string | null;
  episode_count: number;
  air_date: string | null;
  tmdb_id: number | null;
  tvdb_id: number | null;
}

export interface Episode {
  id: string;
  series_id: string;
  season_id: string;
  episode_number: number;
  name: string;
  overview: string;
  still_path: string | null;
  runtime_minutes: number | null;
  air_date: string | null;
  vote_average: number | null;
  tmdb_id: number | null;
  tvdb_id: number | null;
}

export interface Series {
  id: string;
  title: string;
  overview: string;
  first_air_date: string | null;
  last_air_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  status: string;
  vote_average: number | null;
  genres: Genre[];
  seasons: Season[];
  tmdb_id: number | null;
  tvdb_id: number | null;
}

export interface ProviderInfo {
  key: string;
  name: string;
  description: string;
  supports: string[];
  requires_api_key: boolean;
}

export interface ProviderConfig {
  key: string;
  api_key: string;
  status: string;
  priority: number;
}

export interface TestConnectionResponse {
  key: string;
  connected: boolean;
}

export interface MovieEvidence {
  external_id: number;
  title: string;
  overview: string;
  release_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  runtime_minutes: number | null;
  vote_average: number | null;
}

export interface SeriesEvidence {
  external_id: number;
  title: string;
  overview: string;
  first_air_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  vote_average: number | null;
}

export interface ImportResult {
  id: string;
  title: string;
  tmdb_id: number | null;
  tvdb_id: number | null;
}

export interface DiscoveredMovie {
  title: string;
  overview: string;
  release_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  vote_average: number | null;
  provider_key: string;
  external_id: number;
}

export interface DiscoveredSeries {
  title: string;
  overview: string;
  first_air_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  vote_average: number | null;
  provider_key: string;
  external_id: number;
}

export interface DiscoveryGenre {
  name: string;
  external_id: number;
  content_type: string;
  provider_key: string;
}

export interface DiscoverySection {
  title: string;
  section_key: string;
  provider_key: string;
  movies: DiscoveredMovie[];
  series: DiscoveredSeries[];
}

export interface SeasonDetail {
  external_id: number;
  season_number: number;
  name: string;
  overview: string;
  poster_path: string | null;
  episode_count: number;
  air_date: string | null;
  episodes: {
    external_id: number;
    season_number: number;
    episode_number: number;
    name: string;
    overview: string;
    still_path: string | null;
    runtime_minutes: number | null;
    air_date: string | null;
    vote_average: number | null;
  }[];
}

export interface DiscoveredGenre {
  name: string;
  external_id: number;
  content_type: string;
  provider_key: string;
}

export interface MovieDetail {
  external_id: number;
  title: string;
  overview: string;
  release_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  runtime_minutes: number | null;
  vote_average: number | null;
  genres: { id: number; name: string }[];
  collection_external_id: number | null;
  collection_name: string | null;
  provider_key: string;
}

export interface SeriesDetail {
  external_id: number;
  title: string;
  overview: string;
  first_air_date: string | null;
  last_air_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  status: string;
  vote_average: number | null;
  genres: { id: number; name: string }[];
  seasons: {
    external_id: number;
    season_number: number;
    name: string;
    overview: string;
    poster_path: string | null;
    episode_count: number;
    air_date: string | null;
    episodes: {
      external_id: number;
      season_number: number;
      episode_number: number;
      name: string;
      overview: string;
      still_path: string | null;
      runtime_minutes: number | null;
      air_date: string | null;
      vote_average: number | null;
    }[];
  }[];
  provider_key: string;
}

export interface ProviderCapabilities {
  key: string;
  capabilities: string[];
}

export interface ProfileBrief {
  id: string;
  display_name: string;
  avatar_color: string;
  is_admin: boolean;
}

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  profiles: ProfileBrief[];
}

export interface Profile {
  id: string;
  user_id: string;
  display_name: string;
  avatar_color: string;
  is_admin: boolean;
  preferred_quality: string;
  allow_server_processing: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface BootstrapAdminResponse {
  id: string;
  username: string;
  email: string;
  role: string;
  access_token: string;
  token_type: string;
}

export interface UserContentState {
  provider_key: string;
  content_type: string;
  external_id: number;
  is_favorite: boolean;
  is_following: boolean;
}

// Source providers (TorBox, Easynews)
export interface SourceProviderCredentialField {
  name: string;
  label: string;
  field_type: string;
  required: boolean;
  placeholder: string;
}

export interface SourceProviderInfo {
  key: string;
  name: string;
  description: string;
  capabilities: string[];
  credential_fields: SourceProviderCredentialField[];
}

export interface SourceProviderConfig {
  key: string;
  credentials: Record<string, string>;
  status: string;
  priority: number;
}

export interface SourceResult {
  provider_key: string;
  filename: string;
  size_bytes: number;
  quality: string;
  codec: string;
  duration_seconds: number | null;
  info_hash: string | null;
  seeders: number | null;
  source_type: string;
  scraper_source: string | null;
  stream_id: string | null;
  is_season_pack: boolean;
  file_count: number;
}

export interface ScraperConfigFieldSchema {
  type: string;
  label: string;
  description: string;
  options?: string[];
  default?: string;
}

export interface ScraperInfo {
  key: string;
  name: string;
  tier: number;
  category: string;
  content_types: string[];
  enabled: boolean;
  config_schema?: Record<string, ScraperConfigFieldSchema> | null;
  config?: Record<string, string> | null;
}

export interface ScraperModule {
  module_id: string;
  name: string;
  version: string;
  description: string;
  scrapers: ScraperInfo[];
}

export interface ModuleInstallResponse {
  module_id: string;
  name: string;
  version: string;
  description: string;
  scrapers: ScraperInfo[];
}

export interface WatchProgressResponse {
  provider_key: string;
  content_type: string;
  external_id: number;
  series_external_id: number | null;
  season_number: number | null;
  episode_number: number | null;
  position_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  watched: boolean;
  updated_at: string | null;
}
