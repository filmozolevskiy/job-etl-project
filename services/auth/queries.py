"""SQL queries for authentication and user management."""

# Query to get user by username
GET_USER_BY_USERNAME = """
    SELECT
        user_id,
        username,
        email,
        password_hash,
        role,
        created_at,
        updated_at,
        last_login
    FROM marts.users
    WHERE username = %s
"""

# Query to get user by email
GET_USER_BY_EMAIL = """
    SELECT
        user_id,
        username,
        email,
        password_hash,
        role,
        created_at,
        updated_at,
        last_login
    FROM marts.users
    WHERE email = %s
"""

# Query to get user by ID
GET_USER_BY_ID = """
    SELECT
        user_id,
        username,
        email,
        password_hash,
        role,
        created_at,
        updated_at,
        last_login
    FROM marts.users
    WHERE user_id = %s
"""

# Query to create a new user
INSERT_USER = """
    INSERT INTO marts.users (username, email, password_hash, role, created_at, updated_at)
    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING user_id
"""

# Query to update user's last login timestamp
UPDATE_USER_LAST_LOGIN = """
    UPDATE marts.users
    SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE user_id = %s
"""
