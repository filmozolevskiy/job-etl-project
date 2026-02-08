"""
Campaign Management UI

Flask web interface for managing job search campaigns.
Provides CRUD operations for marts.job_campaigns table.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

# Add services to path - works in both dev and container.
# In container: /app/services (or /app when services mounted at /app/services).
# In dev: ../services from campaign_ui/.
if Path("/app").exists():
    sys.path.insert(0, "/app/services")
else:
    services_path = Path(__file__).resolve().parent.parent / "services"
    sys.path.insert(0, str(services_path))

from airflow_client import AirflowClient
from auth import AuthService, UserService
from campaign_management import CampaignService
from documents import (
    CoverLetterGenerationError,
    CoverLetterGenerator,
    CoverLetterService,
    DocumentService,
    LocalStorageService,
    ResumeService,
)
from jobs import JobNoteService, JobService, JobStatusService
from shared import PostgreSQLDatabase

# Load environment variables from environment-specific .env file
# Defaults to .env.development if ENVIRONMENT is not set
repo_root = Path(__file__).resolve().parents[1]
environment = os.getenv("ENVIRONMENT", "development")
env_file = repo_root / f".env.{environment}"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    # Fallback to .env if environment-specific file doesn't exist
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
load_dotenv()  # Load from current directory as well

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_DAG_ID = "jobs_etl_daily"

# Rate limiting storage (in-memory, resets on restart)
_rate_limit_storage: dict[str, list[float]] = {}


def _sanitize_error_message(error: Exception) -> str:
    """Sanitize error messages to avoid leaking sensitive information.

    Args:
        error: Exception object

    Returns:
        Sanitized error message safe for client display
    """
    error_str = str(error).lower()

    # Remove potential file paths
    if "/" in str(error) or "\\" in str(error):
        return "File operation failed. Please check file permissions."

    # Remove database connection strings
    if "password" in error_str or "connection" in error_str or "database" in error_str:
        return "Database operation failed. Please try again."

    # Remove API keys
    if "api" in error_str and ("key" in error_str or "token" in error_str):
        return "API authentication failed. Please check configuration."

    # Generic fallback for unknown errors
    return "An unexpected error occurred. Please try again later."


def _safe_strip(value) -> str:
    """Safely strip a value that may be None or non-string."""
    return value.strip() if isinstance(value, str) else ""


def rate_limit(max_calls: int = 5, window_seconds: int = 60):
    """Simple rate limiting decorator.

    This decorator should be placed AFTER @login_required to ensure
    current_user is available.

    Args:
        max_calls: Maximum number of calls allowed
        window_seconds: Time window in seconds
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure user is authenticated (supports both Flask-Login and JWT)
            user_id = None
            if current_user.is_authenticated:
                user_id = current_user.user_id
            else:
                try:
                    user_id = get_jwt_identity()
                except Exception:
                    user_id = None

            if not user_id:
                if request.is_json:
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("login", next=request.url))

            # Use user_id + endpoint as key
            key = f"{user_id}:{f.__name__}"
            now = datetime.now().timestamp()

            # Clean old entries
            if key in _rate_limit_storage:
                _rate_limit_storage[key] = [
                    timestamp
                    for timestamp in _rate_limit_storage[key]
                    if now - timestamp < window_seconds
                ]
            else:
                _rate_limit_storage[key] = []

            # Check rate limit
            if len(_rate_limit_storage[key]) >= max_calls:
                logger.warning(
                    f"Rate limit exceeded for user {user_id or 'unknown'} on {f.__name__}"
                )
                return jsonify(
                    {
                        "error": f"Rate limit exceeded. Maximum {max_calls} requests per {window_seconds} seconds."
                    }
                ), 429

            # Record this call
            _rate_limit_storage[key].append(now)

            return f(*args, **kwargs)

        return decorated_function

    return decorator


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "dev-secret-key-change-in-production"

# Make UTC timezone available in templates
app.jinja_env.globals.update(timezone_utc=UTC)

# JWT configuration
jwt_secret = os.getenv("JWT_SECRET_KEY")
if not jwt_secret:
    flask_env = os.getenv("FLASK_ENV", "").lower()
    flask_debug = os.getenv("FLASK_DEBUG", "").lower()
    is_dev = flask_env == "development" or flask_debug in {"1", "true", "yes"}
    if not is_dev:
        raise RuntimeError("JWT_SECRET_KEY must be set for non-development environments.")
    jwt_secret = app.secret_key

app.config["JWT_SECRET_KEY"] = jwt_secret
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
app.config["JWT_CSRF_IN_COOKIES"] = False  # Disable CSRF for API-only usage
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
jwt = JWTManager(app)


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"msg": "Token has expired"}), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    logger.error(f"Invalid token error: {str(error)}")
    return jsonify({"msg": f"Invalid token: {str(error)}"}), 422


@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"msg": "Missing authorization header"}), 401


# CORS configuration
CORS(
    app,
    origins=["http://localhost:5173", "http://localhost:3000"],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
)

# Flask-Login setup (kept for backward compatibility during migration)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."


# User class for Flask-Login
class User:
    """User class for Flask-Login."""

    def __init__(self, user_id: int, username: str, email: str, role: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self._role = role

    def is_authenticated(self) -> bool:
        return True

    def is_active(self) -> bool:
        return True

    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.user_id)

    @property
    def is_admin(self) -> bool:
        return self._role == "admin"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Load user from session."""
    try:
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(int(user_id))
        if user_data:
            return User(
                user_id=user_data["user_id"],
                username=user_data["username"],
                email=user_data["email"],
                role=user_data.get("role", "user"),
            )
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}", exc_info=True)
    return None


# Ranking weights configuration
# Maps form field names (HTML input names) to JSON keys used in the database.
# This mapping ensures consistency between the UI form fields and the stored ranking_weights JSONB structure.
# Each weight represents a percentage (0-100) that contributes to the total ranking score.
RANKING_WEIGHT_MAPPING = {
    "ranking_weight_location_match": "location_match",  # Location matching score
    "ranking_weight_salary_match": "salary_match",  # Salary range matching score
    "ranking_weight_company_size_match": "company_size_match",  # Company size preference match
    "ranking_weight_skills_match": "skills_match",  # Skills overlap score
    "ranking_weight_keyword_match": "keyword_match",  # Job title/description keyword match
    "ranking_weight_employment_type_match": "employment_type_match",  # Employment type preference
    "ranking_weight_seniority_match": "seniority_match",  # Seniority level match
    "ranking_weight_remote_type_match": "remote_type_match",  # Remote/hybrid/onsite preference
    "ranking_weight_recency": "recency",  # Job posting recency (newer = higher)
}

WEIGHT_SUM_TOLERANCE = 0.1
MIN_WEIGHT = 0.0
MAX_WEIGHT = 100.0


def extract_ranking_weights(form_data) -> dict[str, float]:
    """
    Extract and validate ranking weights from form data.

    Maps form field names to JSON keys and validates:
    - Each weight is a valid number between 0 and 100
    - All weights sum to exactly 100% (within tolerance)

    Args:
        form_data: Flask request.form object containing ranking weight inputs

    Returns:
        Dictionary mapping JSON keys to float values (percentages), empty dict if no weights provided

    Raises:
        ValueError: If weights are invalid:
            - Non-numeric values
            - Values outside 0-100 range
            - Sum not equal to 100% (within tolerance)
    """
    weights = {}

    for form_field, json_key in RANKING_WEIGHT_MAPPING.items():
        value = form_data.get(form_field, "").strip()
        if value:
            try:
                weight = float(value)
                if weight < MIN_WEIGHT or weight > MAX_WEIGHT:
                    raise ValueError(
                        f"Ranking weight for '{json_key}' must be between {MIN_WEIGHT} and {MAX_WEIGHT}, got {weight}"
                    )
                weights[json_key] = weight
            except ValueError as e:
                # Re-raise if it's our custom validation error
                if "must be between" in str(e):
                    raise
                # Otherwise, it's a conversion error
                raise ValueError(f"Invalid number for ranking weight '{json_key}': {value}") from e

    # Validate sum if any weights provided
    if weights:
        total = sum(weights.values())
        if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Ranking weights must sum to 100%. Current total: {total:.1f}%")

    return weights


@app.template_filter("format_list")
def format_list_filter(value: str | None) -> str:
    """
    Format comma-separated list with spaces for display.

    Args:
        value: Comma-separated string or None

    Returns:
        Formatted string with spaces after commas, or '-' if empty
    """
    return value.replace(",", ", ") if value else "-"


@app.template_filter("from_json")
def from_json_filter(value: str | dict | None) -> dict:
    """
    Parse JSON string to dictionary.

    Args:
        value: JSON string, dict, or None

    Returns:
        Parsed dictionary or empty dict
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


@app.template_filter("parse_iso_date")
def parse_iso_date_filter(value: str | datetime | None) -> datetime | None:
    """
    Parse ISO date string to datetime object.

    Args:
        value: ISO date string, datetime object, or None

    Returns:
        Parsed datetime object or None if parsing fails
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # Normalize Z to +00:00 for fromisoformat
            normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
            return datetime.fromisoformat(normalized)
        except (ValueError, AttributeError):
            return None
    return None


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


def _join_checkbox_values(form, field_name: str, allowed_values: set[str]) -> str:
    """
    Join multiple checkbox values into comma-separated string, filtering invalid values.

    Args:
        form: Flask request form object
        field_name: Name of the checkbox field
        allowed_values: Set of allowed values for validation

    Returns:
        Comma-separated string of valid values, or empty string if none
    """
    values = [v for v in form.getlist(field_name) if v in allowed_values]
    return ",".join(values) if values else ""


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


def admin_required(f):
    """Decorator to require admin role."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.url))
        if not current_user.is_admin:
            flash("Admin access required", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


def get_campaign_service() -> CampaignService:
    """
    Get CampaignService instance with database connection.

    Returns:
        CampaignService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return CampaignService(database=database)


@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard page showing overview of job search activity."""
    try:
        campaign_service = get_campaign_service()
        job_service = get_job_service()

        # Get active campaigns count and total campaigns count
        if current_user.is_admin:
            all_campaigns = campaign_service.get_all_campaigns(user_id=None)
        else:
            all_campaigns = campaign_service.get_all_campaigns(user_id=current_user.user_id)
        total_campaigns_count = len(all_campaigns) if all_campaigns else 0
        active_campaigns_count = sum(1 for c in all_campaigns if c.get("is_active", False))

        # Get jobs statistics - only if user has campaigns
        jobs_processed_count = 0
        success_rate = 0
        recent_jobs = []

        # Only query for jobs if the user has at least one campaign
        if total_campaigns_count > 0:
            try:
                # Get all jobs for the user
                all_jobs = job_service.get_jobs_for_user(user_id=current_user.user_id)

                jobs_processed_count = len(all_jobs) if all_jobs else 0

                # Calculate success rate (jobs with status 'applied', 'interview', or 'offer')
                applied_jobs = (
                    [
                        j
                        for j in all_jobs
                        if j.get("job_status") in ["applied", "interview", "offer"]
                    ]
                    if all_jobs
                    else []
                )
                if jobs_processed_count > 0:
                    success_rate = round((len(applied_jobs) / jobs_processed_count) * 100)

                # Get recent jobs (last 4 applied jobs)
                if all_jobs:
                    recent_jobs = sorted(
                        [j for j in all_jobs if j.get("job_status") == "applied"],
                        key=lambda x: x.get("ranked_at") or datetime.min,
                        reverse=True,
                    )[:4]
                else:
                    recent_jobs = []

                # Prepare activity data for chart (last 30 days)
                activity_data = []
                if all_jobs:
                    from collections import defaultdict

                    jobs_by_date = defaultdict(lambda: {"found": 0, "applied": 0})

                    for job in all_jobs:
                        if job.get("ranked_at"):
                            # Get date from ranked_at
                            if isinstance(job["ranked_at"], str):
                                try:
                                    job_date = datetime.fromisoformat(
                                        job["ranked_at"].replace("Z", "+00:00")
                                    ).date()
                                except (ValueError, AttributeError):
                                    continue
                            else:
                                job_date = (
                                    job["ranked_at"].date()
                                    if hasattr(job["ranked_at"], "date")
                                    else None
                                )

                            if job_date:
                                # Check if within last 30 days
                                today = datetime.now(UTC).date()
                                days_ago = (today - job_date).days
                                if 0 <= days_ago <= 30:
                                    jobs_by_date[job_date]["found"] += 1
                                    if job.get("job_status") == "applied":
                                        jobs_by_date[job_date]["applied"] += 1

                    # Convert to list of dicts and sort by date
                    activity_data = [
                        {
                            "date": str(date),
                            "found": data["found"],
                            "applied": data["applied"],
                        }
                        for date, data in sorted(jobs_by_date.items())
                    ]
            except Exception as e:
                logger.warning(f"Could not fetch job statistics for dashboard: {e}")
                all_jobs = []
                recent_jobs = []
                activity_data = []

        return render_template(
            "dashboard.html",
            active_campaigns_count=active_campaigns_count,
            total_campaigns_count=total_campaigns_count,
            jobs_processed_count=jobs_processed_count,
            success_rate=success_rate,
            recent_jobs=recent_jobs,
            activity_data=activity_data if "activity_data" in locals() else [],
            now=datetime.now(),
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template(
            "dashboard.html",
            active_campaigns_count=0,
            total_campaigns_count=0,
            jobs_processed_count=0,
            success_rate=0,
            recent_jobs=[],
            activity_data=[],
            now=None,
        )


@app.route("/")
@login_required
def index():
    """List all campaigns (filtered by user, unless admin)."""
    try:
        service = get_campaign_service()
        job_service = get_job_service()

        # For non-admin users, only show their own campaigns
        # For admin users, show all campaigns
        if current_user.is_admin:
            campaigns = service.get_all_campaigns(user_id=None)
        else:
            campaigns = service.get_all_campaigns(user_id=current_user.user_id)

        # Calculate total jobs for each campaign (optimized: single query)
        campaign_ids = [c.get("campaign_id") for c in campaigns if c.get("campaign_id")]
        job_counts = {}
        if campaign_ids:
            try:
                job_counts = job_service.get_job_counts_for_campaigns(campaign_ids)
            except Exception as e:
                logger.debug(f"Could not get job counts for campaigns: {e}")

        # Add total_jobs to each campaign dict
        campaigns_with_totals = []
        for campaign in campaigns:
            campaign_id = campaign.get("campaign_id")
            campaign_with_total = dict(campaign)
            campaign_with_total["total_jobs"] = job_counts.get(campaign_id, 0)
            campaigns_with_totals.append(campaign_with_total)

        return render_template("list_campaigns.html", campaigns=campaigns_with_totals)
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}", exc_info=True)
        flash(f"Error loading campaigns: {str(e)}", "error")
        return render_template("list_campaigns.html", campaigns=[])


@app.route("/campaign/<int:campaign_id>")
@login_required
def view_campaign(campaign_id):
    """View a single campaign with details and rich statistics."""
    try:
        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            flash(f"Campaign {campaign_id} not found", "error")
            return redirect(url_for("index"))

        # Check permissions
        if not current_user.is_admin and campaign.get("user_id") != current_user.user_id:
            flash("You do not have permission to view this campaign.", "error")
            return redirect(url_for("index"))

        # Get rich statistics
        statistics = service.get_campaign_statistics(campaign_id) or {}

        # Get derived run status from metrics (only if DAG has been run)
        # Returns None if no metrics data exists (DAG never run)
        # Only show derived status if DAG is actively running or pending
        # After successful completion, show Active/Inactive instead
        try:
            derived_status = service.get_campaign_status_from_metrics(campaign_id=campaign_id)
            # Only show derived status if:
            # 1. Status is "running" (DAG is actively running)
            # 2. Status is "pending" AND dag_run_id is not None (DAG has been triggered but not started)
            # 3. Status is "pending" AND metrics exist (DAG is in progress)
            # Don't show "pending" for new campaigns with no metrics (dag_run_id=None, no metrics)
            # This allows new campaigns to show Active/Inactive based on is_active
            if derived_status and derived_status.get("status") == "running":
                campaign["derived_run_status"] = derived_status
            elif (
                derived_status
                and derived_status.get("status") == "pending"
                and derived_status.get("dag_run_id") is not None
            ):
                # DAG has been triggered (has dag_run_id) but not started yet - show Pending
                campaign["derived_run_status"] = derived_status
            elif (
                derived_status
                and derived_status.get("status") == "pending"
                and derived_status.get("dag_run_id") is None
            ):
                # New campaign with no metrics and no DAG run - don't show derived status
                # Let template fall back to is_active to show Active/Inactive
                campaign["derived_run_status"] = None
            else:
                # DAG completed (success or error) - don't show derived status, show Active/Inactive
                campaign["derived_run_status"] = None
        except Exception as e:
            logger.warning(f"Could not get derived status for campaign {campaign_id}: {e}")
            campaign["derived_run_status"] = None

        # Get jobs for this campaign (include rejected and archived for frontend filtering)
        job_service = get_job_service()
        jobs = (
            job_service.get_jobs_for_campaign(
                campaign_id=campaign_id, user_id=current_user.user_id, include_rejected=True
            )
            or []
        )
        logger.debug(f"Found {len(jobs)} jobs for campaign {campaign_id}")

        # Calculate campaign-specific stats
        total_jobs = len(jobs) if jobs else 0
        applied_jobs_count = (
            sum(1 for job in jobs if job.get("job_status") == "applied") if jobs else 0
        )

        return render_template(
            "view_campaign.html",
            campaign=campaign,
            statistics=statistics,
            jobs=jobs,
            is_admin=current_user.is_admin,
            total_jobs=total_jobs,
            applied_jobs_count=applied_jobs_count,
            now=datetime.now(UTC),
        )
    except Exception as e:
        logger.error(f"Error fetching campaign {campaign_id}: {e}", exc_info=True)
        flash(f"Error loading campaign: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/campaign/<int:campaign_id>/status", methods=["GET"])
@login_required
def get_campaign_status(campaign_id: int):
    """Get campaign status derived from etl_run_metrics."""
    try:
        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

        # Check permissions
        if not current_user.is_admin and campaign.get("user_id") != current_user.user_id:
            return jsonify({"error": "You do not have permission to view this campaign."}), 403

        # Get optional dag_run_id from query parameters
        # Flask's request.args.get() converts + to space in query params
        # We need to fix the timezone part (e.g., " 00:00" -> "+00:00")
        dag_run_id_raw = request.args.get("dag_run_id", None)
        if dag_run_id_raw:
            # Fix the timezone: replace space before timezone with +
            # Pattern: "T23:07:54.078146 00:00" -> "T23:07:54.078146+00:00"
            if (
                " 00:00" in dag_run_id_raw
                or " 01:00" in dag_run_id_raw
                or " 02:00" in dag_run_id_raw
            ):
                # Replace space before timezone offset with +
                import re

                dag_run_id = re.sub(
                    r"(\d{2}:\d{2}:\d{2}\.\d+)\s+(\d{2}:\d{2})", r"\1+\2", dag_run_id_raw
                )
            else:
                dag_run_id = dag_run_id_raw
        else:
            dag_run_id = None

        # Get status from metrics
        logger.debug(f"Getting status for campaign {campaign_id}, dag_run_id: {dag_run_id}")
        status_data = service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )
        logger.debug(f"Status data returned: {status_data}")

        # If no metrics data exists (DAG never run), return pending status
        if status_data is None:
            return jsonify(
                {
                    "status": "pending",
                    "message": "No DAG runs yet",
                    "completed_tasks": [],
                    "failed_tasks": [],
                    "is_complete": False,
                    "jobs_available": False,
                    "dag_run_id": dag_run_id,  # Preserve provided dag_run_id even when no metrics
                }
            )

        # Create human-readable message
        status = status_data["status"]
        if status == "success":
            message = "All tasks completed successfully"
        elif status == "error":
            failed_tasks = status_data.get("failed_tasks", [])
            if failed_tasks:
                message = f"Failed tasks: {', '.join(failed_tasks)}"
            else:
                message = "Pipeline error occurred"
        elif status == "running":
            completed = status_data.get("completed_tasks", [])
            if completed:
                message = f"In progress: {len(completed)} of 4 tasks completed"
            else:
                message = "Pipeline starting"
        else:  # pending
            message = "No tasks have run yet"

        return jsonify(
            {
                "status": status,
                "message": message,
                "completed_tasks": status_data.get("completed_tasks", []),
                "failed_tasks": status_data.get("failed_tasks", []),
                "is_complete": status_data.get("is_complete", False),
                "jobs_available": status_data.get("jobs_available", False),
                "dag_run_id": status_data.get("dag_run_id")
                or dag_run_id,  # Preserve provided dag_run_id if not in response
            }
        )

    except Exception as e:
        logger.error(f"Error getting campaign status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/campaigns/<int:campaign_id>/status", methods=["GET"])
@jwt_required()
def api_get_campaign_status(campaign_id: int):
    """Get campaign status derived from etl_run_metrics (API)."""
    try:
        user_id = get_jwt_identity()
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(int(user_id))
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)
        if not campaign:
            return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

        if not is_admin and campaign.get("user_id") != int(user_id):
            return jsonify({"error": "You do not have permission to view this campaign."}), 403

        # Get optional dag_run_id from query parameters
        dag_run_id_raw = request.args.get("dag_run_id", None)
        if dag_run_id_raw:
            if (
                " 00:00" in dag_run_id_raw
                or " 01:00" in dag_run_id_raw
                or " 02:00" in dag_run_id_raw
            ):
                import re

                dag_run_id = re.sub(
                    r"(\d{2}:\d{2}:\d{2}\.\d+)\s+(\d{2}:\d{2})", r"\1+\2", dag_run_id_raw
                )
            else:
                dag_run_id = dag_run_id_raw
        else:
            dag_run_id = None

        status_data = service.get_campaign_status_from_metrics(
            campaign_id=campaign_id, dag_run_id=dag_run_id
        )

        if status_data is None:
            return jsonify(
                {
                    "status": "pending",
                    "message": "No DAG runs yet",
                    "completed_tasks": [],
                    "failed_tasks": [],
                    "is_complete": False,
                    "jobs_available": False,
                    "dag_run_id": dag_run_id,
                }
            )

        status = status_data["status"]
        if status == "success":
            message = "All tasks completed successfully"
        elif status == "error":
            failed_tasks = status_data.get("failed_tasks", [])
            if failed_tasks:
                message = f"Failed tasks: {', '.join(failed_tasks)}"
            else:
                message = "Pipeline error occurred"
        elif status == "running":
            completed = status_data.get("completed_tasks", [])
            if completed:
                message = f"In progress: {len(completed)} of 4 tasks completed"
            else:
                message = "Pipeline starting"
        else:
            message = "No tasks have run yet"

        return jsonify(
            {
                "status": status,
                "message": message,
                "completed_tasks": status_data.get("completed_tasks", []),
                "failed_tasks": status_data.get("failed_tasks", []),
                "is_complete": status_data.get("is_complete", False),
                "jobs_available": status_data.get("jobs_available", False),
                "dag_run_id": status_data.get("dag_run_id") or dag_run_id,
            }
        )
    except Exception as e:
        logger.error(f"Error getting campaign status: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/campaign/create", methods=["GET", "POST"])
@login_required
def create_campaign():
    """Create a new campaign."""
    if request.method == "POST":
        # Get form data
        campaign_name = request.form.get("campaign_name", "").strip()
        query = request.form.get("query", "").strip()
        location = request.form.get("location", "").strip()
        country = request.form.get("country", "").strip().lower()
        # Normalize "uk" to "gb" (ISO 3166-1 alpha-2 standard)
        if country == "uk":
            country = "gb"
        date_window = request.form.get("date_window", "week")
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        min_salary = request.form.get("min_salary", "").strip()
        max_salary = request.form.get("max_salary", "").strip()
        currency = request.form.get("currency", "").strip().upper()
        # Handle multiple selections for checkboxes with validation
        remote_preference = _join_checkbox_values(
            request.form, "remote_preference", ALLOWED_REMOTE_PREFERENCES
        )
        seniority = _join_checkbox_values(request.form, "seniority", ALLOWED_SENIORITY)
        company_size_preference = _join_checkbox_values(
            request.form, "company_size_preference", ALLOWED_COMPANY_SIZES
        )
        employment_type_preference = _join_checkbox_values(
            request.form, "employment_type_preference", ALLOWED_EMPLOYMENT_TYPES
        )
        is_active = request.form.get("is_active") == "on"

        # Extract and validate ranking weights (optional)
        ranking_weights = {}
        errors = []

        # Check if any weight fields are provided
        if any(request.form.get(f) for f in RANKING_WEIGHT_MAPPING.keys()):
            try:
                ranking_weights = extract_ranking_weights(request.form)
            except ValueError as e:
                errors.append(str(e))

        # Validation
        if not campaign_name:
            errors.append("Campaign name is required")
        if not query:
            errors.append("Search query is required")
        if not country:
            errors.append("Country is required")
        if email and "@" not in email:
            errors.append("Invalid email format")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("create_campaign.html", form_data=request.form)

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary else None
        max_salary_val = float(max_salary) if max_salary else None

        try:
            service = get_campaign_service()
            campaign_id = service.create_campaign(
                campaign_name=campaign_name,
                query=query,
                country=country,
                user_id=current_user.user_id,
                location=location if location else None,
                date_window=date_window,
                email=email if email else None,
                skills=skills if skills else None,
                min_salary=min_salary_val,
                max_salary=max_salary_val,
                currency=currency if currency else None,
                remote_preference=remote_preference if remote_preference else None,
                seniority=seniority if seniority else None,
                company_size_preference=company_size_preference
                if company_size_preference
                else None,
                employment_type_preference=employment_type_preference
                if employment_type_preference
                else None,
                ranking_weights=ranking_weights if ranking_weights else None,
                is_active=is_active,
            )

            flash(f"Campaign '{campaign_name}' created successfully!", "success")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))
        except ValueError as e:
            logger.error(f"Validation error creating campaign: {e}", exc_info=True)
            flash(f"Validation error: {str(e)}", "error")
            return render_template("create_campaign.html", form_data=request.form)
        except Exception as e:
            logger.error(f"Error creating campaign: {e}", exc_info=True)
            flash(f"Error creating campaign: {str(e)}", "error")
            return render_template("create_campaign.html", form_data=request.form)

    # GET request - show form
    return render_template("create_campaign.html")


@app.route("/campaign/<int:campaign_id>/edit", methods=["GET", "POST"])
@login_required
def edit_campaign(campaign_id):
    """Edit an existing campaign."""
    service = get_campaign_service()

    if request.method == "POST":
        # Get form data
        campaign_name = request.form.get("campaign_name", "").strip()
        query = request.form.get("query", "").strip()
        location = request.form.get("location", "").strip()
        country = request.form.get("country", "").strip().lower()
        # Normalize "uk" to "gb" (ISO 3166-1 alpha-2 standard)
        if country == "uk":
            country = "gb"
        date_window = request.form.get("date_window", "week")
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        min_salary = request.form.get("min_salary", "").strip()
        max_salary = request.form.get("max_salary", "").strip()
        currency = request.form.get("currency", "").strip().upper()
        # Handle multiple selections for checkboxes with validation
        remote_preference = _join_checkbox_values(
            request.form, "remote_preference", ALLOWED_REMOTE_PREFERENCES
        )
        seniority = _join_checkbox_values(request.form, "seniority", ALLOWED_SENIORITY)
        company_size_preference = _join_checkbox_values(
            request.form, "company_size_preference", ALLOWED_COMPANY_SIZES
        )
        employment_type_preference = _join_checkbox_values(
            request.form, "employment_type_preference", ALLOWED_EMPLOYMENT_TYPES
        )
        is_active = request.form.get("is_active") == "on"

        # Extract and validate ranking weights (optional)
        ranking_weights = {}
        errors = []

        # Check if any weight fields are provided
        if any(request.form.get(f) for f in RANKING_WEIGHT_MAPPING.keys()):
            try:
                ranking_weights = extract_ranking_weights(request.form)
            except ValueError as e:
                errors.append(str(e))

        # Validation
        if not campaign_name:
            errors.append("Campaign name is required")
        if not query:
            errors.append("Search query is required")
        if not country:
            errors.append("Country is required")
        if email and "@" not in email:
            errors.append("Invalid email format")

        if errors:
            for error in errors:
                flash(error, "error")
            # Re-fetch campaign for display
            campaign = service.get_campaign_by_id(campaign_id)
            if not campaign:
                flash(f"Campaign {campaign_id} not found", "error")
                return redirect(url_for("index"))
            return render_template("edit_campaign.html", campaign=campaign)

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary else None
        max_salary_val = float(max_salary) if max_salary else None

        try:
            service.update_campaign(
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                query=query,
                country=country,
                location=location if location else None,
                date_window=date_window,
                email=email if email else None,
                skills=skills if skills else None,
                min_salary=min_salary_val,
                max_salary=max_salary_val,
                currency=currency if currency else None,
                remote_preference=remote_preference if remote_preference else None,
                seniority=seniority if seniority else None,
                company_size_preference=company_size_preference
                if company_size_preference
                else None,
                employment_type_preference=employment_type_preference
                if employment_type_preference
                else None,
                ranking_weights=ranking_weights if ranking_weights else None,
                is_active=is_active,
            )

            flash(f"Campaign '{campaign_name}' updated successfully!", "success")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))
        except ValueError as e:
            logger.error(f"Validation error updating campaign {campaign_id}: {e}", exc_info=True)
            flash(f"Validation error: {str(e)}", "error")
            # Re-fetch campaign for display
            campaign = service.get_campaign_by_id(campaign_id)
            if not campaign:
                flash(f"Campaign {campaign_id} not found", "error")
                return redirect(url_for("index"))
            return render_template("edit_campaign.html", campaign=campaign)
        except Exception as e:
            logger.error(f"Error updating campaign {campaign_id}: {e}", exc_info=True)
            flash(f"Error updating campaign: {str(e)}", "error")
            # Re-fetch campaign for display
            campaign = service.get_campaign_by_id(campaign_id)
            if not campaign:
                flash(f"Campaign {campaign_id} not found", "error")
                return redirect(url_for("index"))
            return render_template("edit_campaign.html", campaign=campaign)

    # GET request - fetch and display campaign
    try:
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            flash(f"Campaign {campaign_id} not found", "error")
            return redirect(url_for("index"))

        return render_template("edit_campaign.html", campaign=campaign)
    except Exception as e:
        logger.error(f"Error fetching campaign {campaign_id}: {e}", exc_info=True)
        flash(f"Error loading campaign: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/campaign/<int:campaign_id>/toggle-active", methods=["POST"])
@login_required
def toggle_active(campaign_id):
    """Toggle is_active status of a campaign."""
    try:
        service = get_campaign_service()
        new_status = service.toggle_active(campaign_id)

        status_text = "activated" if new_status else "deactivated"

        # Check if request is AJAX
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {
                    "success": True,
                    "is_active": new_status,
                    "message": f"Campaign {status_text} successfully!",
                }
            )

        flash(f"Campaign {campaign_id} {status_text} successfully!", "success")
    except ValueError as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Error: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Error toggling campaign {campaign_id}: {e}", exc_info=True)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Error updating campaign: {str(e)}", "error")

    return redirect(url_for("view_campaign", campaign_id=campaign_id))


@app.route("/campaign/<int:campaign_id>/delete", methods=["POST"])
def delete_campaign(campaign_id):
    """Delete a campaign."""
    try:
        service = get_campaign_service()
        campaign_name = service.delete_campaign(campaign_id)

        flash(f"Campaign '{campaign_name}' deleted successfully!", "success")
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Error deleting campaign {campaign_id}: {e}", exc_info=True)
        flash(f"Error deleting campaign: {str(e)}", "error")

    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration."""
    # Redirect authenticated users away from registration page
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("password_confirm", "").strip()

        errors = []
        if not username:
            errors.append("Username is required")
        if not email:
            errors.append("Email is required")
        if not password:
            errors.append("Password is required")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters")
        if password != confirm_password:
            errors.append("Passwords do not match")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "register.html", form_data={"username": username, "email": email}
            )

        try:
            auth_service = get_auth_service()
            auth_service.register_user(username=username, email=email, password=password)
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template(
                "register.html", form_data={"username": username, "email": email}
            )
        except Exception as e:
            logger.error(f"Error during registration: {e}", exc_info=True)
            flash(f"Registration failed: {str(e)}", "error")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login."""
    # Redirect authenticated users away from login page
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required", "error")
            return render_template("login.html")

        try:
            auth_service = get_auth_service()
            user_data = auth_service.authenticate_user(username=username, password=password)
            if user_data:
                user = User(
                    user_id=user_data["user_id"],
                    username=user_data["username"],
                    email=user_data["email"],
                    role=user_data.get("role", "user"),
                )
                login_user(user)
                next_page = request.args.get("next")
                return redirect(next_page or url_for("index"))
            else:
                flash("Invalid username or password", "error")
        except Exception as e:
            logger.error(f"Error during login: {e}", exc_info=True)
            flash(f"Login failed: {str(e)}", "error")

    return render_template("login.html")


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    """User registration API endpoint returning JWT token."""
    try:
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        confirm_password = data.get("password_confirm", "").strip()

        errors = []
        if not username:
            errors.append("Username is required")
        if not email:
            errors.append("Email is required")
        if not password:
            errors.append("Password is required")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters")
        if password != confirm_password:
            errors.append("Passwords do not match")

        if errors:
            return jsonify({"error": "; ".join(errors)}), 400

        auth_service = get_auth_service()
        auth_service.register_user(username=username, email=email, password=password)

        # Authenticate user to get user data for JWT
        user_data = auth_service.authenticate_user(username=username, password=password)
        if user_data:
            # Create JWT token (without CSRF for API-only usage)
            # Convert user_id to string as flask-jwt-extended requires string identity
            access_token = create_access_token(
                identity=str(user_data["user_id"]),
                additional_claims={
                    "username": user_data["username"],
                    "email": user_data["email"],
                    "role": user_data.get("role", "user"),
                },
                fresh=True,  # Mark as fresh token
            )
            return jsonify(
                {
                    "access_token": access_token,
                    "user": {
                        "user_id": user_data["user_id"],
                        "username": user_data["username"],
                        "email": user_data["email"],
                        "role": user_data.get("role", "user"),
                    },
                }
            ), 201
        else:
            return jsonify({"error": "Registration failed"}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error during registration: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """User login API endpoint returning JWT token."""
    try:
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        auth_service = get_auth_service()
        user_data = auth_service.authenticate_user(username=username, password=password)
        if user_data:
            # Create JWT token (without CSRF for API-only usage)
            # Convert user_id to string as flask-jwt-extended requires string identity
            access_token = create_access_token(
                identity=str(user_data["user_id"]),
                additional_claims={
                    "username": user_data["username"],
                    "email": user_data["email"],
                    "role": user_data.get("role", "user"),
                },
                fresh=True,  # Mark as fresh token
            )
            return jsonify(
                {
                    "access_token": access_token,
                    "user": {
                        "user_id": user_data["user_id"],
                        "username": user_data["username"],
                        "email": user_data["email"],
                        "role": user_data.get("role", "user"),
                    },
                }
            ), 200
        else:
            return jsonify({"error": "Invalid username or password"}), 401
    except Exception as e:
        logger.error(f"Error during login: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/dashboard", methods=["GET"])
@jwt_required()
def api_dashboard():
    """Dashboard API endpoint returning JSON stats."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)  # Convert back to int for database queries
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        campaign_service = get_campaign_service()
        job_service = get_job_service()

        # Get active campaigns count and total campaigns count
        if is_admin:
            all_campaigns = campaign_service.get_all_campaigns(user_id=None)
        else:
            all_campaigns = campaign_service.get_all_campaigns(user_id=user_id)
        total_campaigns_count = len(all_campaigns) if all_campaigns else 0
        active_campaigns_count = sum(1 for c in all_campaigns if c.get("is_active", False))

        # Get jobs statistics - only if user has campaigns
        jobs_processed_count = 0
        success_rate = 0
        recent_jobs = []
        activity_data = []

        # Only query for jobs if the user has at least one campaign
        if total_campaigns_count > 0:
            try:
                # Get all jobs for the user
                all_jobs = job_service.get_jobs_for_user(user_id=user_id)

                jobs_processed_count = len(all_jobs) if all_jobs else 0

                # Calculate success rate (jobs with status 'applied', 'interview', or 'offer')
                applied_jobs = (
                    [
                        j
                        for j in all_jobs
                        if j.get("job_status") in ["applied", "interview", "offer"]
                    ]
                    if all_jobs
                    else []
                )
                if jobs_processed_count > 0:
                    success_rate = round((len(applied_jobs) / jobs_processed_count) * 100)

                # Get recent jobs (last 4 applied jobs)
                if all_jobs:
                    recent_jobs = sorted(
                        [j for j in all_jobs if j.get("job_status") == "applied"],
                        key=lambda x: x.get("ranked_at") or datetime.min,
                        reverse=True,
                    )[:4]

                # Prepare activity data for chart (last 30 days)
                if all_jobs:
                    from collections import defaultdict

                    jobs_by_date = defaultdict(lambda: {"found": 0, "applied": 0})

                    for job in all_jobs:
                        if job.get("ranked_at"):
                            # Get date from ranked_at
                            if isinstance(job["ranked_at"], str):
                                try:
                                    job_date = datetime.fromisoformat(
                                        job["ranked_at"].replace("Z", "+00:00")
                                    ).date()
                                except (ValueError, AttributeError):
                                    continue
                            else:
                                job_date = (
                                    job["ranked_at"].date()
                                    if hasattr(job["ranked_at"], "date")
                                    else None
                                )

                            if job_date:
                                # Check if within last 30 days
                                today = datetime.now(UTC).date()
                                days_ago = (today - job_date).days
                                if 0 <= days_ago <= 30:
                                    jobs_by_date[job_date]["found"] += 1
                                    if job.get("job_status") == "applied":
                                        jobs_by_date[job_date]["applied"] += 1

                    # Convert to list of dicts and sort by date
                    activity_data = [
                        {
                            "date": str(date),
                            "found": data["found"],
                            "applied": data["applied"],
                        }
                        for date, data in sorted(jobs_by_date.items())
                    ]
            except Exception as e:
                logger.warning(f"Could not fetch job statistics for dashboard: {e}")
                recent_jobs = []
                activity_data = []

        return jsonify(
            {
                "active_campaigns_count": active_campaigns_count,
                "total_campaigns_count": total_campaigns_count,
                "jobs_processed_count": jobs_processed_count,
                "success_rate": success_rate,
                "recent_jobs": recent_jobs,
                "activity_data": activity_data,
            }
        ), 200
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/campaigns", methods=["GET"])
@jwt_required()
def api_list_campaigns():
    """Campaigns list API endpoint returning JSON list."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)  # Convert back to int for database queries
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        job_service = get_job_service()

        # For non-admin users, only show their own campaigns
        # For admin users, show all campaigns
        if is_admin:
            campaigns = service.get_all_campaigns(user_id=None)
        else:
            campaigns = service.get_all_campaigns(user_id=user_id)

        # Calculate total jobs for each campaign (optimized: single query)
        campaign_ids = [c.get("campaign_id") for c in campaigns if c.get("campaign_id")]
        job_counts = {}
        if campaign_ids:
            try:
                job_counts = job_service.get_job_counts_for_campaigns(campaign_ids)
            except Exception as e:
                logger.debug(f"Could not get job counts for campaigns: {e}")

        # Add total_jobs to each campaign dict
        campaigns_with_totals = []
        for campaign in campaigns:
            campaign_id = campaign.get("campaign_id")
            campaign_with_total = dict(campaign)
            campaign_with_total["total_jobs"] = job_counts.get(campaign_id, 0)
            campaigns_with_totals.append(campaign_with_total)

        return jsonify({"campaigns": campaigns_with_totals}), 200
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


def _join_json_array_values(json_data: dict, field_name: str, allowed_values: set[str]) -> str:
    """
    Join JSON array values into comma-separated string, filtering invalid values.

    Args:
        json_data: JSON data dictionary
        field_name: Name of the field
        allowed_values: Set of allowed values for validation

    Returns:
        Comma-separated string of valid values, or empty string if none
    """
    value = json_data.get(field_name)
    if not value:
        return ""
    if isinstance(value, str):
        # Handle string as single value
        return value if value in allowed_values else ""
    if isinstance(value, list):
        # Handle array
        values = [str(v) for v in value if str(v) in allowed_values]
        return ",".join(values) if values else ""
    return ""


@app.route("/api/campaigns/<int:campaign_id>", methods=["GET"])
@jwt_required()
def api_get_campaign(campaign_id: int):
    """Get campaign details API endpoint."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)  # Convert back to int for database queries
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

        # Check permissions
        if not is_admin and campaign.get("user_id") != user_id:
            return jsonify({"error": "You do not have permission to view this campaign"}), 403

        return jsonify({"campaign": campaign}), 200
    except Exception as e:
        logger.error(f"Error fetching campaign {campaign_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/campaigns", methods=["POST"])
@jwt_required()
def api_create_campaign():
    """Create campaign API endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id = get_jwt_identity()
        json_data = request.json

        # Extract and validate data
        campaign_name = _safe_strip(json_data.get("campaign_name"))
        query = _safe_strip(json_data.get("query"))
        location = _safe_strip(json_data.get("location")) or None
        country = _safe_strip(json_data.get("country")).lower()
        if country == "uk":
            country = "gb"
        date_window = json_data.get("date_window", "week")
        email = _safe_strip(json_data.get("email")) or None
        skills = _safe_strip(json_data.get("skills")) or None
        min_salary = json_data.get("min_salary")
        max_salary = json_data.get("max_salary")
        currency = _safe_strip(json_data.get("currency")).upper() or None
        remote_preference = (
            _join_json_array_values(json_data, "remote_preference", ALLOWED_REMOTE_PREFERENCES)
            or None
        )
        seniority = _join_json_array_values(json_data, "seniority", ALLOWED_SENIORITY) or None
        company_size_preference = (
            _join_json_array_values(json_data, "company_size_preference", ALLOWED_COMPANY_SIZES)
            or None
        )
        employment_type_preference = (
            _join_json_array_values(
                json_data, "employment_type_preference", ALLOWED_EMPLOYMENT_TYPES
            )
            or None
        )
        ranking_weights = json_data.get("ranking_weights") or None
        is_active = json_data.get("is_active", True)

        # Validation
        errors = []
        if not campaign_name:
            errors.append("Campaign name is required")
        if not query:
            errors.append("Search query is required")
        if not country:
            errors.append("Country is required")
        if email and "@" not in email:
            errors.append("Invalid email format")

        if errors:
            return jsonify({"error": "; ".join(errors)}), 400

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary is not None else None
        max_salary_val = float(max_salary) if max_salary is not None else None

        service = get_campaign_service()
        campaign_id = service.create_campaign(
            campaign_name=campaign_name,
            query=query,
            country=country,
            user_id=user_id,
            location=location,
            date_window=date_window,
            email=email,
            skills=skills,
            min_salary=min_salary_val,
            max_salary=max_salary_val,
            currency=currency,
            remote_preference=remote_preference,
            seniority=seniority,
            company_size_preference=company_size_preference,
            employment_type_preference=employment_type_preference,
            ranking_weights=ranking_weights,
            is_active=is_active,
        )

        return jsonify(
            {"campaign_id": campaign_id, "message": "Campaign created successfully"}
        ), 201
    except ValueError as e:
        logger.error(f"Validation error creating campaign: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating campaign: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/campaigns/<int:campaign_id>", methods=["PUT"])
@jwt_required()
def api_update_campaign(campaign_id: int):
    """Update campaign API endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

        # Check permissions
        if not is_admin and campaign.get("user_id") != user_id:
            return jsonify({"error": "You do not have permission to update this campaign"}), 403

        json_data = request.json

        # Extract and validate data
        campaign_name = _safe_strip(json_data.get("campaign_name"))
        query = _safe_strip(json_data.get("query"))
        location = _safe_strip(json_data.get("location")) or None
        country = _safe_strip(json_data.get("country")).lower()
        if country == "uk":
            country = "gb"
        date_window = json_data.get("date_window", "week")
        email = _safe_strip(json_data.get("email")) or None
        skills = _safe_strip(json_data.get("skills")) or None
        min_salary = json_data.get("min_salary")
        max_salary = json_data.get("max_salary")
        currency = _safe_strip(json_data.get("currency")).upper() or None
        remote_preference = (
            _join_json_array_values(json_data, "remote_preference", ALLOWED_REMOTE_PREFERENCES)
            or None
        )
        seniority = _join_json_array_values(json_data, "seniority", ALLOWED_SENIORITY) or None
        company_size_preference = (
            _join_json_array_values(json_data, "company_size_preference", ALLOWED_COMPANY_SIZES)
            or None
        )
        employment_type_preference = (
            _join_json_array_values(
                json_data, "employment_type_preference", ALLOWED_EMPLOYMENT_TYPES
            )
            or None
        )
        ranking_weights = json_data.get("ranking_weights") or None
        is_active = json_data.get("is_active", True)

        # Validation
        errors = []
        if not campaign_name:
            errors.append("Campaign name is required")
        if not query:
            errors.append("Search query is required")
        if not country:
            errors.append("Country is required")
        if email and "@" not in email:
            errors.append("Invalid email format")

        if errors:
            return jsonify({"error": "; ".join(errors)}), 400

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary is not None else None
        max_salary_val = float(max_salary) if max_salary is not None else None

        service.update_campaign(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            query=query,
            country=country,
            location=location,
            date_window=date_window,
            email=email,
            skills=skills,
            min_salary=min_salary_val,
            max_salary=max_salary_val,
            currency=currency,
            remote_preference=remote_preference,
            seniority=seniority,
            company_size_preference=company_size_preference,
            employment_type_preference=employment_type_preference,
            ranking_weights=ranking_weights,
            is_active=is_active,
        )

        return jsonify({"message": "Campaign updated successfully"}), 200
    except ValueError as e:
        logger.error(f"Validation error updating campaign: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating campaign: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/campaigns/<int:campaign_id>", methods=["DELETE"])
@jwt_required()
def api_delete_campaign(campaign_id: int):
    """Delete campaign API endpoint."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)  # Convert back to int for database queries
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

        # Check permissions
        if not is_admin and campaign.get("user_id") != user_id:
            return jsonify({"error": "You do not have permission to delete this campaign"}), 403

        campaign_name = service.delete_campaign(campaign_id)

        return jsonify({"message": f"Campaign '{campaign_name}' deleted successfully"}), 200
    except ValueError as e:
        logger.error(f"Validation error deleting campaign: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting campaign: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs", methods=["GET"])
@jwt_required()
def api_list_jobs():
    """Jobs list API endpoint returning JSON list."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)  # Convert back to int for database queries
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        campaign_id = request.args.get("campaign_id", type=int)

        job_service = get_job_service()

        if campaign_id:
            # Check campaign ownership
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id)
            if not campaign:
                return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

            if not is_admin and campaign.get("user_id") != user_id:
                return jsonify(
                    {"error": "You do not have permission to view jobs for this campaign"}
                ), 403

            jobs = job_service.get_jobs_for_campaign(campaign_id=campaign_id, user_id=user_id)
        else:
            # Get jobs for all user's campaigns
            jobs = job_service.get_jobs_for_user(user_id=user_id)

        return jsonify({"jobs": jobs or []}), 200
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>", methods=["GET"])
@jwt_required()
def api_get_job(job_id: str):
    """Get job details API endpoint."""
    try:
        user_id = get_jwt_identity()
        job_service = get_job_service()

        job = job_service.get_job_by_id(jsearch_job_id=job_id, user_id=user_id)

        if not job:
            return jsonify({"error": f"Job {job_id} not found"}), 404

        return jsonify({"job": job}), 200
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/application-documents", methods=["GET"])
@jwt_required()
def api_get_job_application_documents(job_id: str):
    """Get application documents and user document lists for a job."""
    try:
        user_id = get_jwt_identity()
        document_service = get_document_service()
        resume_service = get_resume_service()
        cover_letter_service = get_cover_letter_service()

        application_doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=user_id
        )
        user_resumes = resume_service.get_user_resumes(user_id=user_id, in_documents_section=True)
        user_cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=user_id, jsearch_job_id=None, in_documents_section=True
        )

        return jsonify(
            {
                "application_doc": application_doc,
                "user_resumes": user_resumes or [],
                "user_cover_letters": user_cover_letters or [],
            }
        ), 200
    except Exception as e:
        logger.error(f"Error fetching application documents for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/application-documents", methods=["PUT"])
@jwt_required()
def api_update_job_application_documents(job_id: str):
    """Update application documents for a job."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id = get_jwt_identity()
        data = request.get_json() or {}

        resume_id = data.get("resume_id")
        cover_letter_id = data.get("cover_letter_id")
        cover_letter_text = data.get("cover_letter_text") or None
        user_notes = data.get("user_notes") or None

        resume_id = int(resume_id) if str(resume_id).strip() not in ["", "None", "null"] else None
        cover_letter_id = (
            int(cover_letter_id)
            if str(cover_letter_id).strip() not in ["", "None", "null"]
            else None
        )

        document_service = get_document_service()
        doc = document_service.get_job_application_document(jsearch_job_id=job_id, user_id=user_id)

        if doc:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )
        else:
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )

        return jsonify({"message": "Application documents updated successfully"}), 200
    except Exception as e:
        logger.error(f"Error updating application documents for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/resume/upload", methods=["POST"])
@jwt_required()
def api_upload_job_resume(job_id: str):
    """Upload a resume and link it to a job application."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        user_id = get_jwt_identity()
        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume_result = resume_service.upload_resume(
            user_id=user_id,
            file=file,
            resume_name=resume_name,
            in_documents_section=False,
        )
        resume_id = (
            resume_result.get("resume_id") if isinstance(resume_result, dict) else resume_result
        )

        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            resume_id=resume_id,
        )

        return jsonify({"message": "Resume uploaded successfully", "resume_id": resume_id}), 201
    except Exception as e:
        logger.error(f"Error uploading resume for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/cover-letter/create", methods=["POST"])
@jwt_required()
def api_create_job_cover_letter(job_id: str):
    """Create or upload a cover letter for a job (API)."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()
        document_service = get_document_service()

        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter = cover_letter_service.upload_cover_letter_file(
                user_id=user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=job_id,
                in_documents_section=False,
            )
        else:
            cover_letter_text = request.form.get("cover_letter_text", "").strip()
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or "Cover Letter"
            if not cover_letter_text:
                return jsonify({"error": "Cover letter text is required"}), 400
            cover_letter = cover_letter_service.create_cover_letter(
                user_id=user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=cover_letter_text,
                jsearch_job_id=job_id,
                in_documents_section=False,
            )

        cover_letter_id = cover_letter.get("cover_letter_id")
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            cover_letter_id=cover_letter_id,
        )

        return jsonify(
            {
                "cover_letter_id": cover_letter_id,
                "cover_letter_text": cover_letter.get("cover_letter_text"),
                "cover_letter_name": cover_letter.get("cover_letter_name"),
            }
        ), 201
    except Exception as e:
        logger.error(f"Error creating cover letter for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/notes", methods=["GET", "POST"])
@jwt_required()
def api_job_notes(job_id: str):
    """Get or create notes for a job."""
    try:
        note_service = get_job_note_service()
        user_id = get_jwt_identity()

        if request.method == "POST":
            if not request.is_json:
                return jsonify({"error": "Missing JSON in request"}), 400
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()
            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            note_id = note_service.add_note(
                jsearch_job_id=job_id, user_id=user_id, note_text=note_text
            )
            note = note_service.get_note_by_id(note_id=note_id, user_id=user_id)
            return jsonify({"note": note}), 201

        notes = note_service.get_notes(jsearch_job_id=job_id, user_id=user_id)
        return jsonify({"notes": notes or []}), 200
    except Exception as e:
        logger.error(f"Error processing notes for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/notes/<int:note_id>", methods=["PUT", "DELETE"])
@jwt_required()
def api_job_note_by_id(job_id: str, note_id: int):
    """Update or delete a note for a job."""
    try:
        note_service = get_job_note_service()
        user_id = get_jwt_identity()

        if request.method == "PUT":
            if not request.is_json:
                return jsonify({"error": "Missing JSON in request"}), 400
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()
            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            success = note_service.update_note(
                note_id=note_id, user_id=user_id, note_text=note_text
            )
            if not success:
                return jsonify({"error": "Note not found or unauthorized"}), 404
            note = note_service.get_note_by_id(note_id=note_id, user_id=user_id)
            return jsonify({"note": note}), 200

        success = note_service.delete_note(note_id=note_id, user_id=user_id)
        if not success:
            return jsonify({"error": "Note not found or unauthorized"}), 404
        return jsonify({"message": "Note deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error processing note {note_id} for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/status", methods=["POST"])
@jwt_required()
def api_update_job_status(job_id: str):
    """Update job status API endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id = get_jwt_identity()
        json_data = request.json
        status = json_data.get("status", "").strip()

        if not status:
            return jsonify({"error": "Status is required"}), 400

        valid_statuses = [
            "waiting",
            "applied",
            "approved",
            "rejected",
            "interview",
            "offer",
            "archived",
        ]
        if status not in valid_statuses:
            return jsonify(
                {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            ), 400

        status_service = get_job_status_service()
        status_service.upsert_status(jsearch_job_id=job_id, user_id=user_id, status=status)

        # Auto-link generated cover letter when status changes to "applied"
        if status == "applied":
            try:
                cover_letter_service = get_cover_letter_service()
                generated_history = cover_letter_service.get_generation_history(
                    user_id=user_id,
                    jsearch_job_id=job_id,
                )
                if generated_history:
                    latest_generated = generated_history[0]
                    document_service = get_document_service()
                    existing_doc = document_service.get_job_application_document(
                        jsearch_job_id=job_id, user_id=user_id
                    )
                    if (
                        not existing_doc
                        or existing_doc.get("cover_letter_id")
                        != latest_generated["cover_letter_id"]
                    ):
                        document_service.link_documents_to_job(
                            jsearch_job_id=job_id,
                            user_id=user_id,
                            cover_letter_id=latest_generated["cover_letter_id"],
                        )
            except Exception as e:
                logger.warning(f"Error auto-linking cover letter for job {job_id}: {e}")

        return jsonify({"message": "Job status updated successfully"}), 200
    except Exception as e:
        logger.error(f"Error updating job status: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/account", methods=["GET"])
@jwt_required()
def api_get_account():
    """Get user account information API endpoint."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)  # Convert back to int for database queries
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)

        if not user_data:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"user": user_data}), 200
    except Exception as e:
        logger.error(f"Error fetching account: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/account/change-password", methods=["POST"])
@jwt_required()
def api_change_password():
    """Change user password API endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id = get_jwt_identity()
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)

        if not user_data:
            return jsonify({"error": "User not found"}), 404

        json_data = request.json
        current_password = json_data.get("current_password", "").strip()
        new_password = json_data.get("new_password", "").strip()
        confirm_password = json_data.get("confirm_password", "").strip()

        if not current_password or not new_password or not confirm_password:
            return jsonify({"error": "All password fields are required"}), 400

        if new_password != confirm_password:
            return jsonify({"error": "New password and confirm password do not match"}), 400

        if len(new_password) < 8:
            return jsonify({"error": "Password must be at least 8 characters long"}), 400

        auth_service = get_auth_service()
        # Verify current password
        user = auth_service.authenticate_user(
            username=user_data["username"], password=current_password
        )
        if not user:
            return jsonify({"error": "Current password is incorrect"}), 400

        # Update password
        try:
            user_service.update_user_password(user_id, new_password)
            logger.info(f"Password updated successfully for user {user_id}")
            return jsonify({"message": "Password updated successfully"}), 200
        except ValueError as e:
            logger.error(f"Password update validation error: {e}")
            return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error changing password: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents", methods=["GET"])
@jwt_required()
def api_get_documents():
    """Get documents list API endpoint."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        cover_letter_service = get_cover_letter_service()

        resumes = resume_service.get_user_resumes(user_id=user_id, in_documents_section=True)
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=user_id, in_documents_section=True
        )

        return jsonify({"resumes": resumes or [], "cover_letters": cover_letters or []}), 200
    except Exception as e:
        logger.error(f"Error fetching documents: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents/resume/upload", methods=["POST"])
@jwt_required()
def api_upload_resume_documents():
    """Upload a resume (documents section) API endpoint."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        user_id = get_jwt_identity()
        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume_service.upload_resume(
            user_id=user_id,
            file=file,
            resume_name=resume_name,
            in_documents_section=True,
        )

        return jsonify({"message": "Resume uploaded successfully"}), 201
    except Exception as e:
        logger.error(f"Error uploading resume (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents/resume/<int:resume_id>", methods=["DELETE"])
@jwt_required()
def api_delete_resume_documents(resume_id: int):
    """Delete a resume (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        result = resume_service.delete_resume(resume_id=resume_id, user_id=user_id)

        if not result:
            return jsonify({"error": "Resume not found"}), 404

        return jsonify({"message": "Resume deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting resume (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents/cover-letter/create", methods=["POST"])
@jwt_required()
def api_create_cover_letter_documents():
    """Create or upload a cover letter (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()

        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter_service.upload_cover_letter_file(
                user_id=user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=None,
                in_documents_section=True,
            )
        else:
            cover_letter_text = request.form.get("cover_letter_text", "").strip()
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or "Cover Letter"
            if not cover_letter_text:
                return jsonify({"error": "Cover letter text is required"}), 400

            cover_letter_service.create_cover_letter(
                user_id=user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=cover_letter_text,
                jsearch_job_id=None,
                in_documents_section=True,
            )

        return jsonify({"message": "Cover letter created successfully"}), 201
    except Exception as e:
        logger.error(f"Error creating cover letter (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents/cover-letter/<int:cover_letter_id>", methods=["GET", "DELETE"])
@jwt_required()
def api_cover_letter_documents(cover_letter_id: int):
    """Get or delete a cover letter (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()

        if request.method == "DELETE":
            result = cover_letter_service.delete_cover_letter(
                cover_letter_id=cover_letter_id, user_id=user_id
            )
            if not result:
                return jsonify({"error": "Cover letter not found"}), 404
            return jsonify({"message": "Cover letter deleted successfully"}), 200

        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=user_id
        )
        if not cover_letter:
            return jsonify({"error": "Cover letter not found"}), 404

        return jsonify(
            {
                "cover_letter_id": cover_letter.get("cover_letter_id"),
                "cover_letter_name": cover_letter.get("cover_letter_name"),
                "cover_letter_text": cover_letter.get("cover_letter_text"),
                "file_path": cover_letter.get("file_path"),
            }
        ), 200
    except Exception as e:
        logger.error(f"Error fetching cover letter (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents/resume/<int:resume_id>/download", methods=["GET"])
@jwt_required()
def api_download_resume_documents(resume_id: int):
    """Download a resume (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        file_content, filename, mime_type = resume_service.download_resume(
            resume_id=resume_id, user_id=user_id
        )
        from flask import Response

        return Response(
            file_content,
            mimetype=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Error downloading resume (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/documents/cover-letter/<int:cover_letter_id>/download", methods=["GET"])
@jwt_required()
def api_download_cover_letter_documents(cover_letter_id: int):
    """Download a cover letter (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()
        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=user_id
        )

        if not cover_letter:
            return jsonify({"error": "Cover letter not found"}), 404

        from flask import Response

        if cover_letter.get("file_path"):
            file_content, filename, mime_type = cover_letter_service.download_cover_letter(
                cover_letter_id=cover_letter_id, user_id=user_id
            )
            return Response(
                file_content,
                mimetype=mime_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if cover_letter.get("cover_letter_text"):
            text_content = cover_letter["cover_letter_text"]
            filename = f"{cover_letter.get('cover_letter_name', 'cover_letter')}.txt"
            return Response(
                text_content.encode("utf-8"),
                mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        return jsonify({"error": "Cover letter has no content to download"}), 400
    except Exception as e:
        logger.error(f"Error downloading cover letter (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/account")
@login_required
def account_management():
    """Account management page."""
    try:
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(current_user.user_id)
        return render_template("account_management.html", user_data=user_data)
    except Exception as e:
        logger.error(f"Error loading account management: {e}", exc_info=True)
        flash(f"Error loading account: {str(e)}", "error")
        return render_template("account_management.html")


@app.route("/account/change-password", methods=["POST"])
@login_required
def change_password():
    """Change user password."""
    try:
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not current_password or not new_password or not confirm_password:
            flash("All password fields are required.", "error")
            return redirect(url_for("account_management"))

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "error")
            return redirect(url_for("account_management"))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for("account_management"))

        auth_service = get_auth_service()
        # Verify current password
        user = auth_service.authenticate_user(
            username=current_user.username, password=current_password
        )
        if not user:
            flash("Current password is incorrect.", "error")
            return redirect(url_for("account_management"))

        # Update password
        user_service = get_user_service()
        try:
            user_service.update_user_password(current_user.user_id, new_password)
            logger.info(f"Password updated successfully for user {current_user.user_id}")
            flash("Password updated successfully.", "success")
        except ValueError as e:
            logger.error(f"Password update validation error: {e}")
            flash(f"Password update failed: {str(e)}", "error")
        except Exception as e:
            logger.error(f"Unexpected error updating password: {e}", exc_info=True)
            flash(f"Password update failed: {str(e)}", "error")
        return redirect(url_for("account_management"))
    except Exception as e:
        logger.error(f"Error changing password: {e}", exc_info=True)
        flash(f"Error changing password: {str(e)}", "error")
        return redirect(url_for("account_management"))


@app.route("/logout")
@login_required
def logout():
    """User logout."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/jobs")
@app.route("/jobs/<int:campaign_id>")
@login_required
def view_jobs(campaign_id: int | None = None):
    """View jobs for a campaign or all user's campaigns."""
    try:
        job_service = get_job_service()

        if campaign_id:
            # Check campaign ownership
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id)
            if not campaign:
                flash(f"Campaign {campaign_id} not found", "error")
                return redirect(url_for("index"))

            if not current_user.is_admin and campaign.get("user_id") != current_user.user_id:
                flash("You do not have permission to view jobs for this campaign.", "error")
                return redirect(url_for("index"))

            jobs = job_service.get_jobs_for_campaign(
                campaign_id=campaign_id, user_id=current_user.user_id
            )
            campaign_name = campaign.get("campaign_name")
        else:
            # Get jobs for all user's campaigns
            jobs = job_service.get_jobs_for_user(user_id=current_user.user_id)
            campaign_name = None

        return render_template(
            "jobs.html", jobs=jobs, campaign_id=campaign_id, campaign_name=campaign_name
        )
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}", exc_info=True)
        flash(f"Error loading jobs: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/job/<job_id>")
@login_required
def view_job_details(job_id: str):
    """View details of a single job."""
    try:
        job_service = get_job_service()

        # Get job directly by ID (optimized: single query)
        job = job_service.get_job_by_id(jsearch_job_id=job_id, user_id=current_user.user_id)

        if not job:
            flash(f"Job {job_id} not found", "error")
            return redirect(url_for("index"))

        # Get campaign_id if available
        campaign_id = job.get("campaign_id")

        # Get application documents
        document_service = get_document_service()
        application_doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=current_user.user_id
        )

        # Get user's resumes and cover letters for dropdowns (only from documents section)
        resume_service = get_resume_service()
        cover_letter_service = get_cover_letter_service()
        user_resumes = resume_service.get_user_resumes(
            user_id=current_user.user_id, in_documents_section=True
        )
        user_cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=current_user.user_id, jsearch_job_id=None, in_documents_section=True
        )

        # Get job status history (excluding note changes)
        status_service = get_job_status_service()
        all_history = status_service.get_status_history(
            jsearch_job_id=job_id, user_id=current_user.user_id
        )
        # Filter out note-related history entries
        status_history = [
            entry
            for entry in all_history
            if entry.get("change_type") != "note_change"
            and entry.get("status") not in ["note_added", "note_updated", "note_deleted"]
        ]

        return render_template(
            "job_details.html",
            job=job,
            campaign_id=campaign_id,
            application_doc=application_doc,
            user_resumes=user_resumes,
            user_cover_letters=user_cover_letters,
            status_history=status_history,
        )
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        flash(f"Error loading job: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/jobs/<job_id>/note", methods=["GET", "POST"])
@login_required
def job_note(job_id: str):
    """Get all notes or add a new note for a job."""
    try:
        note_service = get_job_note_service()

        if request.method == "POST":
            # Add a new note
            note_text = request.form.get("note_text", "").strip()

            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            note_id = note_service.add_note(
                jsearch_job_id=job_id, user_id=current_user.user_id, note_text=note_text
            )

            # Fetch the created note to return it
            note = note_service.get_note_by_id(note_id=note_id, user_id=current_user.user_id)

            return jsonify(
                {"success": True, "message": "Note added successfully", "note": note}
            ), 201
        else:
            # GET request - return all notes as JSON
            notes = note_service.get_notes(jsearch_job_id=job_id, user_id=current_user.user_id)

            return jsonify({"notes": notes})

    except Exception as e:
        logger.error(f"Error processing note request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/jobs/<job_id>/note/<int:note_id>", methods=["PUT", "DELETE"])
@login_required
def job_note_by_id(job_id: str, note_id: int):
    """Update or delete a specific note by ID."""
    try:
        note_service = get_job_note_service()

        if request.method == "PUT":
            # Update an existing note
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()

            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            success = note_service.update_note(
                note_id=note_id, user_id=current_user.user_id, note_text=note_text
            )

            if not success:
                return jsonify({"error": "Note not found or unauthorized"}), 404

            # Fetch the updated note to return it
            note = note_service.get_note_by_id(note_id=note_id, user_id=current_user.user_id)

            return jsonify(
                {"success": True, "message": "Note updated successfully", "note": note}
            ), 200
        else:
            # DELETE request
            success = note_service.delete_note(note_id=note_id, user_id=current_user.user_id)

            if not success:
                return jsonify({"error": "Note not found or unauthorized"}), 404

            return jsonify({"success": True, "message": "Note deleted successfully"}), 200

    except Exception as e:
        logger.error(f"Error processing note request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/status/history", methods=["GET"])
@jwt_required()
def get_job_status_history(job_id: str):
    """Get status history for a job (excluding note changes)."""
    try:
        status_service = get_job_status_service()
        user_id = get_jwt_identity()
        all_history = status_service.get_status_history(jsearch_job_id=job_id, user_id=user_id)
        # Filter out note-related history entries
        status_history = []
        for entry in all_history:
            if entry.get("change_type") != "note_change" and entry.get("status") not in [
                "note_added",
                "note_updated",
                "note_deleted",
            ]:
                # Convert datetime to UTC ISO format string for consistent JavaScript parsing
                if entry.get("created_at") and isinstance(entry["created_at"], datetime):
                    if entry["created_at"].tzinfo:
                        entry["created_at"] = entry["created_at"].astimezone(UTC).isoformat()
                    else:
                        # Naive datetime - assume UTC
                        entry["created_at"] = entry["created_at"].replace(tzinfo=UTC).isoformat()
                status_history.append(entry)
        return jsonify({"history": status_history}), 200
    except Exception as e:
        logger.error(f"Error fetching status history for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/jobs/<job_id>/status", methods=["POST"])
@login_required
def update_job_status(job_id: str):
    """Update status for a job."""
    # Detect AJAX requests (check both Content-Type and X-Requested-With header)
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Support both form data and JSON
    if request.is_json:
        try:
            data = request.get_json() or {}
            status = data.get("status", "").strip()
        except Exception:
            # If JSON parsing fails, treat as form data
            status = request.form.get("status", "").strip()
    else:
        status = request.form.get("status", "").strip()

    if not status:
        if is_ajax:
            return jsonify({"error": "Status is required"}), 400
        flash("Status is required", "error")
        return redirect(request.referrer or url_for("view_jobs"))

    valid_statuses = [
        "waiting",
        "applied",
        "approved",
        "rejected",
        "interview",
        "offer",
        "archived",
    ]
    if status not in valid_statuses:
        if is_ajax:
            return jsonify(
                {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            ), 400
        flash(f"Invalid status. Must be one of: {', '.join(valid_statuses)}", "error")
        return redirect(request.referrer or url_for("view_jobs"))

    try:
        status_service = get_job_status_service()
        status_service.upsert_status(
            jsearch_job_id=job_id, user_id=current_user.user_id, status=status
        )

        # Auto-link generated cover letter when status changes to "applied"
        if status == "applied":
            try:
                cover_letter_service = get_cover_letter_service()
                # Get the most recent generated cover letter for this job
                # Already sorted by created_at DESC from query
                generated_history = cover_letter_service.get_generation_history(
                    user_id=current_user.user_id,
                    jsearch_job_id=job_id,
                )
                if generated_history:
                    latest_generated = generated_history[0]
                    # Link it to the job application if not already linked
                    document_service = get_document_service()
                    existing_doc = document_service.get_job_application_document(
                        jsearch_job_id=job_id, user_id=current_user.user_id
                    )
                    if (
                        not existing_doc
                        or existing_doc.get("cover_letter_id")
                        != latest_generated["cover_letter_id"]
                    ):
                        document_service.link_documents_to_job(
                            jsearch_job_id=job_id,
                            user_id=current_user.user_id,
                            cover_letter_id=latest_generated["cover_letter_id"],
                        )
                        logger.info(
                            f"Auto-linked generated cover letter {latest_generated['cover_letter_id']} "
                            f"to job {job_id} when status changed to 'applied'"
                        )
            except Exception as e:
                # Log but don't fail status update if cover letter linking fails
                logger.warning(f"Error auto-linking generated cover letter: {e}")

        if is_ajax:
            return jsonify(
                {"success": True, "message": "Status updated successfully!", "status": status}
            ), 200
        flash("Status updated successfully!", "success")
    except Exception as e:
        logger.error(f"Error updating status: {e}", exc_info=True)
        if is_ajax:
            # Return user-friendly error message for AJAX requests
            error_message = "An error occurred while updating the status. Please try again."
            return jsonify({"error": error_message}), 500
        flash(f"Error updating status: {str(e)}", "error")

    return redirect(request.referrer or url_for("view_jobs"))


# ============================================================
# Document Management Routes
# ============================================================


@app.route("/api/user/resumes", methods=["GET"])
@jwt_required()
def get_user_resumes():
    """Get all resumes for the current user API endpoint."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        resumes = resume_service.get_user_resumes(user_id=user_id)
        return jsonify({"resumes": resumes or []}), 200
    except Exception as e:
        logger.error(f"Error fetching resumes: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/user/cover-letters", methods=["GET"])
@jwt_required()
def get_user_cover_letters():
    """Get all cover letters for the current user API endpoint."""
    try:
        user_id = get_jwt_identity()
        job_id = request.args.get("job_id")
        cover_letter_service = get_cover_letter_service()
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=user_id, jsearch_job_id=job_id
        )
        return jsonify({"cover_letters": cover_letters or []}), 200
    except Exception as e:
        logger.error(f"Error fetching cover letters: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@app.route("/api/jobs/<job_id>/cover-letter/generate", methods=["POST"])
@jwt_required()
@rate_limit(max_calls=5, window_seconds=60)  # 5 requests per minute per user
def generate_cover_letter(job_id: str):
    """Generate a cover letter using ChatGPT (AJAX endpoint).

    Accepts JSON:
        {
            "resume_id": int (required),
            "user_comments": str (optional)
        }

    Returns JSON:
        {
            "cover_letter_text": str,
            "cover_letter_id": int,
            "cover_letter_name": str,
            "error": str (optional)
        }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json() or {}
        resume_id = data.get("resume_id")
        user_comments = data.get("user_comments")

        if not resume_id:
            return jsonify({"error": "resume_id is required"}), 400

        try:
            resume_id = int(resume_id)
        except (ValueError, TypeError):
            return jsonify({"error": "resume_id must be an integer"}), 400

        # Generate cover letter
        generator = get_cover_letter_generator()
        user_id = get_jwt_identity()
        cover_letter = generator.generate_cover_letter(
            resume_id=resume_id,
            jsearch_job_id=job_id,
            user_id=user_id,
            user_comments=user_comments,
        )

        # Auto-link to job application
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            cover_letter_id=cover_letter["cover_letter_id"],
        )

        return jsonify(
            {
                "cover_letter_text": cover_letter["cover_letter_text"],
                "cover_letter_id": cover_letter["cover_letter_id"],
                "cover_letter_name": cover_letter["cover_letter_name"],
            }
        )

    except CoverLetterGenerationError as e:
        logger.error(f"Cover letter generation failed: {e}", exc_info=True)
        return jsonify(
            {"error": "Failed to generate cover letter. Please check your resume and try again."}
        ), 500
    except ValueError as e:
        logger.warning(f"Validation error generating cover letter: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error generating cover letter: {e}", exc_info=True)
        sanitized_error = _sanitize_error_message(e)
        return jsonify({"error": sanitized_error}), 500


@app.route("/api/jobs/<job_id>/cover-letter/generation-history", methods=["GET"])
@jwt_required()
def get_cover_letter_generation_history(job_id: str):
    """Get generation history for a job (AJAX endpoint).

    Returns JSON:
        {
            "history": [
                {
                    "cover_letter_id": int,
                    "cover_letter_name": str,
                    "cover_letter_text": str,
                    "generation_prompt": str,
                    "created_at": str,
                    ...
                },
                ...
            ]
        }
    """
    try:
        cover_letter_service = get_cover_letter_service()
        user_id = get_jwt_identity()
        history = cover_letter_service.get_generation_history(
            user_id=user_id,
            jsearch_job_id=job_id,
        )
        return jsonify({"history": history})
    except Exception as e:
        logger.error(f"Error fetching generation history: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/jobs/<job_id>/resume/upload", methods=["POST"])
@login_required
def upload_resume(job_id: str):
    """Upload a resume file for a job."""
    try:
        if "file" not in request.files:
            flash("No file provided", "error")
            return redirect(request.referrer or url_for("view_job_details", job_id=job_id))

        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume = resume_service.upload_resume(
            user_id=current_user.user_id,
            file=file,
            resume_name=resume_name,
            in_documents_section=False,  # Not in documents section
        )

        # Optionally link to job
        link_to_job = request.form.get("link_to_job", "").lower() == "true"
        if link_to_job:
            document_service = get_document_service()
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=current_user.user_id,
                resume_id=resume["resume_id"],
            )

        flash("Resume uploaded successfully!", "success")
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        error_msg = str(e)
        if "validation" in error_msg.lower() or "size" in error_msg.lower():
            flash(f"Upload failed: {error_msg}", "error")
        else:
            flash(f"Error uploading resume: {error_msg}", "error")

    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/resume/<int:resume_id>/download", methods=["GET"])
@login_required
def download_resume(job_id: str, resume_id: int):
    """Download a resume file."""
    try:
        resume_service = get_resume_service()
        file_content, filename, mime_type = resume_service.download_resume(
            resume_id=resume_id, user_id=current_user.user_id
        )
        from flask import Response

        return Response(
            file_content,
            mimetype=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        logger.error(f"Resume not found: {e}")
        flash("Resume not found", "error")
        return redirect(request.referrer or url_for("view_job_details", job_id=job_id))
    except Exception as e:
        logger.error(f"Error downloading resume: {e}", exc_info=True)
        flash(f"Error downloading resume: {str(e)}", "error")
        return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/resume/<int:resume_id>/link", methods=["POST"])
@login_required
def link_resume_to_job(job_id: str, resume_id: int):
    """Link an existing resume to a job."""
    try:
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=current_user.user_id,
            resume_id=resume_id,
        )
        flash("Resume linked successfully!", "success")
    except Exception as e:
        logger.error(f"Error linking resume: {e}", exc_info=True)
        flash(f"Error linking resume: {str(e)}", "error")

    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/resume/<int:resume_id>/unlink", methods=["DELETE", "POST"])
@login_required
def unlink_resume_from_job(job_id: str, resume_id: int):
    """Unlink a resume from a job."""
    try:
        document_service = get_document_service()
        doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=current_user.user_id
        )
        if doc and doc.get("resume_id") == resume_id:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=current_user.user_id,
                resume_id=None,
            )
            flash("Resume unlinked successfully!", "success")
        else:
            flash("Resume not linked to this job", "error")
    except Exception as e:
        logger.error(f"Error unlinking resume: {e}", exc_info=True)
        flash(f"Error unlinking resume: {str(e)}", "error")

    if request.method == "DELETE" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/cover-letter/create", methods=["POST"])
@login_required
def create_cover_letter(job_id: str):
    """Create or upload a cover letter for a job."""
    try:
        cover_letter_service = get_cover_letter_service()
        document_service = get_document_service()

        # Check if it's a file upload or text creation
        if "file" in request.files and request.files["file"].filename:
            # File upload
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter = cover_letter_service.upload_cover_letter_file(
                user_id=current_user.user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=job_id,
                in_documents_section=False,  # Not in documents section
            )
            cover_letter_id = cover_letter["cover_letter_id"]
        else:
            # Text-based cover letter
            cover_letter_text = request.form.get("cover_letter_text", "").strip()
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or "Cover Letter"
            if not cover_letter_text:
                flash("Cover letter text is required", "error")
                return redirect(request.referrer or url_for("view_job_details", job_id=job_id))

            cover_letter = cover_letter_service.create_cover_letter(
                user_id=current_user.user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=cover_letter_text,
                jsearch_job_id=job_id,
                in_documents_section=False,  # Not in documents section
            )
            cover_letter_id = cover_letter["cover_letter_id"]

        # Link to job
        link_to_job = request.form.get("link_to_job", "").lower() != "false"
        if link_to_job:
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=current_user.user_id,
                cover_letter_id=cover_letter_id,
            )

        flash("Cover letter created successfully!", "success")
    except Exception as e:
        logger.error(f"Error creating cover letter: {e}", exc_info=True)
        error_msg = str(e)
        if "validation" in error_msg.lower() or "size" in error_msg.lower():
            flash(f"Upload failed: {error_msg}", "error")
        else:
            flash(f"Error creating cover letter: {error_msg}", "error")

    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/cover-letter/<int:cover_letter_id>/download", methods=["GET"])
@login_required
def download_cover_letter(job_id: str, cover_letter_id: int):
    """Download a cover letter file or text."""
    try:
        cover_letter_service = get_cover_letter_service()

        # Handle inline text (cover_letter_id = 0 means inline text from job_application_documents)
        if cover_letter_id == 0:
            document_service = get_document_service()
            doc = document_service.get_job_application_document(
                jsearch_job_id=job_id, user_id=current_user.user_id
            )
            if doc and doc.get("cover_letter_text"):
                from flask import Response

                filename = f"cover_letter_{job_id}.txt"
                return Response(
                    doc["cover_letter_text"].encode("utf-8"),
                    mimetype="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            else:
                flash("Cover letter text not found", "error")
                return redirect(request.referrer or url_for("view_job_details", job_id=job_id))

        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=current_user.user_id
        )

        if not cover_letter:
            flash("Cover letter not found", "error")
            return redirect(request.referrer or url_for("view_job_details", job_id=job_id))

        from flask import Response

        # Check if it's a file-based or text-based cover letter
        if cover_letter.get("file_path"):
            # File-based: use existing download method
            file_content, filename, mime_type = cover_letter_service.download_cover_letter(
                cover_letter_id=cover_letter_id, user_id=current_user.user_id
            )
            return Response(
                file_content,
                mimetype=mime_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        elif cover_letter.get("cover_letter_text"):
            # Text-based: return as text file
            text_content = cover_letter["cover_letter_text"]
            filename = f"{cover_letter.get('cover_letter_name', 'cover_letter')}.txt"
            return Response(
                text_content.encode("utf-8"),
                mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:
            flash("Cover letter has no content to download", "error")
            return redirect(request.referrer or url_for("view_job_details", job_id=job_id))
    except ValueError as e:
        logger.error(f"Cover letter not found: {e}")
        flash("Cover letter not found", "error")
        return redirect(request.referrer or url_for("view_job_details", job_id=job_id))
    except Exception as e:
        logger.error(f"Error downloading cover letter: {e}", exc_info=True)
        flash(f"Error downloading cover letter: {str(e)}", "error")
        return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/cover-letter/<int:cover_letter_id>/link", methods=["POST"])
@login_required
def link_cover_letter_to_job(job_id: str, cover_letter_id: int):
    """Link an existing cover letter to a job."""
    try:
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=current_user.user_id,
            cover_letter_id=cover_letter_id,
        )
        flash("Cover letter linked successfully!", "success")
    except Exception as e:
        logger.error(f"Error linking cover letter: {e}", exc_info=True)
        flash(f"Error linking cover letter: {str(e)}", "error")

    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/cover-letter/<int:cover_letter_id>/unlink", methods=["DELETE", "POST"])
@login_required
def unlink_cover_letter_from_job(job_id: str, cover_letter_id: int):
    """Unlink a cover letter from a job."""
    try:
        document_service = get_document_service()
        doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=current_user.user_id
        )
        if doc and doc.get("cover_letter_id") == cover_letter_id:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=current_user.user_id,
                cover_letter_id=None,
            )
            flash("Cover letter unlinked successfully!", "success")
        else:
            flash("Cover letter not linked to this job", "error")
    except Exception as e:
        logger.error(f"Error unlinking cover letter: {e}", exc_info=True)
        flash(f"Error unlinking cover letter: {str(e)}", "error")

    if request.method == "DELETE" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


@app.route("/jobs/<job_id>/application-documents/update", methods=["POST"])
@login_required
def update_application_documents(job_id: str):
    """Update job application document (notes, linked documents)."""
    try:
        document_service = get_document_service()
        doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=current_user.user_id
        )

        resume_id = request.form.get("resume_id", "").strip()
        cover_letter_id = request.form.get("cover_letter_id", "").strip()
        cover_letter_text = request.form.get("cover_letter_text", "").strip() or None
        user_notes = request.form.get("user_notes", "").strip() or None

        # Convert to int if provided and not empty
        resume_id = (
            int(resume_id) if resume_id and resume_id != "None" and resume_id != "" else None
        )
        cover_letter_id = (
            int(cover_letter_id)
            if cover_letter_id and cover_letter_id != "None" and cover_letter_id != ""
            else None
        )

        if doc:
            # Update existing document
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=current_user.user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )
        else:
            # Create new document
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=current_user.user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )

        flash("Application documents updated successfully!", "success")
    except Exception as e:
        logger.error(f"Error updating application documents: {e}", exc_info=True)
        flash(f"Error updating application documents: {str(e)}", "error")

    return redirect(request.referrer or url_for("view_job_details", job_id=job_id))


# ============================================================
# Documents Section Routes
# ============================================================


@app.route("/documents")
@login_required
def documents():
    """Display documents management page."""
    try:
        resume_service = get_resume_service()
        cover_letter_service = get_cover_letter_service()

        # Get only documents in the documents section
        resumes = resume_service.get_user_resumes(
            user_id=current_user.user_id, in_documents_section=True
        )
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=current_user.user_id, in_documents_section=True
        )

        return render_template(
            "documents.html",
            resumes=resumes,
            cover_letters=cover_letters,
        )
    except Exception as e:
        logger.error(f"Error loading documents page: {e}", exc_info=True)
        flash(f"Error loading documents: {str(e)}", "error")
        return render_template("documents.html", resumes=[], cover_letters=[])


@app.route("/documents/resume/upload", methods=["POST"])
@login_required
def upload_resume_documents():
    """Upload a resume from documents page."""
    try:
        if "file" not in request.files:
            flash("No file provided", "error")
            return redirect(url_for("documents"))

        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume_service.upload_resume(
            user_id=current_user.user_id,
            file=file,
            resume_name=resume_name,
            in_documents_section=True,  # In documents section
        )

        flash("Resume uploaded successfully!", "success")
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        error_msg = str(e)
        if "validation" in error_msg.lower() or "size" in error_msg.lower():
            flash(f"Upload failed: {error_msg}", "error")
        else:
            flash(f"Error uploading resume: {error_msg}", "error")

    return redirect(url_for("documents"))


@app.route("/documents/resume/<int:resume_id>/delete", methods=["POST", "DELETE"])
@login_required
def delete_resume_documents(resume_id: int):
    """Delete a resume from documents section."""
    try:
        resume_service = get_resume_service()
        result = resume_service.delete_resume(resume_id=resume_id, user_id=current_user.user_id)

        if result:
            flash("Resume deleted successfully!", "success")
        else:
            flash("Resume not found", "error")
    except Exception as e:
        logger.error(f"Error deleting resume: {e}", exc_info=True)
        flash(f"Error deleting resume: {str(e)}", "error")

    if request.method == "DELETE" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
    return redirect(url_for("documents"))


@app.route("/documents/cover-letter/create", methods=["POST"])
@login_required
def create_cover_letter_documents():
    """Create or upload a cover letter from documents page."""
    try:
        cover_letter_service = get_cover_letter_service()

        # Check if it's a file upload or text creation
        if "file" in request.files and request.files["file"].filename:
            # File upload
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter_service.upload_cover_letter_file(
                user_id=current_user.user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=None,  # Generic cover letter, not job-specific
                in_documents_section=True,  # In documents section
            )
        else:
            # Text-based cover letter
            cover_letter_text = request.form.get("cover_letter_text", "").strip()
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or "Cover Letter"
            if not cover_letter_text:
                flash("Cover letter text is required", "error")
                return redirect(url_for("documents"))

            cover_letter_service.create_cover_letter(
                user_id=current_user.user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=cover_letter_text,
                jsearch_job_id=None,  # Generic cover letter, not job-specific
                in_documents_section=True,  # In documents section
            )

        flash("Cover letter created successfully!", "success")
    except Exception as e:
        logger.error(f"Error creating cover letter: {e}", exc_info=True)
        error_msg = str(e)
        if "validation" in error_msg.lower() or "size" in error_msg.lower():
            flash(f"Upload failed: {error_msg}", "error")
        else:
            flash(f"Error creating cover letter: {error_msg}", "error")

    return redirect(url_for("documents"))


@app.route("/documents/cover-letter/<int:cover_letter_id>/delete", methods=["POST", "DELETE"])
@login_required
def delete_cover_letter_documents(cover_letter_id: int):
    """Delete a cover letter from documents section."""
    try:
        cover_letter_service = get_cover_letter_service()
        result = cover_letter_service.delete_cover_letter(
            cover_letter_id=cover_letter_id, user_id=current_user.user_id
        )

        if result:
            flash("Cover letter deleted successfully!", "success")
        else:
            flash("Cover letter not found", "error")
    except Exception as e:
        logger.error(f"Error deleting cover letter: {e}", exc_info=True)
        flash(f"Error deleting cover letter: {str(e)}", "error")

    if request.method == "DELETE" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
    return redirect(url_for("documents"))


@app.route("/documents/resume/<int:resume_id>/download", methods=["GET"])
@login_required
def download_resume_documents(resume_id: int):
    """Download a resume from documents section."""
    try:
        resume_service = get_resume_service()
        file_content, filename, mime_type = resume_service.download_resume(
            resume_id=resume_id, user_id=current_user.user_id
        )
        from flask import Response

        return Response(
            file_content,
            mimetype=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        logger.error(f"Resume not found: {e}")
        flash("Resume not found", "error")
        return redirect(url_for("documents"))
    except Exception as e:
        logger.error(f"Error downloading resume: {e}", exc_info=True)
        flash(f"Error downloading resume: {str(e)}", "error")
        return redirect(url_for("documents"))


@app.route("/documents/cover-letter/<int:cover_letter_id>/download", methods=["GET"])
@login_required
def download_cover_letter_documents(cover_letter_id: int):
    """Download a cover letter from documents section."""
    try:
        cover_letter_service = get_cover_letter_service()
        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=current_user.user_id
        )

        if not cover_letter:
            flash("Cover letter not found", "error")
            return redirect(url_for("documents"))

        from flask import Response

        # Check if it's a file-based or text-based cover letter
        if cover_letter.get("file_path"):
            # File-based: use existing download method
            file_content, filename, mime_type = cover_letter_service.download_cover_letter(
                cover_letter_id=cover_letter_id, user_id=current_user.user_id
            )
            return Response(
                file_content,
                mimetype=mime_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        elif cover_letter.get("cover_letter_text"):
            # Text-based: return as text file
            text_content = cover_letter["cover_letter_text"]
            filename = f"{cover_letter.get('cover_letter_name', 'cover_letter')}.txt"
            return Response(
                text_content.encode("utf-8"),
                mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:
            flash("Cover letter has no content to download", "error")
            return redirect(url_for("documents"))
    except ValueError as e:
        logger.error(f"Cover letter not found: {e}")
        flash("Cover letter not found", "error")
        return redirect(url_for("documents"))
    except Exception as e:
        logger.error(f"Error downloading cover letter: {e}", exc_info=True)
        flash(f"Error downloading cover letter: {str(e)}", "error")
        return redirect(url_for("documents"))


@app.route("/campaign/<int:campaign_id>/trigger-dag", methods=["POST"])
@login_required
def trigger_campaign_dag(campaign_id: int):
    """Trigger DAG run for a specific campaign."""
    try:
        # Check if this is a force start (admin only)
        # Handle both form data and JSON requests
        force = False
        try:
            if request.is_json and hasattr(request, "json") and request.json:
                force = request.json.get("force", False)
            else:
                force_str = request.form.get("force", "")
                force = force_str.lower() == "true" if force_str else False
        except Exception:
            # Fallback to form data if JSON parsing fails
            force_str = request.form.get("force", "")
            force = force_str.lower() == "true" if force_str else False

        # Check campaign ownership
        campaign_service = get_campaign_service()
        campaign = campaign_service.get_campaign_by_id(campaign_id)
        if not campaign:
            error_msg = f"Campaign {campaign_id} not found"
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 404
            flash(error_msg, "error")
            return redirect(url_for("index"))

        if not current_user.is_admin and campaign.get("user_id") != current_user.user_id:
            error_msg = "You do not have permission to trigger DAG for this campaign."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 403
            flash(error_msg, "error")
            return redirect(url_for("index"))

        # Only admins can force start
        if force and not current_user.is_admin:
            error_msg = "Only admins can force start DAG runs."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 403
            flash(error_msg, "error")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))

        # Check if DAG is already running for this campaign (unless force start)
        if not force:
            try:
                derived_status = campaign_service.get_campaign_status_from_metrics(
                    campaign_id=campaign_id
                )
                if derived_status:
                    status_value = derived_status.get("status")

                    # Always block if DAG is running
                    if status_value == "running":
                        error_msg = "A DAG run is already in progress for this campaign. Please wait for it to complete."
                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            return jsonify(
                                {"success": False, "error": error_msg}
                            ), 409  # Conflict status code
                        flash(error_msg, "error")
                        return redirect(url_for("view_campaign", campaign_id=campaign_id))

                    # For "pending" status, only block if it's recent (within last hour)
                    # This prevents blocking reactivated campaigns with stale pending status
                    if status_value == "pending":
                        is_recent = False
                        dag_run_id = derived_status.get("dag_run_id")

                        # Check if there's a recent DAG run
                        if dag_run_id:
                            try:
                                # Parse dag_run_id as date (format: YYYY-MM-DDTHH:mm:ss+ZZ:ZZ or manual__YYYY-MM-DDTHH:mm:ss...)
                                date_str = (
                                    dag_run_id.replace("manual__", "").split("+")[0].split(".")[0]
                                )
                                # Try parsing with timezone, fallback to UTC
                                try:
                                    run_date = datetime.fromisoformat(
                                        date_str.replace("T", " ")
                                    ).replace(tzinfo=UTC)
                                except ValueError:
                                    # If parsing fails, try without timezone
                                    run_date = datetime.strptime(
                                        date_str.replace("T", " "), "%Y-%m-%d %H:%M:%S"
                                    ).replace(tzinfo=UTC)

                                now = datetime.now(UTC)
                                diff = now - run_date
                                is_recent = diff < timedelta(hours=1)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse dag_run_id date: {dag_run_id}, error: {e}"
                                )
                                # If can't parse, assume recent to be safe
                                is_recent = True
                        else:
                            # No dag_run_id - check if last_run_at is recent
                            last_run_at = campaign.get("last_run_at")
                            if last_run_at:
                                try:
                                    if isinstance(last_run_at, str):
                                        # Parse string to datetime
                                        last_run = datetime.fromisoformat(
                                            last_run_at.replace("Z", "+00:00")
                                        )
                                    else:
                                        # Assume it's already a datetime object
                                        last_run = last_run_at

                                    # Ensure timezone aware
                                    if last_run.tzinfo is None:
                                        last_run = last_run.replace(tzinfo=UTC)

                                    now = datetime.now(UTC)
                                    diff = now - last_run
                                    is_recent = diff < timedelta(hours=1)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to parse last_run_at: {last_run_at}, error: {e}"
                                    )
                                    # If can't parse, assume not recent (allow trigger)
                                    is_recent = False
                            else:
                                # No dag_run_id and no last_run_at - not truly pending, allow trigger
                                is_recent = False

                        # Only block if pending status is recent (actual DAG run in progress)
                        if is_recent:
                            error_msg = "A DAG run is already in progress for this campaign. Please wait for it to complete."
                            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                                return jsonify(
                                    {"success": False, "error": error_msg}
                                ), 409  # Conflict status code
                            flash(error_msg, "error")
                            return redirect(url_for("view_campaign", campaign_id=campaign_id))
                        else:
                            # Stale pending status - log and allow trigger
                            logger.debug(
                                f"Pending status for campaign {campaign_id} is stale (no recent DAG run). Allowing trigger."
                            )
            except Exception as e:
                # If we can't check status, log but continue (don't block DAG trigger)
                logger.warning(f"Could not check DAG status before trigger: {e}")

        airflow_client = get_airflow_client()
        if not airflow_client:
            flash("Airflow API is not configured.", "error")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))

        # Trigger DAG with campaign_id in conf
        try:
            dag_run = airflow_client.trigger_dag(
                dag_id=DEFAULT_DAG_ID, conf={"campaign_id": campaign_id}
            )
            dag_run_id = dag_run.get("dag_run_id") if dag_run else None

            # Validate that we got a response (even if dag_run_id is None, that's okay - Airflow might generate it later)
            if dag_run is None:
                logger.warning(f"Airflow trigger_dag returned None for campaign {campaign_id}")
                raise ValueError("Airflow API returned an invalid response")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while triggering DAG for campaign {campaign_id}")
            error_msg = "Request to Airflow timed out. The DAG may have been triggered, but we couldn't confirm. Please check Airflow UI."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 504  # Gateway Timeout
            flash(error_msg, "error")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error while triggering DAG for campaign {campaign_id}")
            error_msg = "Cannot connect to Airflow. Please check if Airflow is running."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 503  # Service Unavailable
            flash(error_msg, "error")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors from AirflowClient
            logger.error(f"HTTP error while triggering DAG for campaign {campaign_id}: {e}")
            error_msg = str(e)
            status_code = 502  # Bad Gateway (Airflow issue)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), status_code
            flash(error_msg, "error")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))

        # If this is an AJAX request, return JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {
                    "success": True,
                    "message": "DAG triggered successfully" + (" (forced)" if force else ""),
                    "dag_run_id": dag_run_id,
                    "forced": force,
                }
            )

        flash("DAG triggered successfully!", "success")
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)

        # If this is an AJAX request, return JSON error
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": str(e)}), 500

        flash(f"Error triggering DAG: {str(e)}", "error")

    return redirect(url_for("view_campaign", campaign_id=campaign_id))


@app.route("/api/campaigns/<int:campaign_id>/trigger-dag", methods=["POST"])
@jwt_required()
def api_trigger_campaign_dag(campaign_id: int):
    """Trigger DAG run for a specific campaign (API)."""
    try:
        user_id = get_jwt_identity()
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(int(user_id))
        is_admin = user_data.get("role") == "admin" if user_data else False

        force = False
        if request.is_json and hasattr(request, "json") and request.json:
            force = request.json.get("force", False)

        campaign_service = get_campaign_service()
        campaign = campaign_service.get_campaign_by_id(campaign_id)
        if not campaign:
            return jsonify({"success": False, "error": f"Campaign {campaign_id} not found"}), 404

        if not is_admin and campaign.get("user_id") != int(user_id):
            return jsonify(
                {
                    "success": False,
                    "error": "You do not have permission to trigger DAG for this campaign.",
                }
            ), 403

        if force and not is_admin:
            return jsonify(
                {"success": False, "error": "Only admins can force start DAG runs."}
            ), 403

        if not force:
            derived_status = campaign_service.get_campaign_status_from_metrics(
                campaign_id=campaign_id
            )
            if derived_status and derived_status.get("status") == "running":
                return jsonify(
                    {
                        "success": False,
                        "error": "A DAG run is already in progress for this campaign. Please wait for it to complete.",
                    }
                ), 409

        airflow_client = get_airflow_client()
        if not airflow_client:
            return jsonify({"success": False, "error": "Airflow API is not configured."}), 503

        dag_run = airflow_client.trigger_dag(
            dag_id=DEFAULT_DAG_ID, conf={"campaign_id": campaign_id}
        )
        dag_run_id = dag_run.get("dag_run_id") if dag_run else None

        return jsonify(
            {
                "success": True,
                "message": "DAG triggered successfully" + (" (forced)" if force else ""),
                "dag_run_id": dag_run_id,
                "forced": force,
            }
        ), 200
    except Exception as e:
        logger.error(f"Error triggering DAG for campaign {campaign_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": _sanitize_error_message(e)}), 500


@app.route("/trigger-all-dags", methods=["POST"])
@login_required
def trigger_all_dags():
    """Trigger DAG run for all active campaigns."""
    try:
        airflow_client = get_airflow_client()
        if not airflow_client:
            flash("Airflow API is not configured.", "error")
            return redirect(url_for("index"))

        # Trigger DAG without campaign_id in conf (will process all active campaigns)
        airflow_client.trigger_dag(dag_id=DEFAULT_DAG_ID, conf={})
        flash("DAG triggered successfully for all campaigns!", "success")
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)
        flash(f"Error triggering DAG: {str(e)}", "error")

    return redirect(url_for("index"))


@app.route("/assets/<path:filename>")
def serve_react_assets(filename: str):
    """Serve React app static assets."""
    react_build_dir = Path(__file__).parent.parent / "frontend" / "dist"
    assets_dir = react_build_dir / "assets"
    if assets_dir.exists():
        return send_from_directory(str(assets_dir), filename)
    return jsonify({"error": "Asset not found"}), 404


@app.route("/vite.svg")
def serve_vite_svg():
    """Serve vite.svg icon."""
    react_build_dir = Path(__file__).parent.parent / "frontend" / "dist"
    vite_svg = react_build_dir / "vite.svg"
    if vite_svg.exists():
        return send_from_directory(str(react_build_dir), "vite.svg")
    return jsonify({"error": "File not found"}), 404


def _resolved_environment() -> str:
    """Resolve effective environment. Slot 10 is treated as production."""
    slot = os.getenv("STAGING_SLOT")
    if slot == "10":
        return "production"
    return os.getenv("ENVIRONMENT", "development")


@app.route("/api/version")
def api_version():
    """Return deployment version and metadata.

    This endpoint is public (no authentication required) to allow
    easy verification of deployed versions across environments.
    """
    env = _resolved_environment()
    payload = {
        "environment": env,
        "branch": os.getenv("DEPLOYED_BRANCH"),
        "commit_sha": os.getenv("DEPLOYED_SHA"),
        "deployed_at": os.getenv("DEPLOYED_AT"),
    }
    if env != "production":
        slot = os.getenv("STAGING_SLOT")
        if slot:
            payload["slot"] = slot
    return jsonify(payload)


@app.route("/api/health")
def api_health():
    """Health check endpoint for load balancers and monitoring."""
    try:
        # Check database connectivity using proper connection string
        db_conn_str = build_db_connection_string()
        db = PostgreSQLDatabase(connection_string=db_conn_str)
        with db.get_cursor() as cur:
            cur.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    env = _resolved_environment()
    response = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "environment": env,
    }
    staging_slot = os.getenv("STAGING_SLOT")
    if staging_slot and env != "production":
        response["staging_slot"] = int(staging_slot)
    return jsonify(response)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path: str):
    """Catch-all route to serve React SPA for non-API routes."""
    # Don't serve React app for API routes (these should be handled by existing routes)
    if path.startswith("api/"):
        return jsonify({"error": "API endpoint not found"}), 404

    # Don't serve React app for static assets (handled by serve_react_assets and serve_vite_svg)
    if path.startswith("assets/") or path == "vite.svg":
        return jsonify({"error": "Asset not found"}), 404

    # React app build directory (will be created when React app is built)
    react_build_dir = Path(__file__).parent.parent / "frontend" / "dist"

    # If React app doesn't exist yet, return a placeholder message
    # This will be updated when React app is built
    if not react_build_dir.exists() or not (react_build_dir / "index.html").exists():
        return jsonify(
            {
                "message": "React app is not built yet. Frontend will be served from /frontend/dist/index.html"
            }
        ), 503

    # Serve React app's index.html for all routes (client-side routing)
    return send_from_directory(str(react_build_dir), "index.html")


if __name__ == "__main__":
    debug = os.getenv("ENVIRONMENT", "development") == "development"
    app.run(host="0.0.0.0", port=5000, debug=debug, use_reloader=debug)
