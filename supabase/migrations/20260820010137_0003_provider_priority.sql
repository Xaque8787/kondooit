/*
# Add priority column to provider_settings

1. Modified Tables
   - `provider_settings`
     - Added `priority` (integer, NOT NULL, default 100) — lower number = higher priority

2. Important Notes
   - Lower priority numbers indicate higher priority (e.g., 1 is highest priority)
   - Default of 100 ensures existing providers get a neutral priority
   - Providers are selected by priority order per ADR-0011
*/

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'provider_settings' AND column_name = 'priority'
  ) THEN
    ALTER TABLE provider_settings ADD COLUMN priority integer NOT NULL DEFAULT 100;
  END IF;
END $$;
