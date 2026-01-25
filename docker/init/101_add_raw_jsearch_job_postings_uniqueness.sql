-- ============================================================
-- Migration: Enforce raw-layer dedupe for JSearch postings
--
-- Purpose:
-- - Remove existing duplicates in raw.jsearch_job_postings
-- - Enforce uniqueness for (job_id, campaign_id) at the database level
--
-- Uniqueness key:
-- - (raw_payload->>'job_id', campaign_id)
--
-- Notes:
-- - Uses ctid to delete duplicates safely without a primary key.
-- - Keeps the most recent row per (job_id, campaign_id) by dwh_load_timestamp.
-- ============================================================

-- 1) Remove existing duplicates (keep most recent per (job_id, campaign_id))
WITH ranked AS (
    SELECT
        ctid,
        row_number() OVER (
            PARTITION BY (raw_payload->>'job_id'), campaign_id
            ORDER BY
                dwh_load_timestamp DESC NULLS LAST,
                dwh_load_date DESC NULLS LAST,
                jsearch_job_postings_key DESC NULLS LAST
        ) AS rn
    FROM raw.jsearch_job_postings
    WHERE raw_payload->>'job_id' IS NOT NULL
        AND raw_payload->>'job_id' <> ''
)
DELETE FROM raw.jsearch_job_postings r
USING ranked
WHERE r.ctid = ranked.ctid
    AND ranked.rn > 1;

-- 2) Enforce uniqueness to prevent future duplicates
CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_jsearch_job_postings_job_id_campaign_id
    ON raw.jsearch_job_postings ((raw_payload->>'job_id'), campaign_id);

