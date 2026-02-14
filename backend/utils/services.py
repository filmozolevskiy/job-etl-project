import os
import sys
from pathlib import Path

# Add services to path
if Path("/app").exists():
    sys.path.insert(0, "/app/services")
else:
    services_path = Path(__file__).resolve().parents[2] / "services"
    sys.path.insert(0, str(services_path))

from airflow_client import AirflowClient
from auth import AuthService, UserService
from campaign_management import CampaignService
from documents import (
    CoverLetterGenerator,
    CoverLetterService,
    DocumentService,
    LocalStorageService,
    ResumeService,
)
from jobs import JobNoteService, JobService, JobStatusService
from shared import PostgreSQLDatabase


def build_db_connection_string() -> str:
    """
    Build PostgreSQL connection string from environment variables.

    Checks DATABASE_URL first, then falls back to individual POSTGRES_* variables.

    Returns:
        PostgreSQL connection string
    """
    # Check for DATABASE_URL first (useful for tests and deployments)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # Fall back to individual environment variables
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")
    ssl_mode = os.getenv("POSTGRES_SSL_MODE", "")

    conn_str = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    if ssl_mode:
        conn_str += f"?sslmode={ssl_mode}"
    return conn_str


def get_user_service() -> UserService:
    """
    Get UserService instance with database connection.

    Returns:
        UserService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return UserService(database=database)


def get_auth_service() -> AuthService:
    """
    Get AuthService instance with database connection.

    Returns:
        AuthService instance
    """
    user_service = get_user_service()
    return AuthService(user_service=user_service)


def get_job_service() -> JobService:
    """
    Get JobService instance with database connection.

    Returns:
        JobService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return JobService(database=database)


def get_job_note_service() -> JobNoteService:
    """
    Get JobNoteService instance with database connection.

    Returns:
        JobNoteService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return JobNoteService(database=database)


def get_job_status_service() -> JobStatusService:
    """
    Get JobStatusService instance with database connection.

    Returns:
        JobStatusService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return JobStatusService(database=database)


def get_resume_service() -> ResumeService:
    """
    Get ResumeService instance with database connection and storage.

    Returns:
        ResumeService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    upload_base_dir = os.getenv("UPLOAD_BASE_DIR", "uploads")
    max_file_size = int(os.getenv("UPLOAD_MAX_SIZE", "5242880"))
    allowed_extensions = os.getenv("UPLOAD_ALLOWED_EXTENSIONS", "pdf,docx").split(",")
    storage_service = LocalStorageService(base_dir=upload_base_dir)
    return ResumeService(
        database=database,
        storage_service=storage_service,
        max_file_size=max_file_size,
        allowed_extensions=allowed_extensions,
    )


def get_cover_letter_service() -> CoverLetterService:
    """
    Get CoverLetterService instance with database connection and storage.

    Returns:
        CoverLetterService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    upload_base_dir = os.getenv("UPLOAD_BASE_DIR", "uploads")
    max_file_size = int(os.getenv("UPLOAD_MAX_SIZE", "5242880"))
    allowed_extensions = os.getenv("UPLOAD_ALLOWED_EXTENSIONS", "pdf,docx").split(",")
    storage_service = LocalStorageService(base_dir=upload_base_dir)
    return CoverLetterService(
        database=database,
        storage_service=storage_service,
        max_file_size=max_file_size,
        allowed_extensions=allowed_extensions,
    )


def get_document_service() -> DocumentService:
    """
    Get DocumentService instance with database connection.

    Returns:
        DocumentService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return DocumentService(database=database)


def get_cover_letter_generator() -> CoverLetterGenerator:
    """
    Get CoverLetterGenerator instance with all required services.

    Returns:
        CoverLetterGenerator instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    upload_base_dir = os.getenv("UPLOAD_BASE_DIR", "uploads")
    storage_service = LocalStorageService(base_dir=upload_base_dir)
    cover_letter_service = get_cover_letter_service()
    resume_service = get_resume_service()
    job_service = get_job_service()
    return CoverLetterGenerator(
        database=database,
        cover_letter_service=cover_letter_service,
        resume_service=resume_service,
        job_service=job_service,
        storage_service=storage_service,
    )


def get_airflow_client() -> AirflowClient | None:
    """
    Get AirflowClient instance if configured.

    Returns:
        AirflowClient instance or None if not configured
    """
    api_url = os.getenv("AIRFLOW_API_URL")
    username = os.getenv("AIRFLOW_API_USERNAME")
    password = os.getenv("AIRFLOW_API_PASSWORD")

    if not api_url or not username or not password:
        return None

    return AirflowClient(api_url=api_url, username=username, password=password)


def get_campaign_service() -> CampaignService:
    """
    Get CampaignService instance with database connection.

    Returns:
        CampaignService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return CampaignService(database=database)
