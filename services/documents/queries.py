"""SQL queries for document management (resumes, cover letters, job application documents)."""

# ============================================================
# Resume Queries
# ============================================================

# Insert a new resume
INSERT_RESUME = """
    INSERT INTO marts.user_resumes (user_id, resume_name, file_path, file_size, file_type, created_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING resume_id, user_id, resume_name, file_path, file_size, file_type, created_at, updated_at
"""

# Get all resumes for a user
GET_USER_RESUMES = """
    SELECT resume_id, user_id, resume_name, file_path, file_size, file_type, created_at, updated_at
    FROM marts.user_resumes
    WHERE user_id = %s
    ORDER BY created_at DESC
"""

# Get a resume by ID (with user validation)
GET_RESUME_BY_ID = """
    SELECT resume_id, user_id, resume_name, file_path, file_size, file_type, created_at, updated_at
    FROM marts.user_resumes
    WHERE resume_id = %s AND user_id = %s
"""

# Update a resume (name only)
UPDATE_RESUME = """
    UPDATE marts.user_resumes
    SET resume_name = %s, updated_at = CURRENT_TIMESTAMP
    WHERE resume_id = %s AND user_id = %s
    RETURNING resume_id, user_id, resume_name, file_path, file_size, file_type, created_at, updated_at
"""

# Delete a resume
DELETE_RESUME = """
    DELETE FROM marts.user_resumes
    WHERE resume_id = %s AND user_id = %s
    RETURNING resume_id, file_path
"""

# ============================================================
# Cover Letter Queries
# ============================================================

# Insert a new cover letter
INSERT_COVER_LETTER = """
    INSERT INTO marts.user_cover_letters (
        user_id, jsearch_job_id, cover_letter_name, cover_letter_text,
        file_path, is_generated, generation_prompt, created_at, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING cover_letter_id, user_id, jsearch_job_id, cover_letter_name,
              cover_letter_text, file_path, is_generated, generation_prompt, created_at, updated_at
"""

# Get all cover letters for a user (optionally filtered by job)
GET_USER_COVER_LETTERS = """
    SELECT cover_letter_id, user_id, jsearch_job_id, cover_letter_name,
           cover_letter_text, file_path, is_generated, generation_prompt, created_at, updated_at
    FROM marts.user_cover_letters
    WHERE user_id = %s
    AND (%s IS NULL OR jsearch_job_id = %s)
    ORDER BY created_at DESC
"""

# Get a cover letter by ID (with user validation)
GET_COVER_LETTER_BY_ID = """
    SELECT cover_letter_id, user_id, jsearch_job_id, cover_letter_name,
           cover_letter_text, file_path, is_generated, generation_prompt, created_at, updated_at
    FROM marts.user_cover_letters
    WHERE cover_letter_id = %s AND user_id = %s
"""

# Update a cover letter
UPDATE_COVER_LETTER = """
    UPDATE marts.user_cover_letters
    SET cover_letter_name = COALESCE(%s, cover_letter_name),
        cover_letter_text = COALESCE(%s, cover_letter_text),
        file_path = COALESCE(%s, file_path),
        updated_at = CURRENT_TIMESTAMP
    WHERE cover_letter_id = %s AND user_id = %s
    RETURNING cover_letter_id, user_id, jsearch_job_id, cover_letter_name,
              cover_letter_text, file_path, is_generated, generation_prompt, created_at, updated_at
"""

# Delete a cover letter
DELETE_COVER_LETTER = """
    DELETE FROM marts.user_cover_letters
    WHERE cover_letter_id = %s AND user_id = %s
    RETURNING cover_letter_id, file_path
"""

# ============================================================
# Job Application Document Queries
# ============================================================

# Upsert job application document (insert or update)
UPSERT_JOB_APPLICATION_DOCUMENT = """
    INSERT INTO marts.job_application_documents (
        jsearch_job_id, user_id, resume_id, cover_letter_id,
        cover_letter_text, user_notes, created_at, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (jsearch_job_id, user_id)
    DO UPDATE SET
        resume_id = COALESCE(EXCLUDED.resume_id, job_application_documents.resume_id),
        cover_letter_id = COALESCE(EXCLUDED.cover_letter_id, job_application_documents.cover_letter_id),
        cover_letter_text = COALESCE(EXCLUDED.cover_letter_text, job_application_documents.cover_letter_text),
        user_notes = COALESCE(EXCLUDED.user_notes, job_application_documents.user_notes),
        updated_at = CURRENT_TIMESTAMP
    RETURNING document_id, jsearch_job_id, user_id, resume_id, cover_letter_id,
              cover_letter_text, user_notes, created_at, updated_at
"""

# Get job application document by job and user
GET_JOB_APPLICATION_DOCUMENT = """
    SELECT
        jad.document_id, jad.jsearch_job_id, jad.user_id,
        jad.resume_id, jad.cover_letter_id, jad.cover_letter_text,
        jad.user_notes, jad.created_at, jad.updated_at,
        ur.resume_name, ur.file_path as resume_file_path, ur.file_type as resume_file_type,
        ucl.cover_letter_name, ucl.file_path as cover_letter_file_path,
        ucl.cover_letter_text as cover_letter_text_full, ucl.is_generated
    FROM marts.job_application_documents jad
    LEFT JOIN marts.user_resumes ur ON jad.resume_id = ur.resume_id
    LEFT JOIN marts.user_cover_letters ucl ON jad.cover_letter_id = ucl.cover_letter_id
    WHERE jad.jsearch_job_id = %s AND jad.user_id = %s
"""

# Update job application document
UPDATE_JOB_APPLICATION_DOCUMENT = """
    UPDATE marts.job_application_documents
    SET resume_id = COALESCE(%s, resume_id),
        cover_letter_id = COALESCE(%s, cover_letter_id),
        cover_letter_text = COALESCE(%s, cover_letter_text),
        user_notes = COALESCE(%s, user_notes),
        updated_at = CURRENT_TIMESTAMP
    WHERE document_id = %s AND user_id = %s
    RETURNING document_id, jsearch_job_id, user_id, resume_id, cover_letter_id,
              cover_letter_text, user_notes, created_at, updated_at
"""

# Delete job application document
DELETE_JOB_APPLICATION_DOCUMENT = """
    DELETE FROM marts.job_application_documents
    WHERE document_id = %s AND user_id = %s
    RETURNING document_id
"""

