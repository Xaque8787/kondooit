/*
# Add provider_settings table

1. New Tables
   - `provider_settings`
     - `key` (text, primary key) — provider identifier (e.g. "tmdb", "tvdb")
     - `api_key` (text, not null, default '') — API key for the provider
     - `status` (text, not null, default 'disabled') — "enabled" or "disabled"
     - `created_at`, `updated_at` (timestamps)

2. Purpose
   Stores configuration for metadata providers (TMDB, TVDB). Each provider
   has a row with its API key and enabled/disabled status.

3. Security
   - RLS enabled with permissive policies (server uses service-role connection).
   - API key values are stored as plaintext for v0.0.1 simplicity; encryption
     at rest is future work.

4. Notes
   - This table is scoped to metadata provider configuration only.
   - No source, playback, or acquisition provider types are represented.
*/

CREATE TABLE IF NOT EXISTS provider_settings (
    key text PRIMARY KEY,
    api_key text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'disabled',
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
