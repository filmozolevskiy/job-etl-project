-- Migration script to fix UK country code from "uk" to "gb"
-- Bug #5: Incorrect Country Code for United Kingdom
-- Date: 2026-01-02
--
-- This script updates existing campaigns that use "uk" as the country code
-- to use "gb" (ISO 3166-1 alpha-2 standard) instead.

-- Update campaigns with country = 'uk' to 'gb'
UPDATE marts.job_campaigns
SET country = 'gb'
WHERE country = 'uk';

-- Log the number of rows updated
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE 'Updated % campaign(s) from country "uk" to "gb"', updated_count;
END $$;

COMMENT ON TABLE marts.job_campaigns IS 'Updated: Country code normalization - "uk" has been migrated to "gb" per ISO 3166-1 alpha-2 standard';

