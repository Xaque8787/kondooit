/*
# Kondooit Complete Schema (canonical reference)

Ensures all tables exist for fresh deployments.
Tables added by migrations 0002-0005 are included here
so a fresh database arrives at the full current state.
*/

-- Provider settings (metadata + source providers)
CREATE TABLE IF NOT EXISTS provider_settings (
    key text PRIMARY KEY,
    api_key text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'disabled',
    priority integer NOT NULL DEFAULT 100,
    credentials jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE provider_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_provider_settings" ON provider_settings;
CREATE POLICY "anon_select_provider_settings" ON provider_settings FOR SELECT
TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_provider_settings" ON provider_settings;
CREATE POLICY "anon_insert_provider_settings" ON provider_settings FOR INSERT
TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_provider_settings" ON provider_settings;
CREATE POLICY "anon_update_provider_settings" ON provider_settings FOR UPDATE
TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_provider_settings" ON provider_settings;
CREATE POLICY "anon_delete_provider_settings" ON provider_settings FOR DELETE
TO anon, authenticated USING (true);

-- User content state (favorites/following)
CREATE TABLE IF NOT EXISTS user_content_state (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider_key text NOT NULL,
  content_type text NOT NULL CHECK (content_type IN ('movie', 'series')),
  external_id integer NOT NULL,
  is_favorite boolean NOT NULL DEFAULT false,
  is_following boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_user_content_state UNIQUE (user_id, provider_key, content_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_user_content_state_user_favorites
  ON user_content_state (user_id, is_favorite) WHERE is_favorite = true;

CREATE INDEX IF NOT EXISTS idx_user_content_state_user_following
  ON user_content_state (user_id, is_following) WHERE is_following = true;

ALTER TABLE user_content_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "select_own_state" ON user_content_state;
CREATE POLICY "select_own_state" ON user_content_state FOR SELECT
  TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "insert_own_state" ON user_content_state;
CREATE POLICY "insert_own_state" ON user_content_state FOR INSERT
  TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "update_own_state" ON user_content_state;
CREATE POLICY "update_own_state" ON user_content_state FOR UPDATE
  TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "delete_own_state" ON user_content_state;
CREATE POLICY "delete_own_state" ON user_content_state FOR DELETE
  TO authenticated USING (auth.uid() = user_id);

-- Scraper modules (installed source resolver modules)
CREATE TABLE IF NOT EXISTS scraper_modules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id text NOT NULL UNIQUE,
    name text NOT NULL,
    version text NOT NULL,
    description text NOT NULL DEFAULT '',
    source_type text NOT NULL,
    source_path text NOT NULL,
    installed_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE scraper_modules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_scraper_modules" ON scraper_modules;
CREATE POLICY "anon_select_scraper_modules" ON scraper_modules FOR SELECT
TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_scraper_modules" ON scraper_modules;
CREATE POLICY "anon_insert_scraper_modules" ON scraper_modules FOR INSERT
TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_scraper_modules" ON scraper_modules;
CREATE POLICY "anon_update_scraper_modules" ON scraper_modules FOR UPDATE
TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_scraper_modules" ON scraper_modules;
CREATE POLICY "anon_delete_scraper_modules" ON scraper_modules FOR DELETE
TO anon, authenticated USING (true);

-- Scraper settings (per-scraper toggle within a module)
CREATE TABLE IF NOT EXISTS scraper_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id text NOT NULL,
    scraper_key text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    config jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_scraper_settings_module_key UNIQUE (module_id, scraper_key)
);

ALTER TABLE scraper_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_scraper_settings" ON scraper_settings;
CREATE POLICY "anon_select_scraper_settings" ON scraper_settings FOR SELECT
TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_scraper_settings" ON scraper_settings;
CREATE POLICY "anon_insert_scraper_settings" ON scraper_settings FOR INSERT
TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_scraper_settings" ON scraper_settings;
CREATE POLICY "anon_update_scraper_settings" ON scraper_settings FOR UPDATE
TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_scraper_settings" ON scraper_settings;
CREATE POLICY "anon_delete_scraper_settings" ON scraper_settings FOR DELETE
TO anon, authenticated USING (true);

-- Watch progress (per-profile playback position and watched status)
CREATE TABLE IF NOT EXISTS watch_progress (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  profile_id uuid,
  provider_key text NOT NULL,
  content_type text NOT NULL CHECK (content_type IN ('movie', 'episode')),
  external_id integer NOT NULL,
  series_external_id integer,
  season_number integer,
  episode_number integer,
  position_seconds real NOT NULL DEFAULT 0,
  duration_seconds real NOT NULL DEFAULT 0,
  watched boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_watch_progress_user_profile_content
  ON watch_progress (user_id, COALESCE(profile_id, '00000000-0000-0000-0000-000000000000'), provider_key, content_type, external_id);

CREATE INDEX IF NOT EXISTS idx_watch_progress_continue
  ON watch_progress (user_id, profile_id, updated_at DESC)
  WHERE watched = false AND position_seconds > 0;

CREATE INDEX IF NOT EXISTS idx_watch_progress_watched
  ON watch_progress (user_id, profile_id, watched)
  WHERE watched = true;

ALTER TABLE watch_progress ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "select_own_progress" ON watch_progress;
CREATE POLICY "select_own_progress" ON watch_progress FOR SELECT
  TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "insert_own_progress" ON watch_progress;
CREATE POLICY "insert_own_progress" ON watch_progress FOR INSERT
  TO authenticated WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "update_own_progress" ON watch_progress;
CREATE POLICY "update_own_progress" ON watch_progress FOR UPDATE
  TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "delete_own_progress" ON watch_progress;
CREATE POLICY "delete_own_progress" ON watch_progress FOR DELETE
  TO authenticated USING (auth.uid() = user_id);
