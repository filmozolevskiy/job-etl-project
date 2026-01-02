-- ============================================================
-- Add in_documents_section flag to document tables
-- Adds boolean column to track documents in documents section
-- This script is idempotent and safe to run multiple times
-- ============================================================

-- Add in_documents_section column to user_resumes table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'user_resumes' 
        AND column_name = 'in_documents_section'
    ) THEN
        ALTER TABLE marts.user_resumes 
        ADD COLUMN in_documents_section BOOLEAN DEFAULT false NOT NULL;
        
        COMMENT ON COLUMN marts.user_resumes.in_documents_section IS 
            'Indicates if this resume is in the documents section. Only documents with this flag set to true will appear in job attachment dropdowns.';
    END IF;
END $$;

-- Add in_documents_section column to user_cover_letters table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'user_cover_letters' 
        AND column_name = 'in_documents_section'
    ) THEN
        ALTER TABLE marts.user_cover_letters 
        ADD COLUMN in_documents_section BOOLEAN DEFAULT false NOT NULL;
        
        COMMENT ON COLUMN marts.user_cover_letters.in_documents_section IS 
            'Indicates if this cover letter is in the documents section. Only documents with this flag set to true will appear in job attachment dropdowns.';
    END IF;
END $$;

-- Create indexes for efficient filtering
CREATE INDEX IF NOT EXISTS idx_user_resumes_in_documents_section 
    ON marts.user_resumes(user_id, in_documents_section) 
    WHERE in_documents_section = true;

CREATE INDEX IF NOT EXISTS idx_user_cover_letters_in_documents_section 
    ON marts.user_cover_letters(user_id, in_documents_section) 
    WHERE in_documents_section = true;

