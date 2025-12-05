{{ config(
    materialized='ephemeral',
    schema='raw'
) }}

-- Raw layer table for Glassdoor company data
-- Stores raw JSON payloads from Glassdoor API with minimal transformation
-- This table is populated by the Company Extraction service
--
-- IMPORTANT: Table structure is created by docker/init/02_create_tables.sql
-- This model exists for dbt lineage only (ephemeral = no database object created)

select * from raw.glassdoor_companies
