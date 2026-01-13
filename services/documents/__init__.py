"""Document management services for resumes and cover letters."""

from .cover_letter_generator import CoverLetterGenerator
from .cover_letter_service import CoverLetterService
from .document_service import DocumentService
from .resume_service import ResumeService
from .resume_text_extractor import ResumeTextExtractionError, extract_text_from_resume
from .storage_service import LocalStorageService, StorageService

__all__ = [
    "CoverLetterGenerator",
    "CoverLetterService",
    "DocumentService",
    "LocalStorageService",
    "ResumeService",
    "ResumeTextExtractionError",
    "StorageService",
    "extract_text_from_resume",
]
