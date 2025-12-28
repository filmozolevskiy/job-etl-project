-- ============================================================
-- Migration Script: Add User Authentication
-- This script migrates existing data to support user authentication
-- Run this after 02_create_tables.sql
-- ============================================================

-- Note: The tables (users, job_notes) and user_id column should already exist
-- from 02_create_tables.sql. This script handles data migration only.

-- Create default admin user (password: admin - CHANGE IN PRODUCTION!)
-- The password hash is for 'admin' - users should change this on first login
-- Using bcrypt hash: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYq1qL4F2Vy
-- To generate a new hash, use: python -c "import bcrypt; print(bcrypt.hashpw('yourpassword'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'))"
INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
SELECT 'admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYq1qL4F2Vy', 'admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM marts.users WHERE username = 'admin')
RETURNING user_id;

-- Set existing profiles' user_id to admin user
-- Only update profiles that don't already have a user_id
UPDATE marts.profile_preferences
SET user_id = (SELECT user_id FROM marts.users WHERE username = 'admin' LIMIT 1)
WHERE user_id IS NULL
    AND EXISTS (SELECT 1 FROM marts.users WHERE username = 'admin');

-- Note: If there are existing profiles and no admin user was created above,
-- the profiles will remain with user_id = NULL, which should be handled
-- by application logic (e.g., deny access or assign to admin)

