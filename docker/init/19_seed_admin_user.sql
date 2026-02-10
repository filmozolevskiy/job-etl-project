-- ============================================================
-- Seed Admin User
-- Creates a default admin user for all environments
-- ============================================================

-- Insert admin user if not exists
-- Password hash for 'admin123'
INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
VALUES (
    'admin', 
    'admin@example.com', 
    '$2b$12$9GEneHVg9uMvJ4OGCwdhh.0.C6ScxQYZzYBPhEnzlKnWjYzF0JK1S', 
    'admin', 
    CURRENT_TIMESTAMP, 
    CURRENT_TIMESTAMP
)
ON CONFLICT (username) DO UPDATE 
SET password_hash = EXCLUDED.password_hash,
    role = 'admin',
    updated_at = CURRENT_TIMESTAMP;

-- Also ensure email uniqueness if username conflict didn't trigger but email exists
INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
VALUES (
    'admin', 
    'admin@example.com', 
    '$2b$12$9GEneHVg9uMvJ4OGCwdhh.0.C6ScxQYZzYBPhEnzlKnWjYzF0JK1S', 
    'admin', 
    CURRENT_TIMESTAMP, 
    CURRENT_TIMESTAMP
)
ON CONFLICT (email) DO UPDATE 
SET password_hash = EXCLUDED.password_hash,
    role = 'admin',
    updated_at = CURRENT_TIMESTAMP;
