"""
Campaign Management UI

Flask web interface for managing job search campaigns.
Provides CRUD operations for marts.job_campaigns table.
"""

import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory,
)
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required

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

    Args:
        max_calls: Maximum number of calls allowed
        window_seconds: Time window in seconds
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure user is authenticated (JWT only)
            try:
                user_id = get_jwt_identity()
            except Exception:
                user_id = None

            if not user_id:
                return jsonify({"error": "Authentication required"}), 401

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
    @jwt_required()
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user_service = get_user_service()
        user = user_service.get_user_by_id(user_id)

        if not user or not user.get("is_admin"):
            return jsonify({"error": "Admin access required"}), 403
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


@app.route("/api/campaigns/<int:campaign_id>/toggle-active", methods=["POST"])
@jwt_required()
def api_toggle_active(campaign_id: int):
    """Toggle is_active status of a campaign via API."""
    try:
        user_id = get_jwt_identity()
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(int(user_id))
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        campaign = service.get_campaign_by_id(campaign_id)

        if not campaign:
            return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

        # Check permissions
        if not is_admin and campaign.get("user_id") != int(user_id):
            return jsonify({"error": "You do not have permission to update this campaign"}), 403

        new_status = service.toggle_active(campaign_id)
        status_text = "activated" if new_status else "deactivated"

        return jsonify(
            {
                "success": True,
                "is_active": new_status,
                "message": f"Campaign {status_text} successfully!",
            }
        )
    except Exception as e:
        logger.error(f"Error toggling campaign status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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


@app.route("/api/user/resumes", methods=["GET"])


@app.route("/api/jobs/<job_id>/note", methods=["GET", "POST"])
@jwt_required()
def job_note(job_id: str):
    """Get all notes or add a new note for a job."""
    try:
        user_id = int(get_jwt_identity())
        note_service = get_job_note_service()

        if request.method == "POST":
            # Add a new note
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()

            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            note_id = note_service.add_note(
                jsearch_job_id=job_id, user_id=user_id, note_text=note_text
            )

            # Fetch the created note to return it
            note = note_service.get_note_by_id(note_id=note_id, user_id=user_id)

            return jsonify(
                {"success": True, "message": "Note added successfully", "note": note}
            ), 201
        else:
            # GET request - return all notes as JSON
            notes = note_service.get_notes(jsearch_job_id=job_id, user_id=user_id)

            return jsonify({"notes": notes})

    except Exception as e:
        logger.error(f"Error processing note request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/note/<int:note_id>", methods=["PUT", "DELETE"])
@jwt_required()
def job_note_by_id(job_id: str, note_id: int):
    """Update or delete a specific note by ID."""
    try:
        user_id = int(get_jwt_identity())
        note_service = get_job_note_service()

        if request.method == "PUT":
            # Update an existing note
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()

            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            success = note_service.update_note(
                note_id=note_id, user_id=user_id, note_text=note_text
            )

            if not success:
                return jsonify({"error": "Note not found or unauthorized"}), 404

            # Fetch the updated note to return it
            note = note_service.get_note_by_id(note_id=note_id, user_id=user_id)

            return jsonify(
                {"success": True, "message": "Note updated successfully", "note": note}
            ), 200
        else:
            # DELETE request
            success = note_service.delete_note(note_id=note_id, user_id=user_id)

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


@app.route("/api/jobs/<job_id>/status", methods=["POST"])
@jwt_required()
def update_job_status(job_id: str):
    """Update status for a job."""
    user_id = int(get_jwt_identity())
    try:
        data = request.get_json() or {}
        status = data.get("status", "").strip()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

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

    try:
        status_service = get_job_status_service()
        status_service.upsert_status(
            jsearch_job_id=job_id, user_id=user_id, status=status
        )

        # Auto-link generated cover letter when status changes to "applied"
        if status == "applied":
            try:
                cover_letter_service = get_cover_letter_service()
                # Get the most recent generated cover letter for this job
                generated_history = cover_letter_service.get_generation_history(
                    user_id=user_id,
                    jsearch_job_id=job_id,
                )
                if generated_history:
                    latest_generated = generated_history[0]
                    # Link it to the job application if not already linked
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
                        logger.info(
                            f"Auto-linked generated cover letter {latest_generated['cover_letter_id']} "
                            f"to job {job_id} when status changed to 'applied'"
                        )
            except Exception as e:
                # Log but don't fail status update if cover letter linking fails
                logger.warning(f"Error auto-linking generated cover letter: {e}")

        return jsonify(
            {"success": True, "message": "Status updated successfully!", "status": status}
        ), 200
    except Exception as e:
        logger.error(f"Error updating status: {e}", exc_info=True)
        return jsonify({"error": "An error occurred while updating the status. Please try again."}), 500


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


@app.route("/api/jobs/<job_id>/resume/upload", methods=["POST"])
@jwt_required()
def upload_resume(job_id: str):
    """Upload a resume file for a job."""
    user_id = int(get_jwt_identity())
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume = resume_service.upload_resume(
            user_id=user_id,
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
                user_id=user_id,
                resume_id=resume["resume_id"],
            )

        return jsonify({"success": True, "message": "Resume uploaded successfully!", "resume": resume}), 201
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/resume/<int:resume_id>/download", methods=["GET"])
@jwt_required()
def download_resume(job_id: str, resume_id: int):
    """Download a resume file."""
    user_id = int(get_jwt_identity())
    try:
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
    except ValueError as e:
        logger.error(f"Resume not found: {e}")
        return jsonify({"error": "Resume not found"}), 404
    except Exception as e:
        logger.error(f"Error downloading resume: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/resume/<int:resume_id>/link", methods=["POST"])
@jwt_required()
def link_resume_to_job(job_id: str, resume_id: int):
    """Link an existing resume to a job."""
    user_id = int(get_jwt_identity())
    try:
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            resume_id=resume_id,
        )
        return jsonify({"success": True, "message": "Resume linked successfully!"}), 200
    except Exception as e:
        logger.error(f"Error linking resume: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/resume/<int:resume_id>/unlink", methods=["DELETE", "POST"])
@jwt_required()
def unlink_resume_from_job(job_id: str, resume_id: int):
    """Unlink a resume from a job."""
    user_id = int(get_jwt_identity())
    try:
        document_service = get_document_service()
        doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=user_id
        )
        if doc and doc.get("resume_id") == resume_id:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=user_id,
                resume_id=None,
            )
            return jsonify({"success": True, "message": "Resume unlinked successfully!"}), 200
        else:
            return jsonify({"error": "Resume not linked to this job"}), 400
    except Exception as e:
        logger.error(f"Error unlinking resume: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/cover-letter/create", methods=["POST"])
@jwt_required()
def create_cover_letter(job_id: str):
    """Create or upload a cover letter for a job."""
    user_id = int(get_jwt_identity())
    try:
        cover_letter_service = get_cover_letter_service()
        document_service = get_document_service()

        # Check if it's a file upload or text creation
        if "file" in request.files and request.files["file"].filename:
            # File upload
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter = cover_letter_service.upload_cover_letter_file(
                user_id=user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=job_id,
                in_documents_section=False,  # Not in documents section
            )
            cover_letter_id = cover_letter["cover_letter_id"]
        else:
            # Text-based cover letter
            # Support both form data and JSON
            if request.is_json:
                data = request.get_json() or {}
                cover_letter_text = data.get("cover_letter_text", "").strip()
                cover_letter_name = data.get("cover_letter_name", "").strip() or "Cover Letter"
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
                in_documents_section=False,  # Not in documents section
            )
            cover_letter_id = cover_letter["cover_letter_id"]

        # Link to job
        link_to_job = request.form.get("link_to_job", "").lower() != "false"
        if link_to_job:
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=user_id,
                cover_letter_id=cover_letter_id,
            )

        return jsonify({"success": True, "message": "Cover letter created successfully!", "cover_letter": cover_letter}), 201
    except Exception as e:
        logger.error(f"Error creating cover letter: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/cover-letter/<int:cover_letter_id>/download", methods=["GET"])
@jwt_required()
def download_cover_letter(job_id: str, cover_letter_id: int):
    """Download a cover letter file or text."""
    user_id = int(get_jwt_identity())
    try:
        cover_letter_service = get_cover_letter_service()

        # Handle inline text (cover_letter_id = 0 means inline text from job_application_documents)
        if cover_letter_id == 0:
            document_service = get_document_service()
            doc = document_service.get_job_application_document(
                jsearch_job_id=job_id, user_id=user_id
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
                return jsonify({"error": "Cover letter text not found"}), 404

        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=user_id
        )

        if not cover_letter:
            return jsonify({"error": "Cover letter not found"}), 404

        from flask import Response

        # Check if it's a file-based or text-based cover letter
        if cover_letter.get("file_path"):
            # File-based: use existing download method
            file_content, filename, mime_type = cover_letter_service.download_cover_letter(
                cover_letter_id=cover_letter_id, user_id=user_id
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
            return jsonify({"error": "Cover letter has no content to download"}), 400
    except ValueError as e:
        logger.error(f"Cover letter not found: {e}")
        return jsonify({"error": "Cover letter not found"}), 404
    except Exception as e:
        logger.error(f"Error downloading cover letter: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/cover-letter/<int:cover_letter_id>/link", methods=["POST"])
@jwt_required()
def link_cover_letter_to_job(job_id: str, cover_letter_id: int):
    """Link an existing cover letter to a job."""
    user_id = int(get_jwt_identity())
    try:
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            cover_letter_id=cover_letter_id,
        )
        return jsonify({"success": True, "message": "Cover letter linked successfully!"}), 200
    except Exception as e:
        logger.error(f"Error linking cover letter: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/cover-letter/<int:cover_letter_id>/unlink", methods=["DELETE", "POST"])
@jwt_required()
def unlink_cover_letter_from_job(job_id: str, cover_letter_id: int):
    """Unlink a cover letter from a job."""
    user_id = int(get_jwt_identity())
    try:
        document_service = get_document_service()
        doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=user_id
        )
        if doc and doc.get("cover_letter_id") == cover_letter_id:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=user_id,
                cover_letter_id=None,
            )
            return jsonify({"success": True, "message": "Cover letter unlinked successfully!"}), 200
        else:
            return jsonify({"error": "Cover letter not linked to this job"}), 400
    except Exception as e:
        logger.error(f"Error unlinking cover letter: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/application-documents/update", methods=["POST"])
@jwt_required()
def update_application_documents(job_id: str):
    """Update job application document (notes, linked documents)."""
    user_id = int(get_jwt_identity())
    try:
        document_service = get_document_service()
        doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=user_id
        )

        # Support both form data and JSON
        if request.is_json:
            data = request.get_json() or {}
            resume_id = data.get("resume_id")
            cover_letter_id = data.get("cover_letter_id")
            cover_letter_text = data.get("cover_letter_text")
            user_notes = data.get("user_notes")
        else:
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
                user_id=user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )
        else:
            # Create new document
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )

        return jsonify({"success": True, "message": "Application documents updated successfully!"}), 200
    except Exception as e:
        logger.error(f"Error updating application documents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Documents Section Routes
# ============================================================


@app.route("/api/user/resumes", methods=["GET"])


@app.route("/api/campaigns/<int:campaign_id>/trigger-dag", methods=["POST"])
@jwt_required()
def trigger_campaign_dag(campaign_id: int):
    """Trigger DAG run for a specific campaign."""
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


@app.route("/api/trigger-all-dags", methods=["POST"])
@jwt_required()
def trigger_all_dags():
    """Trigger DAG run for all active campaigns."""
    try:
        airflow_client = get_airflow_client()
        if not airflow_client:
            return jsonify({"error": "Airflow API is not configured."}), 500

        # Trigger DAG without campaign_id in conf (will process all active campaigns)
        airflow_client.trigger_dag(dag_id=DEFAULT_DAG_ID, conf={})
        return jsonify({"success": True, "message": "DAG triggered successfully for all campaigns!"}), 200
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/assets/<path:filename>")
def serve_react_assets(filename: str):
    """Serve React app static assets."""
    if os.path.exists("/app/frontend/dist"):
        react_build_dir = Path("/app/frontend/dist")
    else:
        react_build_dir = Path(__file__).parent.parent / "frontend" / "dist"
    assets_dir = react_build_dir / "assets"
    if assets_dir.exists():
        return send_from_directory(str(assets_dir), filename)
    return jsonify({"error": "Asset not found"}), 404


@app.route("/vite.svg")
def serve_vite_svg():
    """Serve vite.svg icon."""
    if os.path.exists("/app/frontend/dist"):
        react_build_dir = Path("/app/frontend/dist")
    else:
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
    # In Docker, app.py is at /app/app.py and dist is at /app/frontend/dist
    # In local dev, app.py is at campaign_ui/app.py and dist is at frontend/dist
    if os.path.exists("/app/frontend/dist"):
        react_build_dir = Path("/app/frontend/dist")
    else:
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
