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
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

# Add services to path - works in both dev and container
# In container: /app/services
# In dev: ../services from campaign_ui/
if Path("/app").exists():
    # Running in container - services are at /app/services
    sys.path.insert(0, "/app/services")
else:
    # Running locally - services are at ../services from campaign_ui/
    services_path = Path(__file__).parent.parent / "services"
    sys.path.insert(0, str(services_path))

from airflow_client import AirflowClient
from auth import AuthService, UserService
from campaign_management import CampaignService
from documents import (
    CoverLetterService,
    DocumentService,
    LocalStorageService,
    ResumeService,
)
from jobs import JobNoteService, JobService, JobStatusService
from shared import PostgreSQLDatabase

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_DAG_ID = "jobs_etl_daily"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "dev-secret-key-change-in-production"

# Flask-Login setup
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

    Returns:
        PostgreSQL connection string
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


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
            except Exception as e:
                logger.warning(f"Could not fetch job statistics for dashboard: {e}")
                all_jobs = []
                recent_jobs = []

        return render_template(
            "dashboard.html",
            active_campaigns_count=active_campaigns_count,
            total_campaigns_count=total_campaigns_count,
            jobs_processed_count=jobs_processed_count,
            success_rate=success_rate,
            recent_jobs=recent_jobs,
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
            # Only show derived status if it's running or pending (not success/error after completion)
            # This allows status to revert to Active/Inactive after DAG completes
            if derived_status and derived_status.get("status") in ("running", "pending"):
                campaign["derived_run_status"] = derived_status
            else:
                # DAG completed (success or error) - don't show derived status, show Active/Inactive
                campaign["derived_run_status"] = None
        except Exception as e:
            logger.warning(f"Could not get derived status for campaign {campaign_id}: {e}")
            campaign["derived_run_status"] = None

        # Get jobs for this campaign
        job_service = get_job_service()
        jobs = (
            job_service.get_jobs_for_campaign(campaign_id=campaign_id, user_id=current_user.user_id)
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
            now=datetime.now(),
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
                "dag_run_id": status_data.get("dag_run_id")
                or dag_run_id,  # Preserve provided dag_run_id if not in response
            }
        )

    except Exception as e:
        logger.error(f"Error getting campaign status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
        flash(f"Campaign {campaign_id} {status_text} successfully!", "success")
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Error toggling campaign {campaign_id}: {e}", exc_info=True)
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

        return render_template(
            "job_details.html",
            job=job,
            campaign_id=campaign_id,
            application_doc=application_doc,
            user_resumes=user_resumes,
            user_cover_letters=user_cover_letters,
        )
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        flash(f"Error loading job: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/jobs/<job_id>/note", methods=["GET", "POST"])
@login_required
def job_note(job_id: str):
    """Get or update a note for a job."""
    if request.method == "POST":
        note_text = request.form.get("note_text", "").strip()

        try:
            note_service = get_job_note_service()
            note_service.upsert_note(
                jsearch_job_id=job_id, user_id=current_user.user_id, note_text=note_text
            )
            flash("Note saved successfully!", "success")
        except Exception as e:
            logger.error(f"Error saving note: {e}", exc_info=True)
            flash(f"Error saving note: {str(e)}", "error")

        return redirect(request.referrer or url_for("view_jobs"))
    else:
        # GET request - return note data as JSON
        try:
            note_service = get_job_note_service()
            note = note_service.get_note(jsearch_job_id=job_id, user_id=current_user.user_id)

            return jsonify({"note_text": note.get("note_text", "") if note else ""})
        except Exception as e:
            logger.error(f"Error fetching note: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


@app.route("/jobs/<job_id>/status", methods=["POST"])
@login_required
def update_job_status(job_id: str):
    """Update status for a job."""
    status = request.form.get("status", "").strip()
    if not status:
        flash("Status is required", "error")
        return redirect(request.referrer or url_for("view_jobs"))

    valid_statuses = ["waiting", "applied", "rejected", "interview", "offer", "archived"]
    if status not in valid_statuses:
        flash(f"Invalid status. Must be one of: {', '.join(valid_statuses)}", "error")
        return redirect(request.referrer or url_for("view_jobs"))

    try:
        status_service = get_job_status_service()
        status_service.upsert_status(
            jsearch_job_id=job_id, user_id=current_user.user_id, status=status
        )
        flash("Status updated successfully!", "success")
    except Exception as e:
        logger.error(f"Error updating status: {e}", exc_info=True)
        flash(f"Error updating status: {str(e)}", "error")

    return redirect(request.referrer or url_for("view_jobs"))


# ============================================================
# Document Management Routes
# ============================================================


@app.route("/api/user/resumes", methods=["GET"])
@login_required
def get_user_resumes():
    """Get all resumes for the current user (AJAX endpoint)."""
    try:
        resume_service = get_resume_service()
        resumes = resume_service.get_user_resumes(user_id=current_user.user_id)
        return jsonify({"resumes": resumes})
    except Exception as e:
        logger.error(f"Error fetching resumes: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/user/cover-letters", methods=["GET"])
@login_required
def get_user_cover_letters():
    """Get all cover letters for the current user (AJAX endpoint)."""
    try:
        job_id = request.args.get("job_id")
        cover_letter_service = get_cover_letter_service()
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=current_user.user_id, jsearch_job_id=job_id
        )
        return jsonify({"cover_letters": cover_letters})
    except Exception as e:
        logger.error(f"Error fetching cover letters: {e}", exc_info=True)
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
