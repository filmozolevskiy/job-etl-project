-- ============================================================
-- Resume and Cover Letter Storage Tables
-- Creates tables for user document management
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- ============================================================
-- MARTS LAYER (Gold)
-- User-managed document tables
-- ============================================================

-- User resumes table
CREATE TABLE IF NOT EXISTS marts.user_resumes (
    resume_id SERIAL PRIMARY KEY,
    user_id integer NOT NULL,
    resume_name varchar NOT NULL,
    file_path varchar NOT NULL,
    file_size integer NOT NULL,
    file_type varchar NOT NULL,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_resume_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE marts.user_resumes IS 'Stores user-uploaded resume files. Each user can have multiple resumes. Files are stored in the uploads directory structure.';

-- User cover letters table
CREATE TABLE IF NOT EXISTS marts.user_cover_letters (
    cover_letter_id SERIAL PRIMARY KEY,
    user_id integer NOT NULL,
    jsearch_job_id varchar,
    cover_letter_name varchar NOT NULL,
    cover_letter_text text,
    file_path varchar,
    is_generated boolean DEFAULT false,
    generation_prompt text,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cover_letter_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE marts.user_cover_letters IS 'Stores user cover letters. Can be text-based, file-based, or AI-generated. Cover letters can be job-specific (jsearch_job_id) or generic.';

-- Job application documents table (links documents to job applications)
CREATE TABLE IF NOT EXISTS marts.job_application_documents (
    document_id SERIAL PRIMARY KEY,
    jsearch_job_id varchar NOT NULL,
    user_id integer NOT NULL,
    resume_id integer,
    cover_letter_id integer,
    cover_letter_text text,
    user_notes text,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_app_doc_user FOREIGN KEY (user_id) REFERENCES marts.users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_app_doc_resume FOREIGN KEY (resume_id) REFERENCES marts.user_resumes(resume_id) ON DELETE SET NULL,
    CONSTRAINT fk_app_doc_cover_letter FOREIGN KEY (cover_letter_id) REFERENCES marts.user_cover_letters(cover_letter_id) ON DELETE SET NULL,
    CONSTRAINT unique_job_user_document UNIQUE (jsearch_job_id, user_id)
);

COMMENT ON TABLE marts.job_application_documents IS 'Links resumes and cover letters to specific job applications. One document set per job per user. Supports inline cover letter text or linked cover letter records.';

-- ============================================================
-- INDEXES (for performance)
-- ============================================================

-- Indexes for user_resumes
CREATE INDEX IF NOT EXISTS idx_user_resumes_user_id 
    ON marts.user_resumes(user_id);
    
CREATE INDEX IF NOT EXISTS idx_user_resumes_created_at 
    ON marts.user_resumes(created_at DESC);

-- Indexes for user_cover_letters
CREATE INDEX IF NOT EXISTS idx_user_cover_letters_user_id 
    ON marts.user_cover_letters(user_id);
    
CREATE INDEX IF NOT EXISTS idx_user_cover_letters_job_id 
    ON marts.user_cover_letters(jsearch_job_id);
    
CREATE INDEX IF NOT EXISTS idx_user_cover_letters_created_at 
    ON marts.user_cover_letters(created_at DESC);

-- Indexes for job_application_documents
CREATE INDEX IF NOT EXISTS idx_job_app_docs_job_id 
    ON marts.job_application_documents(jsearch_job_id);
    
CREATE INDEX IF NOT EXISTS idx_job_app_docs_user_id 
    ON marts.job_application_documents(user_id);
    
CREATE INDEX IF NOT EXISTS idx_job_app_docs_resume_id 
    ON marts.job_application_documents(resume_id);

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

-- Grant permissions to application user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'app_user') THEN
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.user_resumes TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.user_cover_letters TO app_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE marts.job_application_documents TO app_user';
        -- Grant sequence permissions for SERIAL columns
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.user_resumes_resume_id_seq TO app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.user_cover_letters_cover_letter_id_seq TO app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE marts.job_application_documents_document_id_seq TO app_user';
    END IF;
END $$;

-- Grant permissions to postgres user (for Docker default)
GRANT ALL PRIVILEGES ON TABLE marts.user_resumes TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.user_cover_letters TO postgres;
GRANT ALL PRIVILEGES ON TABLE marts.job_application_documents TO postgres;

