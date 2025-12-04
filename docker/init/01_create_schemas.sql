-- Database Schema Initialization Script
-- Creates the Medallion architecture schemas: raw, staging, marts
-- This script is idempotent and safe to run multiple times

-- Create raw schema (Bronze layer)
CREATE SCHEMA IF NOT EXISTS raw;

-- Create staging schema (Silver layer)
CREATE SCHEMA IF NOT EXISTS staging;

-- Create marts schema (Gold layer)
CREATE SCHEMA IF NOT EXISTS marts;

-- Grant permissions to application user
-- Note: Replace 'app_user' with your actual application user if different
-- This assumes the user already exists; create it separately if needed
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        GRANT ALL PRIVILEGES ON SCHEMA raw TO app_user;
        GRANT ALL PRIVILEGES ON SCHEMA staging TO app_user;
        GRANT ALL PRIVILEGES ON SCHEMA marts TO app_user;
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON SCHEMA raw TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA staging TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA marts TO postgres;

-- Note: Tables within these schemas will be created and managed by dbt models
-- This script only creates the schema infrastructure

