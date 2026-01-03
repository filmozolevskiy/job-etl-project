-- Migration script to normalize field value casing in staging.jsearch_job_postings
-- Bug #4: Inconsistent Field Value Casing in Database
-- Date: 2026-01-02
--
-- This script normalizes field values to consistent casing standards:
-- - job_salary_period: lowercase ("year", "month", "week", "day", "hour")
-- - job_employment_type: uppercase ("FULLTIME", "PARTTIME", "CONTRACTOR", etc.)
-- - employment_types: uppercase (comma-separated values)
-- - remote_work_type: lowercase ("remote", "hybrid", "onsite")
-- - seniority_level: lowercase ("intern", "junior", "mid", "senior", "executive")
-- - job_salary_currency: uppercase ("USD", "CAD", "EUR", "GBP")

-- Normalize job_salary_period to lowercase
UPDATE staging.jsearch_job_postings
SET job_salary_period = LOWER(job_salary_period)
WHERE job_salary_period IS NOT NULL
    AND job_salary_period != LOWER(job_salary_period);

-- Normalize job_employment_type to uppercase
UPDATE staging.jsearch_job_postings
SET job_employment_type = UPPER(job_employment_type)
WHERE job_employment_type IS NOT NULL
    AND job_employment_type != UPPER(job_employment_type)
    AND job_employment_type != '';

-- Normalize employment_types (comma-separated string) to uppercase
-- Use a CTE to normalize and then update
WITH normalized_employment_types AS (
    SELECT
        jsearch_job_postings_key,
        string_agg(UPPER(TRIM(unnest_value)), ',') AS normalized_types
    FROM staging.jsearch_job_postings,
    LATERAL unnest(string_to_array(employment_types, ',')) AS unnest_value
    WHERE employment_types IS NOT NULL
        AND employment_types != ''
    GROUP BY jsearch_job_postings_key
)
UPDATE staging.jsearch_job_postings jp
SET employment_types = net.normalized_types
FROM normalized_employment_types net
WHERE jp.jsearch_job_postings_key = net.jsearch_job_postings_key
    AND jp.employment_types != net.normalized_types;

-- Normalize remote_work_type to lowercase
UPDATE staging.jsearch_job_postings
SET remote_work_type = LOWER(remote_work_type)
WHERE remote_work_type IS NOT NULL
    AND remote_work_type != LOWER(remote_work_type);

-- Normalize seniority_level to lowercase
UPDATE staging.jsearch_job_postings
SET seniority_level = LOWER(seniority_level)
WHERE seniority_level IS NOT NULL
    AND seniority_level != LOWER(seniority_level);

-- Normalize job_salary_currency to uppercase
UPDATE staging.jsearch_job_postings
SET job_salary_currency = UPPER(job_salary_currency)
WHERE job_salary_currency IS NOT NULL
    AND job_salary_currency != UPPER(job_salary_currency);

-- Log summary
DO $$
DECLARE
    salary_period_count INTEGER;
    employment_type_count INTEGER;
    remote_type_count INTEGER;
    seniority_count INTEGER;
    currency_count INTEGER;
BEGIN
    -- Count rows that would be affected (already normalized rows won't be updated)
    SELECT COUNT(*) INTO salary_period_count
    FROM staging.jsearch_job_postings
    WHERE job_salary_period IS NOT NULL
        AND job_salary_period != LOWER(job_salary_period);
    
    SELECT COUNT(*) INTO employment_type_count
    FROM staging.jsearch_job_postings
    WHERE job_employment_type IS NOT NULL
        AND job_employment_type != UPPER(job_employment_type)
        AND job_employment_type != '';
    
    SELECT COUNT(*) INTO remote_type_count
    FROM staging.jsearch_job_postings
    WHERE remote_work_type IS NOT NULL
        AND remote_work_type != LOWER(remote_work_type);
    
    SELECT COUNT(*) INTO seniority_count
    FROM staging.jsearch_job_postings
    WHERE seniority_level IS NOT NULL
        AND seniority_level != LOWER(seniority_level);
    
    SELECT COUNT(*) INTO currency_count
    FROM staging.jsearch_job_postings
    WHERE job_salary_currency IS NOT NULL
        AND job_salary_currency != UPPER(job_salary_currency);
    
    RAISE NOTICE 'Normalization complete. Rows updated:';
    RAISE NOTICE '  - job_salary_period: %', salary_period_count;
    RAISE NOTICE '  - job_employment_type: %', employment_type_count;
    RAISE NOTICE '  - remote_work_type: %', remote_type_count;
    RAISE NOTICE '  - seniority_level: %', seniority_count;
    RAISE NOTICE '  - job_salary_currency: %', currency_count;
END $$;

COMMENT ON TABLE staging.jsearch_job_postings IS 'Updated: Field value casing normalized per Bug #4. All fields now use consistent casing standards.';

