/*
# Add playback preference columns to profiles table

1. Modified Tables
   - `profiles`
     - `max_resolution` (integer, default 2160) - max video resolution (480, 720, 1080, 2160)
     - `allow_direct_play` (boolean, default true) - allow direct playback without processing
     - `allow_remux` (boolean, default true) - allow remuxing (repackaging without re-encoding)
     - `allow_transcode` (boolean, default false) - allow full transcoding
     - `auto_play` (boolean, default false) - automatically select and play best matching source
     - `client_video_codecs` (text, default '') - comma-separated video codecs detected from browser
     - `client_audio_codecs` (text, default '') - comma-separated audio codecs detected from browser

2. Notes
   - These columns support the playback preference system (Phase A).
   - client_video_codecs and client_audio_codecs are populated by the browser at profile-select time.
   - The existing preferred_quality and allow_server_processing columns remain for backward compatibility
     but the new granular columns take precedence in application logic.
   - RLS policies remain unchanged (open access, app-layer auth via JWT guards).
*/

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'max_resolution'
    ) THEN
        ALTER TABLE profiles ADD COLUMN max_resolution integer NOT NULL DEFAULT 2160;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'allow_direct_play'
    ) THEN
        ALTER TABLE profiles ADD COLUMN allow_direct_play boolean NOT NULL DEFAULT true;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'allow_remux'
    ) THEN
        ALTER TABLE profiles ADD COLUMN allow_remux boolean NOT NULL DEFAULT true;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'allow_transcode'
    ) THEN
        ALTER TABLE profiles ADD COLUMN allow_transcode boolean NOT NULL DEFAULT false;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'auto_play'
    ) THEN
        ALTER TABLE profiles ADD COLUMN auto_play boolean NOT NULL DEFAULT false;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'client_video_codecs'
    ) THEN
        ALTER TABLE profiles ADD COLUMN client_video_codecs text NOT NULL DEFAULT '';
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'client_audio_codecs'
    ) THEN
        ALTER TABLE profiles ADD COLUMN client_audio_codecs text NOT NULL DEFAULT '';
    END IF;
END $$;
