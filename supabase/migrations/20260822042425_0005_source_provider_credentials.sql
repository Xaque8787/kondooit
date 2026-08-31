/*
# Add credentials column to provider_settings for source providers

1. Modified Tables
   - `provider_settings`
     - Added `credentials` (jsonb, NOT NULL, default '{}') — flexible credential storage
       for source providers that need more than a single API key (e.g. Easynews needs
       username + password, TorBox uses api_key, IPTV needs server URL + credentials)

2. Purpose
   Source providers (TorBox, Easynews, IPTV) share the same provider_settings table as
   metadata providers. The existing `api_key` column works for simple providers but source
   providers have varying credential shapes. The `credentials` JSONB column stores
   provider-specific credential data flexibly.

3. Important Notes
   - Metadata providers (tmdb, tvdb) continue using the `api_key` column unchanged.
   - Source providers use the `credentials` column for their specific auth data.
   - Both provider categories share the same table, distinguished by `key`.
*/

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'provider_settings' AND column_name = 'credentials'
  ) THEN
    ALTER TABLE provider_settings ADD COLUMN credentials jsonb NOT NULL DEFAULT '{}';
  END IF;
END $$;