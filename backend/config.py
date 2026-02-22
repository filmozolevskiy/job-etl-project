import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
repo_root = Path(__file__).resolve().parents[1]
environment = os.getenv("ENVIRONMENT", "development")
env_file = repo_root / f".env.{environment}"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or "dev-secret-key-change-in-production"

    # JWT configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    JWT_CSRF_IN_COOKIES = False
    JWT_COOKIE_CSRF_PROTECT = False

    # CORS configuration: allow production frontend origin(s) via env (comma-separated)
    _cors_env = os.getenv("CORS_ORIGINS", "").strip()
    CORS_ORIGINS = (
        [o.strip() for o in _cors_env.split(",") if o.strip()]
        if _cors_env
        else ["http://localhost:5173", "http://localhost:3000"]
    )

    # Constants
    DEFAULT_DAG_ID = "jobs_etl_daily"

    # Allowed values for multi-select preference fields
    ALLOWED_REMOTE_PREFERENCES = {"remote", "hybrid", "onsite"}
    ALLOWED_SENIORITY = {"entry", "mid", "senior", "lead"}
    ALLOWED_COMPANY_SIZES = {
        "1-50",
        "51-200",
        "201-500",
        "501-1000",
        "1001-5000",
        "5001-10000",
        "10000+",
    }
    ALLOWED_EMPLOYMENT_TYPES = {"FULLTIME", "PARTTIME", "CONTRACTOR", "TEMPORARY", "INTERN"}


def get_airflow_ui_url() -> str | None:
    """Return the public Airflow UI URL for this environment, or None if not applicable."""
    explicit = os.getenv("AIRFLOW_UI_URL", "").strip()
    if explicit:
        return explicit.rstrip("/") + "/"
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        return "https://justapply.net/airflow/"
    slot = os.getenv("STAGING_SLOT", "").strip()
    if env == "staging" and slot:
        return f"https://staging-{slot}.justapply.net/airflow/"
    return None
