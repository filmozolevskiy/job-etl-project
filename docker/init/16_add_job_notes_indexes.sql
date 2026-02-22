-- ============================================================
-- Add Indexes for Job Notes Performance
-- Optimizes queries that filter by jsearch_job_id and user_id
-- ============================================================

-- Index for efficient note retrieval by job and user
CREATE INDEX IF NOT EXISTS idx_job_notes_job_user 
ON marts.job_notes(jsearch_job_id, user_id);

-- Index for efficient note retrieval by user (for user-centric queries)
CREATE INDEX IF NOT EXISTS idx_job_notes_user 
ON marts.job_notes(user_id);

-- Index for efficient note retrieval by note_id (for authorization checks)
CREATE INDEX IF NOT EXISTS idx_job_notes_id_user 
ON marts.job_notes(note_id, user_id);

COMMENT ON INDEX marts.idx_job_notes_job_user IS 'Optimizes queries that filter notes by job and user (e.g., GET_NOTES_BY_JOB_AND_USER)';
COMMENT ON INDEX marts.idx_job_notes_user IS 'Optimizes queries that filter notes by user (e.g., user-centric note listings)';
COMMENT ON INDEX marts.idx_job_notes_id_user IS 'Optimizes authorization checks when retrieving/updating notes by ID';
