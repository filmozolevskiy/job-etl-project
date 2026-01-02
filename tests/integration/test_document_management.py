"""
Integration tests for document management (resumes, cover letters, job application documents).

Tests end-to-end workflows:
1. Upload resume → link to job → retrieve → download
2. Create cover letter (text and file) → link to job → retrieve
3. Update job application documents
"""

import tempfile
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from services.documents import (
    CoverLetterService,
    DocumentService,
    LocalStorageService,
    ResumeService,
)
from services.shared import PostgreSQLDatabase

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_storage_dir():
    """Create a temporary directory for file storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_user_id(test_database):
    """Create a test user and return user_id."""
    # Use psycopg2 directly with autocommit to ensure user is committed
    import psycopg2

    conn = psycopg2.connect(test_database)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # Delete any existing test user first (in case of leftover data)
            cur.execute("DELETE FROM marts.users WHERE username = 'test_user'")

            # Create new test user
            cur.execute(
                """
                INSERT INTO marts.users (username, email, password_hash, role)
                VALUES ('test_user', 'test@example.com', 'hashed_password', 'user')
                RETURNING user_id
                """
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create test user")
            user_id = result[0]

            # Verify user was created
            cur.execute("SELECT user_id FROM marts.users WHERE user_id = %s", (user_id,))
            verify = cur.fetchone()
            if not verify:
                raise ValueError(f"Test user {user_id} was not created successfully")

            yield user_id
    finally:
        conn.close()

        # Note: Don't delete user here - test_database fixture handles cleanup via truncate


@pytest.fixture
def test_job_id(test_database):
    """Create a test job and return jsearch_job_id."""
    # We need a job in fact_jobs for the test
    # For simplicity, we'll use a mock job_id
    return "test_job_123"


@pytest.fixture
def resume_service(test_database, test_storage_dir):
    """Create ResumeService with test database and storage."""
    storage = LocalStorageService(base_dir=test_storage_dir)
    return ResumeService(
        database=PostgreSQLDatabase(connection_string=test_database),
        storage_service=storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


@pytest.fixture
def cover_letter_service(test_database, test_storage_dir):
    """Create CoverLetterService with test database and storage."""
    storage = LocalStorageService(base_dir=test_storage_dir)
    return CoverLetterService(
        database=PostgreSQLDatabase(connection_string=test_database),
        storage_service=storage,
        max_file_size=5 * 1024 * 1024,
        allowed_extensions=["pdf", "docx"],
    )


@pytest.fixture
def document_service(test_database):
    """Create DocumentService with test database."""
    return DocumentService(database=PostgreSQLDatabase(connection_string=test_database))


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    file_content = b"%PDF-1.4\nsample pdf content for testing"
    file = FileStorage(
        stream=BytesIO(file_content),
        filename="test_resume.pdf",
        content_type="application/pdf",
    )
    return file


class TestDocumentManagementIntegration:
    """Integration tests for document management workflows."""

    def test_upload_resume_and_link_to_job(
        self, resume_service, document_service, test_user_id, test_job_id, sample_pdf_file
    ):
        """Test complete workflow: upload resume → link to job → retrieve."""
        # Upload resume
        resume = resume_service.upload_resume(
            user_id=test_user_id, file=sample_pdf_file, resume_name="Test Resume"
        )
        assert resume["resume_id"] is not None
        assert resume["resume_name"] == "Test Resume"

        # Link to job
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            resume_id=resume["resume_id"],
        )
        assert doc["resume_id"] == resume["resume_id"]

        # Retrieve document
        retrieved_doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        assert retrieved_doc is not None
        assert retrieved_doc["resume_id"] == resume["resume_id"]

        # Download resume
        sample_pdf_file.seek(0)  # Reset file pointer
        original_content = sample_pdf_file.read()
        content, filename, mime_type = resume_service.download_resume(
            resume_id=resume["resume_id"], user_id=test_user_id
        )
        assert content == original_content
        assert "Test Resume" in filename
        assert mime_type == "application/pdf"

    def test_create_text_cover_letter_and_link(
        self, cover_letter_service, document_service, test_user_id, test_job_id
    ):
        """Test creating text-based cover letter and linking to job."""
        # Create text cover letter
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Test Cover Letter",
            cover_letter_text="Dear Hiring Manager,\n\nI am interested...",
            jsearch_job_id=test_job_id,
        )
        assert cover_letter["cover_letter_id"] is not None
        assert cover_letter["cover_letter_text"] == "Dear Hiring Manager,\n\nI am interested..."

        # Link to job
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            cover_letter_id=cover_letter["cover_letter_id"],
        )
        assert doc["cover_letter_id"] == cover_letter["cover_letter_id"]

        # Retrieve document
        retrieved_doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        assert retrieved_doc is not None
        assert retrieved_doc["cover_letter_id"] == cover_letter["cover_letter_id"]

    def test_upload_cover_letter_file_and_link(
        self, cover_letter_service, document_service, test_user_id, test_job_id, sample_pdf_file
    ):
        """Test uploading cover letter file and linking to job."""
        # Upload cover letter file
        cover_letter = cover_letter_service.upload_cover_letter_file(
            user_id=test_user_id,
            file=sample_pdf_file,
            cover_letter_name="Test Cover Letter File",
            jsearch_job_id=test_job_id,
        )
        assert cover_letter["cover_letter_id"] is not None
        assert cover_letter["file_path"] is not None

        # Link to job
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            cover_letter_id=cover_letter["cover_letter_id"],
        )
        assert doc["cover_letter_id"] == cover_letter["cover_letter_id"]

    def test_update_job_application_document(self, document_service, test_user_id, test_job_id):
        """Test updating job application document."""
        # Create initial document
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            user_notes="Initial notes",
        )
        assert doc["user_notes"] == "Initial notes"

        # Update document
        updated_doc = document_service.update_job_application_document(
            document_id=doc["document_id"],
            user_id=test_user_id,
            user_notes="Updated notes",
        )
        assert updated_doc["user_notes"] == "Updated notes"

        # Verify update
        retrieved_doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        assert retrieved_doc["user_notes"] == "Updated notes"

    def test_delete_resume_removes_file(
        self, resume_service, test_user_id, sample_pdf_file, test_storage_dir
    ):
        """Test that deleting resume also removes the file."""
        # Upload resume
        resume = resume_service.upload_resume(
            user_id=test_user_id, file=sample_pdf_file, resume_name="Test Resume"
        )
        file_path = resume["file_path"]

        # Verify file exists
        storage = LocalStorageService(base_dir=test_storage_dir)
        assert storage.file_exists(file_path)

        # Delete resume
        result = resume_service.delete_resume(resume_id=resume["resume_id"], user_id=test_user_id)
        assert result is True

        # Verify file is deleted
        assert not storage.file_exists(file_path)

    def test_get_user_resumes_list(self, resume_service, test_user_id, sample_pdf_file):
        """Test getting list of all user's resumes."""
        # Upload multiple resumes
        resume_service.upload_resume(
            user_id=test_user_id, file=sample_pdf_file, resume_name="Resume 1"
        )
        resume_service.upload_resume(
            user_id=test_user_id, file=sample_pdf_file, resume_name="Resume 2"
        )

        # Get all resumes
        resumes = resume_service.get_user_resumes(user_id=test_user_id)
        assert len(resumes) >= 2
        resume_names = [r["resume_name"] for r in resumes]
        assert "Resume 1" in resume_names
        assert "Resume 2" in resume_names

    def test_inline_cover_letter_text_workflow(self, document_service, test_user_id, test_job_id):
        """Test workflow with inline cover letter text (stored in job_application_documents)."""
        # Create document with inline text
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            cover_letter_text="This is inline cover letter text for the job",
            user_notes="Application notes",
        )

        assert doc["cover_letter_text"] == "This is inline cover letter text for the job"
        assert doc.get("cover_letter_id") is None

        # Retrieve document
        retrieved_doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        assert retrieved_doc["cover_letter_text"] == "This is inline cover letter text for the job"
        assert retrieved_doc["user_notes"] == "Application notes"

        # Update inline text
        updated_doc = document_service.update_job_application_document(
            document_id=doc["document_id"],
            user_id=test_user_id,
            cover_letter_text="Updated inline text",
        )
        assert updated_doc["cover_letter_text"] == "Updated inline text"

    def test_mixed_document_types_workflow(
        self,
        resume_service,
        cover_letter_service,
        document_service,
        test_user_id,
        test_job_id,
        sample_pdf_file,
        test_storage_dir,
    ):
        """Test workflow with both resume and cover letter linked to same job."""
        # Upload resume
        resume = resume_service.upload_resume(
            user_id=test_user_id, file=sample_pdf_file, resume_name="Test Resume"
        )

        # Create text-based cover letter
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Test Cover Letter",
            cover_letter_text="Cover letter text",
            jsearch_job_id=test_job_id,
        )

        # Link both to job
        doc = document_service.link_documents_to_job(
            jsearch_job_id=test_job_id,
            user_id=test_user_id,
            resume_id=resume["resume_id"],
            cover_letter_id=cover_letter["cover_letter_id"],
            user_notes="Both documents linked",
        )

        assert doc["resume_id"] == resume["resume_id"]
        assert doc["cover_letter_id"] == cover_letter["cover_letter_id"]
        assert doc["user_notes"] == "Both documents linked"

        # Retrieve and verify
        retrieved_doc = document_service.get_job_application_document(
            jsearch_job_id=test_job_id, user_id=test_user_id
        )
        assert retrieved_doc["resume_id"] == resume["resume_id"]
        assert retrieved_doc["cover_letter_id"] == cover_letter["cover_letter_id"]
        assert retrieved_doc["user_notes"] == "Both documents linked"

    def test_get_user_cover_letters_filtered_by_job(
        self, cover_letter_service, test_user_id, test_storage_dir
    ):
        """Test getting cover letters filtered by job ID."""
        job1_id = "test_job_1"
        job2_id = "test_job_2"

        # Create cover letters for different jobs
        cl1 = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="CL for Job 1",
            cover_letter_text="Text 1",
            jsearch_job_id=job1_id,
        )

        cl2 = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="CL for Job 2",
            cover_letter_text="Text 2",
            jsearch_job_id=job2_id,
        )

        cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Generic CL",
            cover_letter_text="Text 3",
            jsearch_job_id=None,
        )

        # Get all cover letters
        all_cls = cover_letter_service.get_user_cover_letters(user_id=test_user_id)
        assert len(all_cls) >= 3

        # Get cover letters for job1
        job1_cls = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, jsearch_job_id=job1_id
        )
        assert len(job1_cls) >= 1
        assert any(cl["cover_letter_id"] == cl1["cover_letter_id"] for cl in job1_cls)

        # Get cover letters for job2
        job2_cls = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, jsearch_job_id=job2_id
        )
        assert len(job2_cls) >= 1
        assert any(cl["cover_letter_id"] == cl2["cover_letter_id"] for cl in job2_cls)

    def test_documents_uploaded_from_job_details_not_in_documents_section(
        self, resume_service, cover_letter_service, test_user_id, test_job_id, sample_pdf_file
    ):
        """Test that documents uploaded from job details are not in documents section."""
        # Upload resume from job details
        resume = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Resume from Job Details",
            in_documents_section=False,
        )

        # Create cover letter from job details
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Cover Letter from Job Details",
            cover_letter_text="Text content",
            jsearch_job_id=test_job_id,
            in_documents_section=False,
        )

        # Verify they are not in documents section
        resumes_in_section = resume_service.get_user_resumes(
            user_id=test_user_id, in_documents_section=True
        )
        cover_letters_in_section = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )

        assert len(resumes_in_section) == 0
        assert len(cover_letters_in_section) == 0

        # But they should exist when getting all documents
        all_resumes = resume_service.get_user_resumes(user_id=test_user_id)
        all_cover_letters = cover_letter_service.get_user_cover_letters(user_id=test_user_id)

        assert len(all_resumes) >= 1
        assert len(all_cover_letters) >= 1
        assert any(r["resume_id"] == resume["resume_id"] for r in all_resumes)
        assert any(  # noqa: E501
            cl["cover_letter_id"] == cover_letter["cover_letter_id"] for cl in all_cover_letters
        )

    def test_only_documents_section_documents_in_job_attachment_dropdowns(
        self, resume_service, cover_letter_service, test_user_id, sample_pdf_file
    ):
        """Test that only documents from documents section appear in job attachment dropdowns."""
        # Create documents in documents section
        resume_in_section = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Resume in Section",
            in_documents_section=True,
        )

        cover_letter_in_section = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Cover Letter in Section",
            cover_letter_text="Text",
            in_documents_section=True,
        )

        # Create documents NOT in documents section (from job details)
        resume_not_in_section = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Resume from Job",
            in_documents_section=False,
        )

        cover_letter_not_in_section = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Cover Letter from Job",
            cover_letter_text="Text",
            in_documents_section=False,
        )

        # Get documents for job attachment (should only return in_documents_section=True)
        resumes_for_job = resume_service.get_user_resumes(
            user_id=test_user_id, in_documents_section=True
        )
        cover_letters_for_job = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )

        # Verify only documents in section appear
        resume_ids = [r["resume_id"] for r in resumes_for_job]
        cover_letter_ids = [cl["cover_letter_id"] for cl in cover_letters_for_job]

        assert resume_in_section["resume_id"] in resume_ids
        assert resume_not_in_section["resume_id"] not in resume_ids
        assert cover_letter_in_section["cover_letter_id"] in cover_letter_ids
        assert cover_letter_not_in_section["cover_letter_id"] not in cover_letter_ids
