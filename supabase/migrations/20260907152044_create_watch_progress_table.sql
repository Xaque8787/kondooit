/*
# Create watch_progress table

Tracks per-profile playback progress for movies and episodes.
The client reports position/duration when playback pauses, stops,
or on page unload. The server computes `watched` status using a
90% completion threshold.

1. New Tables
   - `watch_progress`
     - `id` (uuid, primary key)
     - `user_id` (uuid, references users)
     - `profile_id` (uuid, nullable - for per-profile tracking)
     - `provider_key` (text - which metadata provider, e.g. 'tmdb')
     - `content_type` (text - 'movie' or 'episode')
     - `external_id` (integer - provider external ID for the content)
     - `series_external_id` (integer, nullable - parent series ID for episodes)
     - `season_number` (integer, nullable - for episode context)
     - `episode_number` (integer, nullable - for episode context)
     - `position_seconds` (real - current playback position)
     - `duration_seconds` (real - total content duration)
     - `watched` (boolean - true when >= 90% viewed or manually set)
     - `created_at` (timestamptz)
     - `updated_at` (timestamptz)

2. Indexes
   - Unique constraint on (user_id, profile_id, provider_key, content_type, external_id)
   - Index on (user_id, profile_id, watched) for "continue watching" queries
   - Index on (user_id, profile_id, updated_at) for recent activity

3. Security
   - RLS enabled with owner-scoped policies (authenticated users only).

4. Notes
   - `content_type` is 'movie' or 'episode' (not 'series') because progress
     is tracked per-playable-item. Series-level watched status is derived
     from episode-level data.
   - `series_external_id`, `season_number`, `episode_number` provide context
     so the "continue watching" row can show which episode in which series.
*/

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
