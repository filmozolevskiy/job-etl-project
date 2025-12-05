{{ config(
    materialized='ephemeral',
    schema='staging'
) }}

-- Staging layer: Company enrichment queue
-- Tracks which companies need Glassdoor enrichment
-- This table is populated by the Company Extraction service and updated as enrichment progresses
--
-- IMPORTANT: Table structure is created by docker/init/02_create_tables.sql
-- This model exists for dbt lineage only (ephemeral = no database object created)

select * from staging.company_enrichment_queue
