"""
Integration tests for documents page functionality.

Tests:
1. Documents page route accessibility
2. Resume upload from documents page (sets in_documents_section=True)
3. Resume deletion from documents page
4. Cover letter creation from documents page (sets in_documents_section=True)
5. Cover letter deletion from documents page
6. Verify documents uploaded from job details don't appear in documents section
7. Verify only documents from documents section appear in job attachment dropdowns
"""

import tempfile
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from services.documents import (
    CoverLetterService,
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
    import psycopg2

    conn = psycopg2.connect(test_database)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM marts.users WHERE username = 'test_user_docs'")

            cur.execute(
                """
                INSERT INTO marts.users (username, email, password_hash, role)
                VALUES ('test_user_docs', 'test_docs@example.com', 'hashed_password', 'user')
                RETURNING user_id
                """
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("Failed to create test user")
            user_id = result[0]
            yield user_id
    finally:
        conn.close()


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
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    # Create a minimal PDF file content
    pdf_content = (  # noqa: E501
        b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n"
        b"<<\n/Root 1 0 R\n>>\n%%EOF"
    )
    return FileStorage(
        stream=BytesIO(pdf_content),
        filename="test_resume.pdf",
        content_type="application/pdf",
    )


class TestDocumentsPage:
    """Integration tests for documents page functionality."""

    def test_upload_resume_from_documents_section(
        self, resume_service, test_user_id, sample_pdf_file
    ):
        """Test uploading resume from documents page sets in_documents_section=True."""
        resume = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Test Resume from Documents",
            in_documents_section=True,
        )

        assert resume["resume_id"] is not None
        assert resume["resume_name"] == "Test Resume from Documents"
        assert resume["in_documents_section"] is True

        # Verify it appears when filtering by in_documents_section=True
        resumes = resume_service.get_user_resumes(user_id=test_user_id, in_documents_section=True)
        assert len(resumes) == 1
        assert resumes[0]["resume_id"] == resume["resume_id"]

    def test_upload_resume_from_job_details_not_in_documents_section(
        self, resume_service, test_user_id, sample_pdf_file
    ):
        """Test uploading resume from job details sets in_documents_section=False."""
        resume = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Test Resume from Job Details",
            in_documents_section=False,
        )

        assert resume["resume_id"] is not None
        assert resume["in_documents_section"] is False

        # Verify it does NOT appear when filtering by in_documents_section=True
        resumes = resume_service.get_user_resumes(user_id=test_user_id, in_documents_section=True)
        assert len(resumes) == 0

        # But it should appear when getting all resumes
        all_resumes = resume_service.get_user_resumes(user_id=test_user_id)
        assert len(all_resumes) == 1
        assert all_resumes[0]["resume_id"] == resume["resume_id"]

    def test_delete_resume_from_documents_section(
        self, resume_service, test_user_id, sample_pdf_file
    ):
        """Test deleting resume from documents section."""
        # Upload resume to documents section
        resume = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Resume to Delete",
            in_documents_section=True,
        )

        # Verify it exists
        resumes = resume_service.get_user_resumes(user_id=test_user_id, in_documents_section=True)
        assert len(resumes) == 1

        # Delete it
        result = resume_service.delete_resume(resume_id=resume["resume_id"], user_id=test_user_id)
        assert result is True

        # Verify it's gone
        resumes = resume_service.get_user_resumes(user_id=test_user_id, in_documents_section=True)
        assert len(resumes) == 0

    def test_create_cover_letter_from_documents_section(self, cover_letter_service, test_user_id):
        """Test creating cover letter from documents page sets in_documents_section=True."""
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Test Cover Letter from Documents",
            cover_letter_text="This is a test cover letter.",
            in_documents_section=True,
        )

        assert cover_letter["cover_letter_id"] is not None
        assert cover_letter["cover_letter_name"] == "Test Cover Letter from Documents"
        assert cover_letter["in_documents_section"] is True

        # Verify it appears when filtering by in_documents_section=True
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )
        assert len(cover_letters) == 1
        assert cover_letters[0]["cover_letter_id"] == cover_letter["cover_letter_id"]

    def test_create_cover_letter_from_job_details_not_in_documents_section(
        self, cover_letter_service, test_user_id
    ):
        """Test creating cover letter from job details sets in_documents_section=False."""
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Test Cover Letter from Job Details",
            cover_letter_text="This is a test cover letter.",
            jsearch_job_id="test_job_123",
            in_documents_section=False,
        )

        assert cover_letter["cover_letter_id"] is not None
        assert cover_letter["in_documents_section"] is False

        # Verify it does NOT appear when filtering by in_documents_section=True
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )
        assert len(cover_letters) == 0

        # But it should appear when getting all cover letters
        all_cover_letters = cover_letter_service.get_user_cover_letters(user_id=test_user_id)
        assert len(all_cover_letters) == 1
        assert all_cover_letters[0]["cover_letter_id"] == cover_letter["cover_letter_id"]

    def test_delete_cover_letter_from_documents_section(self, cover_letter_service, test_user_id):
        """Test deleting cover letter from documents section."""
        # Create cover letter in documents section
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Cover Letter to Delete",
            cover_letter_text="This will be deleted.",
            in_documents_section=True,
        )

        # Verify it exists
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )
        assert len(cover_letters) == 1

        # Delete it
        result = cover_letter_service.delete_cover_letter(
            cover_letter_id=cover_letter["cover_letter_id"], user_id=test_user_id
        )
        assert result is True

        # Verify it's gone
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )
        assert len(cover_letters) == 0

    def test_only_documents_section_resumes_appear_in_job_attachment(
        self, resume_service, test_user_id, sample_pdf_file
    ):
        """Test that only resumes with in_documents_section=True appear in job attachments."""  # noqa: E501
        # Upload resume to documents section
        resume_in_section = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Resume in Section",
            in_documents_section=True,
        )

        # Upload resume from job details (not in section)
        resume_not_in_section = resume_service.upload_resume(
            user_id=test_user_id,
            file=sample_pdf_file,
            resume_name="Resume from Job Details",
            in_documents_section=False,
        )

        # Get resumes for job attachment (should only return in_documents_section=True)
        resumes_for_job = resume_service.get_user_resumes(
            user_id=test_user_id, in_documents_section=True
        )

        assert len(resumes_for_job) == 1
        assert resumes_for_job[0]["resume_id"] == resume_in_section["resume_id"]
        assert resumes_for_job[0]["resume_id"] != resume_not_in_section["resume_id"]

    def test_only_documents_section_cover_letters_appear_in_job_attachment(
        self, cover_letter_service, test_user_id
    ):
        """Test that only cover letters with in_documents_section=True appear in job attachments."""  # noqa: E501
        # Create cover letter in documents section
        cl_in_section = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Cover Letter in Section",
            cover_letter_text="Text 1",
            in_documents_section=True,
        )

        # Create cover letter from job details (not in section)
        cl_not_in_section = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Cover Letter from Job Details",
            cover_letter_text="Text 2",
            jsearch_job_id="test_job_123",
            in_documents_section=False,
        )

        # Get cover letters for job attachment (should only return in_documents_section=True)
        cover_letters_for_job = cover_letter_service.get_user_cover_letters(
            user_id=test_user_id, in_documents_section=True
        )

        assert len(cover_letters_for_job) == 1
        assert cover_letters_for_job[0]["cover_letter_id"] == cl_in_section["cover_letter_id"]
        assert cover_letters_for_job[0]["cover_letter_id"] != cl_not_in_section["cover_letter_id"]

    def test_delete_nonexistent_resume(self, resume_service, test_user_id):
        """Test deleting a non-existent resume returns False."""
        result = resume_service.delete_resume(resume_id=99999, user_id=test_user_id)
        assert result is False

    def test_delete_nonexistent_cover_letter(self, cover_letter_service, test_user_id):
        """Test deleting a non-existent cover letter returns False."""
        result = cover_letter_service.delete_cover_letter(
            cover_letter_id=99999, user_id=test_user_id
        )
        assert result is False

    def test_get_resume_by_id_not_found(self, resume_service, test_user_id):
        """Test getting a non-existent resume raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            resume_service.get_resume_by_id(resume_id=99999, user_id=test_user_id)

    def test_get_cover_letter_by_id_not_found(self, cover_letter_service, test_user_id):
        """Test getting a non-existent cover letter raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            cover_letter_service.get_cover_letter_by_id(cover_letter_id=99999, user_id=test_user_id)

    def test_download_text_based_cover_letter_fails(self, cover_letter_service, test_user_id):
        """Test downloading a text-based cover letter raises ValueError."""
        # Create text-based cover letter
        cover_letter = cover_letter_service.create_cover_letter(
            user_id=test_user_id,
            cover_letter_name="Text Cover Letter",
            cover_letter_text="This is text content",
            in_documents_section=True,
        )

        # Attempting to download should fail
        with pytest.raises(ValueError, match="text-based"):
            cover_letter_service.download_cover_letter(
                cover_letter_id=cover_letter["cover_letter_id"],
                user_id=test_user_id,
            )

    def test_upload_resume_invalid_file_type(self, resume_service, test_user_id):
        """Test uploading resume with invalid file type raises error."""
        from io import BytesIO

        invalid_file = FileStorage(
            stream=BytesIO(b"invalid content"),
            filename="test.txt",
            content_type="text/plain",
        )

        with pytest.raises(Exception) as exc_info:
            resume_service.upload_resume(
                user_id=test_user_id,
                file=invalid_file,
                resume_name="Invalid Resume",
                in_documents_section=True,
            )
        assert "not allowed" in str(exc_info.value).lower()

    def test_upload_cover_letter_invalid_file_type(self, cover_letter_service, test_user_id):
        """Test uploading cover letter with invalid file type raises error."""
        from io import BytesIO

        invalid_file = FileStorage(
            stream=BytesIO(b"invalid content"),
            filename="test.txt",
            content_type="text/plain",
        )

        with pytest.raises(Exception) as exc_info:
            cover_letter_service.upload_cover_letter_file(
                user_id=test_user_id,
                file=invalid_file,
                cover_letter_name="Invalid Cover Letter",
                in_documents_section=True,
            )
        assert "not allowed" in str(exc_info.value).lower()
