/*
# Create user_content_state table

This table stores user preference/state (Favorites and Following) — NOT a content catalog.
It is a thin reference layer connecting users to provider-sourced content.
Metadata is always retrieved from the provider; this table stores only the relationship.

1. New Tables
   - `user_content_state`
     - `id` (uuid, primary key)
     - `user_id` (uuid, FK to users, NOT NULL)
     - `provider_key` (text, NOT NULL) — which provider the content comes from
     - `content_type` (text, NOT NULL) — 'movie' or 'series'
     - `external_id` (integer, NOT NULL) — provider's external ID for the content
     - `is_favorite` (boolean, default false)
     - `is_following` (boolean, default false)
     - `created_at` (timestamptz)
     - `updated_at` (timestamptz)
   - Unique constraint on (user_id, provider_key, content_type, external_id)
   - Future migration path: a content_id column can be added later for cross-provider identity

2. Security
   - Enable RLS on user_content_state
   - 4 policies: users can only manage their own state (authenticated only)

3. Important Notes
   - This is user preference/state, NOT a content catalog
   - Provider IDs are references, not content identity (per ADR-0011)
   - Table structure intentionally allows future content_id column addition
*/

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
