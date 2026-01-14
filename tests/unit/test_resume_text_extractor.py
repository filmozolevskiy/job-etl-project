"""Unit tests for resume text extractor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.documents.resume_text_extractor import (
    ResumeTextExtractionError,
    _extract_docx_text,
    _extract_pdf_text,
    extract_text_from_resume,
)


class TestExtractPdfText:
    """Test PDF text extraction."""

    def test_extract_pdf_text_success(self):
        """Test successful PDF text extraction."""
        # Mock PDF content (minimal valid PDF structure)
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Page\n/Contents 2 0 R\n>>\nendobj\n"

        with patch("services.documents.resume_text_extractor.PyPDF2") as mock_pypdf2:
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample resume text\nLine 2"
            mock_reader.pages = [mock_page]
            mock_pypdf2.PdfReader.return_value = mock_reader

            result = _extract_pdf_text(pdf_content)
            assert result == "Sample resume text\nLine 2"
            mock_pypdf2.PdfReader.assert_called_once()

    def test_extract_pdf_text_multiple_pages(self):
        """Test PDF extraction with multiple pages."""
        pdf_content = b"%PDF-1.4"

        with patch("services.documents.resume_text_extractor.PyPDF2") as mock_pypdf2:
            mock_reader = MagicMock()
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "Page 1 text"
            mock_page2 = MagicMock()
            mock_page2.extract_text.return_value = "Page 2 text"
            mock_reader.pages = [mock_page1, mock_page2]
            mock_pypdf2.PdfReader.return_value = mock_reader

            result = _extract_pdf_text(pdf_content)
            assert result == "Page 1 text\n\nPage 2 text"

    def test_extract_pdf_text_no_text(self):
        """Test PDF extraction when no text is found."""
        pdf_content = b"%PDF-1.4"

        with patch("services.documents.resume_text_extractor.PyPDF2") as mock_pypdf2:
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""
            mock_reader.pages = [mock_page]
            mock_pypdf2.PdfReader.return_value = mock_reader

            with pytest.raises(ResumeTextExtractionError, match="No text could be extracted"):
                _extract_pdf_text(pdf_content)

    def test_extract_pdf_text_pypdf2_not_installed(self):
        """Test PDF extraction when PyPDF2 is not installed."""
        with patch("services.documents.resume_text_extractor.PyPDF2", None):
            with pytest.raises(ResumeTextExtractionError, match="PyPDF2 library is not installed"):
                _extract_pdf_text(b"fake pdf content")

    def test_extract_pdf_text_error_handling(self):
        """Test PDF extraction error handling."""
        pdf_content = b"%PDF-1.4"

        with patch("services.documents.resume_text_extractor.PyPDF2") as mock_pypdf2:
            mock_pypdf2.PdfReader.side_effect = Exception("PDF parsing error")

            with pytest.raises(ResumeTextExtractionError, match="Failed to extract text from PDF"):
                _extract_pdf_text(pdf_content)


class TestExtractDocxText:
    """Test DOCX text extraction."""

    def test_extract_docx_text_success(self):
        """Test successful DOCX text extraction."""
        docx_content = b"fake docx content"

        with patch("services.documents.resume_text_extractor.Document") as mock_document:
            mock_doc = MagicMock()
            mock_para1 = MagicMock()
            mock_para1.text = "Paragraph 1"
            mock_para2 = MagicMock()
            mock_para2.text = "Paragraph 2"
            mock_doc.paragraphs = [mock_para1, mock_para2]
            mock_doc.tables = []
            mock_document.return_value = mock_doc

            result = _extract_docx_text(docx_content)
            assert result == "Paragraph 1\n\nParagraph 2"

    def test_extract_docx_text_with_tables(self):
        """Test DOCX extraction with tables."""
        docx_content = b"fake docx content"

        with patch("services.documents.resume_text_extractor.Document") as mock_document:
            mock_doc = MagicMock()
            mock_doc.paragraphs = [MagicMock(text="Paragraph")]
            mock_table = MagicMock()
            mock_row = MagicMock()
            mock_cell1 = MagicMock()
            mock_cell1.text = "Cell 1"
            mock_cell2 = MagicMock()
            mock_cell2.text = "Cell 2"
            mock_row.cells = [mock_cell1, mock_cell2]
            mock_table.rows = [mock_row]
            mock_doc.tables = [mock_table]
            mock_document.return_value = mock_doc

            result = _extract_docx_text(docx_content)
            assert "Paragraph" in result
            assert "Cell 1 | Cell 2" in result

    def test_extract_docx_text_no_text(self):
        """Test DOCX extraction when no text is found."""
        docx_content = b"fake docx content"

        with patch("services.documents.resume_text_extractor.Document") as mock_document:
            mock_doc = MagicMock()
            mock_para = MagicMock()
            mock_para.text = "   "  # Only whitespace
            mock_doc.paragraphs = [mock_para]
            mock_doc.tables = []
            mock_document.return_value = mock_doc

            with pytest.raises(ResumeTextExtractionError, match="No text could be extracted"):
                _extract_docx_text(docx_content)

    def test_extract_docx_text_python_docx_not_installed(self):
        """Test DOCX extraction when python-docx is not installed."""
        with patch("services.documents.resume_text_extractor.Document", None):
            with pytest.raises(
                ResumeTextExtractionError, match="python-docx library is not installed"
            ):
                _extract_docx_text(b"fake docx content")

    def test_extract_docx_text_error_handling(self):
        """Test DOCX extraction error handling."""
        docx_content = b"fake docx content"

        with patch("services.documents.resume_text_extractor.Document") as mock_document:
            mock_document.side_effect = Exception("DOCX parsing error")

            with pytest.raises(ResumeTextExtractionError, match="Failed to extract text from DOCX"):
                _extract_docx_text(docx_content)


class TestExtractTextFromResume:
    """Test extract_text_from_resume function."""

    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        db = MagicMock()
        cursor = MagicMock()
        cursor.description = [
            ("resume_id",),
            ("user_id",),
            ("resume_name",),
            ("file_path",),
            ("file_size",),
            ("file_type",),
            ("in_documents_section",),
            ("created_at",),
            ("updated_at",),
        ]
        cursor.fetchone.return_value = (
            1,  # resume_id
            1,  # user_id
            "test_resume.pdf",  # resume_name
            "resumes/1/1_test_resume.pdf",  # file_path
            1024,  # file_size
            "application/pdf",  # file_type
            False,  # in_documents_section
            None,  # created_at
            None,  # updated_at
        )
        db.get_cursor.return_value.__enter__.return_value = cursor
        db.get_cursor.return_value.__exit__.return_value = None
        return db

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage service."""
        storage = MagicMock()
        storage.get_file.return_value = b"%PDF-1.4\nfake pdf content"
        return storage

    def test_extract_text_from_resume_pdf_success(self, mock_database, mock_storage):
        """Test successful resume text extraction for PDF."""
        with patch("services.documents.resume_text_extractor._extract_pdf_text") as mock_extract:
            mock_extract.return_value = "Extracted PDF text"

            result = extract_text_from_resume(1, 1, mock_storage, mock_database)

            assert result == "Extracted PDF text"
            mock_storage.get_file.assert_called_once_with("resumes/1/1_test_resume.pdf")
            mock_extract.assert_called_once()

    def test_extract_text_from_resume_docx_success(self, mock_database, mock_storage):
        """Test successful resume text extraction for DOCX."""
        # Update mock to return DOCX path
        cursor = mock_database.get_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            1,
            "test_resume.docx",
            "resumes/1/1_test_resume.docx",
            1024,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            False,
            None,
            None,
        )

        with patch("services.documents.resume_text_extractor._extract_docx_text") as mock_extract:
            mock_extract.return_value = "Extracted DOCX text"

            result = extract_text_from_resume(1, 1, mock_storage, mock_database)

            assert result == "Extracted DOCX text"
            mock_extract.assert_called_once()

    def test_extract_text_from_resume_not_found(self, mock_database, mock_storage):
        """Test extraction when resume is not found."""
        cursor = mock_database.get_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="not found or access denied"):
            extract_text_from_resume(999, 1, mock_storage, mock_database)

    def test_extract_text_from_resume_no_file_path(self, mock_database, mock_storage):
        """Test extraction when resume has no file path."""
        cursor = mock_database.get_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            1,
            "test_resume",
            None,  # No file_path
            0,
            None,
            False,
            None,
            None,
        )

        with pytest.raises(ResumeTextExtractionError, match="no file path"):
            extract_text_from_resume(1, 1, mock_storage, mock_database)

    def test_extract_text_from_resume_file_not_found(self, mock_database, mock_storage):
        """Test extraction when file doesn't exist."""
        mock_storage.get_file.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            extract_text_from_resume(1, 1, mock_storage, mock_database)

    def test_extract_text_from_resume_unsupported_format(self, mock_database, mock_storage):
        """Test extraction with unsupported file format."""
        cursor = mock_database.get_cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            1,
            "test_resume.txt",
            "resumes/1/1_test_resume.txt",
            1024,
            "text/plain",
            False,
            None,
            None,
        )

        with pytest.raises(ResumeTextExtractionError, match="Unsupported file type"):
            extract_text_from_resume(1, 1, mock_storage, mock_database)
