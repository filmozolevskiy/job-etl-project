# SQL queries for staging management service

GET_ALL_SLOTS = """
    SELECT * FROM marts.staging_slots
    ORDER BY slot_id ASC
"""

GET_SLOT_BY_ID = """
    SELECT * FROM marts.staging_slots
    WHERE slot_id = %s
"""

UPDATE_SLOT_STATUS = """
    UPDATE marts.staging_slots
    SET status = %s,
        owner = %s,
        branch = %s,
        issue_id = %s,
        deployed_at = %s,
        purpose = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE slot_id = %s
"""

UPDATE_SLOT_HEALTH = """
    UPDATE marts.staging_slots
    SET health_status = %s,
        last_health_check_at = %s,
        metadata = metadata || %s::jsonb,
        updated_at = CURRENT_TIMESTAMP
    WHERE slot_id = %s
"""

RELEASE_SLOT = """
    UPDATE marts.staging_slots
    SET status = 'Available',
        owner = NULL,
        branch = NULL,
        issue_id = NULL,
        deployed_at = NULL,
        purpose = NULL,
        health_status = 'Unknown',
        updated_at = CURRENT_TIMESTAMP
    WHERE slot_id = %s
"""
