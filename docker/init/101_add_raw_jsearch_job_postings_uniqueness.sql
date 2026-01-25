-- ============================================================
-- Migration: Enforce uniqueness in raw.jsearch_job_postings
--
-- Goal:
-- - Prevent duplicate raw inserts for the same (job_id, campaign_id)
-- - Keep raw layer small and metrics honest
--
-- Strategy:
-- 1) Delete existing duplicates, keeping the most recent record
-- 2) Add a UNIQUE index on ((raw_payload->>'job_id'), campaign_id)
-- ============================================================

-- 1) Remove duplicates (keep latest per (job_id, campaign_id))
WITH ranked AS (
    SELECT
        ctid,
        row_number() OVER (
            PARTITION BY raw_payload->>'job_id', campaign_id
            ORDER BY dwh_load_timestamp DESC NULLS LAST, dwh_load_date DESC NULLS LAST
        ) AS rn
    FROM raw.jsearch_job_postings
    WHERE raw_payload->>'job_id' IS NOT NULL
)
DELETE FROM raw.jsearch_job_postings r
USING ranked d
WHERE r.ctid = d.ctid
  AND d.rn > 1;

-- 2) Enforce uniqueness going forward
CREATE UNIQUE INDEX IF NOT EXISTS uq_jsearch_job_postings_job_id_campaign_id
    ON raw.jsearch_job_postings ((raw_payload->>'job_id'), campaign_id);

