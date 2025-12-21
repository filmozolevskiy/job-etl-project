"""SQL queries for enrichment analysis service.

This module contains all SQL queries used by the EnrichmentAnalyzer service.
"""

# Query to find jobs with missing seniority detection
# Finds jobs where seniority_level IS NULL but title/description contains seniority indicators
FIND_MISSING_SENIORITY = """
    SELECT
        jsearch_job_postings_key,
        jsearch_job_id,
        job_title,
        job_description,
        extracted_skills,
        seniority_level
    FROM staging.jsearch_job_postings
    WHERE seniority_level IS NULL
        AND job_title IS NOT NULL
        AND (
            -- Check for seniority patterns in title
            LOWER(job_title) ~ '\\y(intern|internship|co-op|coop)\\y'
            OR LOWER(job_title) ~ '\\y(junior|jr|entry|entry-level|entry level|associate)\\y'
            OR LOWER(job_title) ~ '\\y(mid|mid-level|mid level|intermediate|level 2|ii)\\y'
            OR LOWER(job_title) ~ '\\y(senior|sr|lead|principal|staff|level 3|iii|iv)\\y'
            OR LOWER(job_title) ~ '\\y(director|vp|vice president|cfo|cto|ceo|executive)\\y'
            -- Also check description if title doesn't have it
            OR (
                job_description IS NOT NULL
                AND (
                    LOWER(job_description) ~ '\\y(intern|internship|co-op|coop)\\y'
                    OR LOWER(job_description) ~ '\\y(junior|jr|entry|entry-level|entry level|associate)\\y'
                    OR LOWER(job_description) ~ '\\y(mid|mid-level|mid level|intermediate|level 2|ii)\\y'
                    OR LOWER(job_description) ~ '\\y(senior|sr|lead|principal|staff|level 3|iii|iv)\\y'
                    OR LOWER(job_description) ~ '\\y(director|vp|vice president|cfo|cto|ceo|executive)\\y'
                )
            )
        )
    ORDER BY dwh_load_timestamp DESC
    LIMIT %s
"""

# Query to get sample job titles grouped by patterns for missing seniority
GET_SENIORITY_PATTERNS = """
    SELECT
        CASE
            WHEN LOWER(job_title) ~ '\\y(intern|internship|co-op|coop)\\y' THEN 'intern'
            WHEN LOWER(job_title) ~ '\\y(junior|jr|entry|entry-level|entry level|associate)\\y' THEN 'junior'
            WHEN LOWER(job_title) ~ '\\y(mid|mid-level|mid level|intermediate|level 2|ii)\\y' THEN 'mid'
            WHEN LOWER(job_title) ~ '\\y(senior|sr|lead|principal|staff|level 3|iii|iv)\\y' THEN 'senior'
            WHEN LOWER(job_title) ~ '\\y(director|vp|vice president|cfo|cto|ceo|executive)\\y' THEN 'executive'
            ELSE 'unknown'
        END as detected_seniority,
        COUNT(*) as job_count,
        array_agg(DISTINCT job_title ORDER BY job_title) as sample_titles
    FROM staging.jsearch_job_postings
    WHERE seniority_level IS NULL
        AND job_title IS NOT NULL
        AND (
            LOWER(job_title) ~ '\\y(intern|internship|co-op|coop)\\y'
            OR LOWER(job_title) ~ '\\y(junior|jr|entry|entry-level|entry level|associate)\\y'
            OR LOWER(job_title) ~ '\\y(mid|mid-level|mid level|intermediate|level 2|ii)\\y'
            OR LOWER(job_title) ~ '\\y(senior|sr|lead|principal|staff|level 3|iii|iv)\\y'
            OR LOWER(job_title) ~ '\\y(director|vp|vice president|cfo|cto|ceo|executive)\\y'
        )
    GROUP BY detected_seniority
    ORDER BY job_count DESC
"""

# Query to find common technical terms in job descriptions that might be missing from skills
# This uses PostgreSQL's text search to find potential skills
FIND_POTENTIAL_MISSING_SKILLS = """
    WITH job_texts AS (
        SELECT
            jsearch_job_postings_key,
            jsearch_job_id,
            job_title,
            job_description,
            extracted_skills,
            LOWER(job_title || ' ' || COALESCE(job_description, '')) as full_text
        FROM staging.jsearch_job_postings
        WHERE job_description IS NOT NULL
            AND trim(job_description) != ''
            AND extracted_skills IS NOT NULL
            AND jsonb_array_length(extracted_skills) > 0
    ),
    -- Common technical terms to check for (expanded list)
    technical_terms AS (
        SELECT unnest(ARRAY[
            'postgres', 'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch',
            'cassandra', 'oracle', 'dynamodb', 'neo4j', 'couchdb', 'sqlite',
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust',
            'ruby', 'php', 'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl',
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask',
            'spring', 'asp.net', 'laravel', 'rails', 'next.js', 'nuxt', 'svelte',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ansible',
            'jenkins', 'ci/cd', 'git', 'github', 'gitlab', 'circleci', 'travis',
            'spark', 'hadoop', 'kafka', 'airflow', 'dbt', 'tableau', 'power bi',
            'looker', 'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch',
            'keras', 'machine learning', 'deep learning', 'data science',
            'data engineering', 'linux', 'unix', 'rest', 'graphql', 'microservices',
            'api', 'agile', 'scrum', 'jira', 'confluence', 'slack', 'figma',
            -- Additional common terms
            'snowflake', 'databricks', 'redshift', 'bigquery', 's3', 'ec2', 'lambda',
            'sagemaker', 'apache', 'nginx', 'rabbitmq', 'pulsar', 'flink', 'storm',
            'presto', 'trino', 'clickhouse', 'influxdb', 'timescaledb', 'cockroachdb',
            'prometheus', 'grafana', 'kibana', 'splunk', 'datadog', 'new relic',
            'terraform', 'pulumi', 'cloudformation', 'serverless', 'lambda',
            'fastapi', 'fastify', 'nestjs', 'gin', 'echo', 'fiber',
            'vue.js', 'ember', 'backbone', 'jquery', 'bootstrap', 'tailwind',
            'webpack', 'vite', 'rollup', 'esbuild', 'parcel', 'babel',
            'jest', 'mocha', 'cypress', 'playwright', 'selenium', 'pytest',
            'junit', 'testng', 'mockito', 'jasmine', 'karma', 'protractor'
        ]) as term
    )
    SELECT
        t.term,
        COUNT(DISTINCT jt.jsearch_job_postings_key) as mention_count,
        COUNT(DISTINCT CASE 
            WHEN NOT EXISTS (
                SELECT 1 
                FROM jsonb_array_elements_text(jt.extracted_skills) as skill
                WHERE LOWER(skill) = LOWER(t.term)
            )
            THEN jt.jsearch_job_postings_key 
        END) as missing_count,
        array_agg(DISTINCT jt.job_title ORDER BY jt.job_title) as sample_titles
    FROM technical_terms t
    CROSS JOIN job_texts jt
    WHERE jt.full_text LIKE '%' || t.term || '%'
    GROUP BY t.term
    HAVING COUNT(DISTINCT CASE 
        WHEN NOT EXISTS (
            SELECT 1 
            FROM jsonb_array_elements_text(jt.extracted_skills) as skill
            WHERE LOWER(skill) = LOWER(t.term)
        )
        THEN jt.jsearch_job_postings_key 
    END) > 0
    ORDER BY missing_count DESC, mention_count DESC
    LIMIT %s
"""

# Query to get jobs with specific missing skills for detailed analysis
GET_JOBS_WITH_MISSING_SKILLS = """
    SELECT
        jsearch_job_postings_key,
        jsearch_job_id,
        job_title,
        job_description,
        extracted_skills
    FROM staging.jsearch_job_postings
    WHERE job_description IS NOT NULL
        AND trim(job_description) != ''
        AND extracted_skills IS NOT NULL
        AND jsonb_array_length(extracted_skills) > 0
        AND LOWER(job_description) LIKE '%' || LOWER(%s) || '%'
        AND NOT EXISTS (
            SELECT 1 
            FROM jsonb_array_elements_text(extracted_skills) as skill
            WHERE LOWER(skill) = LOWER(%s)
        )
    ORDER BY dwh_load_timestamp DESC
    LIMIT %s
"""

# Query to get statistics about enrichment coverage
GET_ENRICHMENT_STATISTICS = """
    SELECT
        COUNT(*) as total_jobs,
        COUNT(CASE WHEN extracted_skills IS NOT NULL AND jsonb_array_length(extracted_skills) > 0 THEN 1 END) as jobs_with_skills,
        COUNT(CASE WHEN seniority_level IS NOT NULL THEN 1 END) as jobs_with_seniority,
        COUNT(CASE WHEN extracted_skills IS NOT NULL AND jsonb_array_length(extracted_skills) > 0 AND seniority_level IS NOT NULL THEN 1 END) as fully_enriched,
        ROUND(AVG(jsonb_array_length(extracted_skills)) FILTER (WHERE extracted_skills IS NOT NULL), 2) as avg_skills_per_job
    FROM staging.jsearch_job_postings
    WHERE job_description IS NOT NULL
        AND trim(job_description) != ''
"""

# Query to extract all single words from job descriptions
# We'll generate n-grams in Python for better performance
EXTRACT_WORDS_FROM_DESCRIPTIONS = """
    SELECT
        jsearch_job_postings_key,
        job_title,
        LOWER(trim(regexp_replace(word, '[^a-z0-9]', '', 'g'))) as word
    FROM staging.jsearch_job_postings,
    LATERAL regexp_split_to_table(LOWER(COALESCE(job_description, '')), '\\s+') as word
    WHERE job_description IS NOT NULL
        AND trim(job_description) != ''
        AND length(trim(regexp_replace(word, '[^a-z0-9]', '', 'g'))) >= 2
        AND trim(regexp_replace(word, '[^a-z0-9]', '', 'g')) !~ '^[0-9]+$'
"""

# Query to extract all single words from job titles
EXTRACT_WORDS_FROM_TITLES = """
    SELECT
        jsearch_job_postings_key,
        job_title,
        LOWER(trim(regexp_replace(word, '[^a-z0-9]', '', 'g'))) as word
    FROM staging.jsearch_job_postings,
    LATERAL regexp_split_to_table(LOWER(COALESCE(job_title, '')), '\\s+') as word
    WHERE job_title IS NOT NULL
        AND trim(job_title) != ''
        AND length(trim(regexp_replace(word, '[^a-z0-9]', '', 'g'))) >= 2
        AND trim(regexp_replace(word, '[^a-z0-9]', '', 'g')) !~ '^[0-9]+$'
"""

