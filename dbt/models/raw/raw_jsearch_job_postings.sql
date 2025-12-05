{{ config(
    materialized='ephemeral',
    schema='raw'
) }}

-- Raw layer table for JSearch job postings
-- Stores raw JSON payloads from JSearch API with minimal transformation
-- This table is populated by the Source Extractor service
-- 
-- IMPORTANT: Table structure is created by docker/init/02_create_tables.sql
-- This model exists for dbt lineage only (ephemeral = no database object created)

select * from raw.jsearch_job_postings
