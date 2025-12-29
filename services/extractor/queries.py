"""SQL queries for extractor services.

This module contains all SQL queries used by the extractor services, such as
CompanyExtractor and JobExtractor. Extracting queries here improves
maintainability, enables syntax highlighting, and makes queries easier to
review and test.
"""

# Query to check if staging.glassdoor_companies table exists
CHECK_GLASSDOOR_TABLE_EXISTS = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'staging'
        AND table_name = 'glassdoor_companies'
    )
"""

# Query to get companies needing enrichment when glassdoor_companies table exists
GET_COMPANIES_TO_ENRICH_WITH_TABLE = """
    SELECT DISTINCT
        lower(trim(employer_name)) as company_lookup_key
    FROM staging.jsearch_job_postings
    WHERE employer_name IS NOT NULL
        AND trim(employer_name) != ''
        AND lower(trim(employer_name)) NOT IN (
            -- Exclude companies already in staging.glassdoor_companies
            SELECT DISTINCT company_lookup_key
            FROM staging.glassdoor_companies
            WHERE company_lookup_key IS NOT NULL
        )
        AND lower(trim(employer_name)) NOT IN (
            -- Exclude companies already successfully enriched or marked as not_found
            SELECT company_lookup_key
            FROM staging.company_enrichment_queue
            WHERE enrichment_status IN ('success', 'not_found')
        )
    ORDER BY company_lookup_key
"""

# Query to get companies needing enrichment when glassdoor_companies table doesn't exist yet
GET_COMPANIES_TO_ENRICH_WITHOUT_TABLE = """
    SELECT DISTINCT
        lower(trim(employer_name)) as company_lookup_key
    FROM staging.jsearch_job_postings
    WHERE employer_name IS NOT NULL
        AND trim(employer_name) != ''
        AND lower(trim(employer_name)) NOT IN (
            -- Exclude companies already successfully enriched or marked as not_found
            SELECT company_lookup_key
            FROM staging.company_enrichment_queue
            WHERE enrichment_status IN ('success', 'not_found')
        )
    ORDER BY company_lookup_key
"""

# Query to mark a company as queued/pending in the enrichment queue
MARK_COMPANY_QUEUED = """
    INSERT INTO staging.company_enrichment_queue (
        company_lookup_key,
        enrichment_status,
        first_queued_at,
        last_attempt_at,
        attempt_count
    ) VALUES (%s, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
    ON CONFLICT (company_lookup_key)
    DO UPDATE SET
        enrichment_status = 'pending',
        last_attempt_at = CURRENT_TIMESTAMP,
        attempt_count = staging.company_enrichment_queue.attempt_count + 1
"""

# Query to insert company data into raw.glassdoor_companies
INSERT_COMPANY = """
    INSERT INTO raw.glassdoor_companies (
        glassdoor_companies_key,
        raw_payload,
        company_lookup_key,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system
    ) VALUES (%s, %s, %s, %s, %s, %s)
"""

# Query to mark company enrichment as error
MARK_COMPANY_ERROR = """
    UPDATE staging.company_enrichment_queue
    SET enrichment_status = 'error',
        last_attempt_at = CURRENT_TIMESTAMP,
        error_message = %s
    WHERE company_lookup_key = %s
"""

# Query to update enrichment status in queue
UPDATE_ENRICHMENT_STATUS = """
    UPDATE staging.company_enrichment_queue
    SET enrichment_status = %s,
        last_attempt_at = CURRENT_TIMESTAMP,
        completed_at = CASE WHEN %s IN ('success', 'not_found') THEN CURRENT_TIMESTAMP ELSE completed_at END
    WHERE company_lookup_key = %s
"""


# === JobExtractor queries ===

# Query to get active campaigns for job extraction
GET_ACTIVE_CAMPAIGNS_FOR_JOBS = """
    SELECT
        campaign_id,
        campaign_name,
        query,
        location,
        country,
        date_window,
        email
    FROM marts.job_campaigns
    WHERE is_active = true
    ORDER BY campaign_id
"""

# Base INSERT for raw.jsearch_job_postings
INSERT_JSEARCH_JOB_POSTINGS = """
    INSERT INTO raw.jsearch_job_postings (
        jsearch_job_postings_key,
        raw_payload,
        dwh_load_date,
        dwh_load_timestamp,
        dwh_source_system,
        campaign_id
    ) VALUES %s
"""
