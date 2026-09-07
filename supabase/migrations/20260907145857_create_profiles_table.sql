/*
# Create profiles table

Profiles represent individual household members within a single account.
Each account (user) can have multiple profiles with their own display name,
avatar, and playback preferences. The admin user gets a default profile
automatically via application logic on first login.

1. New Tables
   - `profiles`
     - `id` (uuid, primary key)
     - `user_id` (uuid, FK -> users, CASCADE) - owning account
     - `display_name` (text, not null) - name shown on profile selection
     - `avatar_color` (text) - hex color for generated avatar
     - `is_admin` (boolean, default false) - admin profile flag
     - `preferred_quality` (text, default '1080p') - preferred stream quality
     - `allow_server_processing` (boolean, default true) - allow remux/transcode
     - `created_at` (timestamptz)
     - `updated_at` (timestamptz)

2. Modified Tables
   - `user_content_state` - add `profile_id` column (uuid, FK -> profiles)
     Content state becomes profile-scoped. The column is nullable initially
     to avoid breaking existing rows; application logic will require it going forward.

3. Security
   - RLS enabled on `profiles`.
   - Policies: anon + authenticated full access (admin-only system with custom JWT auth).
   - user_content_state gets an index on profile_id.

4. Notes
   - The app uses custom JWT auth (not Supabase Auth), so RLS policies use
     open access similar to other tables. Access control is enforced at the
     application layer via JWT guards.
*/

-- Profiles table
CREATE TABLE IF NOT EXISTS profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name text NOT NULL,
    avatar_color text NOT NULL DEFAULT '#3B82F6',
    is_admin boolean NOT NULL DEFAULT false,
    preferred_quality text NOT NULL DEFAULT '1080p',
    allow_server_processing boolean NOT NULL DEFAULT true,
    max_resolution integer NOT NULL DEFAULT 2160,
    allow_direct_play boolean NOT NULL DEFAULT true,
    allow_remux boolean NOT NULL DEFAULT true,
    allow_transcode boolean NOT NULL DEFAULT false,
    auto_play boolean NOT NULL DEFAULT false,
    client_video_codecs text NOT NULL DEFAULT '',
    client_audio_codecs text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles (user_id);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_profiles" ON profiles;
CREATE POLICY "anon_select_profiles" ON profiles FOR SELECT
TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_profiles" ON profiles;
CREATE POLICY "anon_insert_profiles" ON profiles FOR INSERT
TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_profiles" ON profiles;
CREATE POLICY "anon_update_profiles" ON profiles FOR UPDATE
TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_profiles" ON profiles;
CREATE POLICY "anon_delete_profiles" ON profiles FOR DELETE
TO anon, authenticated USING (true);

-- Add profile_id to user_content_state (nullable for migration safety)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_content_state' AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE user_content_state ADD COLUMN profile_id uuid REFERENCES profiles(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_content_state_profile
    ON user_content_state (profile_id) WHERE profile_id IS NOT NULL;
