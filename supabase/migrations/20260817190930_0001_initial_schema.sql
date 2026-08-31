/*
# Kondooit v0.0.1 Initial Schema

Creates the foundational database tables for the Kondooit media platform's
walking skeleton. This schema supports: administrator authentication, canonical
content catalog (movies, series, seasons, episodes), genres, and collections.

## Architecture Note

Kondooit's server connects to PostgreSQL directly with a service-role connection.
The server is the sole database client — the React web client talks to the
Litestar API, never to PostgreSQL directly. RLS is enabled per Supabase requirements
with permissive policies for anon/authenticated roles, but the server's connection
bypasses RLS via its service role.

## New Tables

1. `users` — Administrator accounts for the Kondooit server
   - `id` (uuid, primary key)
   - `username` (text, unique, not null)
   - `email` (text, unique, not null)
   - `password_hash` (text, not null)
   - `role` (text, not null, default 'admin')
   - `is_active` (boolean, not null, default true)
   - `created_at`, `updated_at` (timestamps)

2. `genres` — Canonical genre categories
   - `id` (uuid, primary key)
   - `name` (text, not null)
   - `tmdb_id` (integer, unique, nullable) — external evidence
   - `tvdb_id` (integer, nullable) — external evidence
   - `created_at` (timestamp)

3. `collections` — Curated content collections (e.g. "Marvel Cinematic Universe")
   - `id` (uuid, primary key)
   - `name` (text, not null)
   - `description` (text)
   - `poster_url`, `backdrop_url` (text, nullable)
   - `tmdb_id` (integer, nullable) — external evidence
   - `created_at`, `updated_at` (timestamps)

4. `movies` — Canonical movie entities (Kondooit-owned, not TMDB/TVDB mirrors)
   - `id` (uuid, primary key)
   - `title`, `overview`, `release_date`, `poster_path`, `backdrop_path`
   - `runtime_minutes`, `vote_average`
   - `collection_id` (FK to collections, nullable)
   - `tmdb_id` (integer, unique, nullable) — external evidence
   - `tvdb_id` (integer, nullable) — external evidence
   - `created_at`, `updated_at` (timestamps)

5. `series` — Canonical TV series entities
   - `id` (uuid, primary key)
   - `title`, `overview`, `first_air_date`, `last_air_date`
   - `poster_path`, `backdrop_path`, `status`, `vote_average`
   - `tmdb_id` (integer, unique, nullable) — external evidence
   - `tvdb_id` (integer, nullable) — external evidence
   - `created_at`, `updated_at` (timestamps)

6. `seasons` — Seasons belonging to a series
   - `id` (uuid, primary key)
   - `series_id` (FK to series, not null)
   - `season_number`, `name`, `overview`, `poster_path`, `episode_count`, `air_date`
   - `tmdb_id`, `tvdb_id` (nullable) — external evidence
   - `created_at`, `updated_at` (timestamps)

7. `episodes` — Episodes belonging to a season
   - `id` (uuid, primary key)
   - `series_id` (FK to series, not null)
   - `season_id` (FK to seasons, not null)
   - `episode_number`, `name`, `overview`, `still_path`, `runtime_minutes`, `air_date`, `vote_average`
   - `tmdb_id`, `tvdb_id` (nullable) — external evidence
   - `created_at`, `updated_at` (timestamps)

8. `movie_genres` — Many-to-many association (movie ↔ genre)
9. `series_genres` — Many-to-many association (series ↔ genre)

## Security

- RLS enabled on all tables.
- Permissive CRUD policies for anon, authenticated roles (server uses service-role connection that bypasses RLS).
- The Kondooit server enforces its own authentication and authorization at the application layer.

## Important Notes

1. External IDs (tmdb_id, tvdb_id) are evidence for identity resolution, not canonical identity.
2. Canonical identity is owned by the Kondooit core (ADR-0003).
3. This schema is intentionally minimal for v0.0.1 — no sources, playback sessions, or future capability tables.
*/

-- Users
CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text NOT NULL UNIQUE,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'admin',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Genres
CREATE TABLE IF NOT EXISTS genres (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    tmdb_id integer UNIQUE,
    tvdb_id integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Collections
CREATE TABLE IF NOT EXISTS collections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    poster_url text,
    backdrop_url text,
    tmdb_id integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Movies
CREATE TABLE IF NOT EXISTS movies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    overview text NOT NULL DEFAULT '',
    release_date date,
    poster_path text,
    backdrop_path text,
    runtime_minutes integer,
    vote_average real,
    collection_id uuid REFERENCES collections(id),
    tmdb_id integer UNIQUE,
    tvdb_id integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Series
CREATE TABLE IF NOT EXISTS series (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    overview text NOT NULL DEFAULT '',
    first_air_date date,
    last_air_date date,
    poster_path text,
    backdrop_path text,
    status text NOT NULL DEFAULT '',
    vote_average real,
    tmdb_id integer UNIQUE,
    tvdb_id integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seasons
CREATE TABLE IF NOT EXISTS seasons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id uuid NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    season_number integer NOT NULL,
    name text NOT NULL DEFAULT '',
    overview text NOT NULL DEFAULT '',
    poster_path text,
    episode_count integer NOT NULL DEFAULT 0,
    air_date date,
    tmdb_id integer,
    tvdb_id integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Episodes
CREATE TABLE IF NOT EXISTS episodes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id uuid NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    season_id uuid NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    episode_number integer NOT NULL,
    name text NOT NULL DEFAULT '',
    overview text NOT NULL DEFAULT '',
    still_path text,
    runtime_minutes integer,
    air_date date,
    vote_average real,
    tmdb_id integer,
    tvdb_id integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Association tables
CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id uuid NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    genre_id uuid NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, genre_id)
);

CREATE TABLE IF NOT EXISTS series_genres (
    series_id uuid NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    genre_id uuid NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (series_id, genre_id)
);

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE genres ENABLE ROW LEVEL SECURITY;
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE movies ENABLE ROW LEVEL SECURITY;
ALTER TABLE series ENABLE ROW LEVEL SECURITY;
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE movie_genres ENABLE ROW LEVEL SECURITY;
ALTER TABLE series_genres ENABLE ROW LEVEL SECURITY;

-- Permissive CRUD policies for anon, authenticated
-- (The Kondooit server connects with a service role that bypasses RLS.
--  Application-layer authentication is enforced by the Litestar API.)
DO $$
DECLARE
    t text;
    tables text[] := ARRAY['users', 'genres', 'collections', 'movies', 'series', 'seasons', 'episodes', 'movie_genres', 'series_genres'];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS "anon_select_%s" ON %I', t, t);
        EXECUTE format('CREATE POLICY "anon_select_%s" ON %s FOR SELECT TO anon, authenticated USING (true)', t, t);

        EXECUTE format('DROP POLICY IF EXISTS "anon_insert_%s" ON %I', t, t);
        EXECUTE format('CREATE POLICY "anon_insert_%s" ON %s FOR INSERT TO anon, authenticated WITH CHECK (true)', t, t);

        EXECUTE format('DROP POLICY IF EXISTS "anon_update_%s" ON %I', t, t);
        EXECUTE format('CREATE POLICY "anon_update_%s" ON %s FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true)', t, t);

        EXECUTE format('DROP POLICY IF EXISTS "anon_delete_%s" ON %I', t, t);
        EXECUTE format('CREATE POLICY "anon_delete_%s" ON %s FOR DELETE TO anon, authenticated USING (true)', t, t);
    END LOOP;
END $$;
