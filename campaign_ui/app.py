"""
Campaign Management UI

Flask web interface for managing job search campaigns.
Provides CRUD operations for marts.job_campaigns table.
"""

import json
import logging
import os
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

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

        # Get jobs for this campaign
        job_service = get_job_service()
        jobs = (
            job_service.get_jobs_for_campaign(campaign_id=campaign_id, user_id=current_user.user_id)
            or []
        )

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
            total_jobs=total_jobs,
            applied_jobs_count=applied_jobs_count,
            now=datetime.now(),
        )
    except Exception as e:
        logger.error(f"Error fetching campaign {campaign_id}: {e}", exc_info=True)
        flash(f"Error loading campaign: {str(e)}", "error")
        return redirect(url_for("index"))


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

        # Note is already included in the job query result
        # No need for separate query

        return render_template("job_details.html", job=job, campaign_id=campaign_id)
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


@app.route("/campaign/<int:campaign_id>/trigger-dag", methods=["POST"])
@login_required
def trigger_campaign_dag(campaign_id: int):
    """Trigger DAG run for a specific campaign."""
    try:
        # Check campaign ownership
        campaign_service = get_campaign_service()
        campaign = campaign_service.get_campaign_by_id(campaign_id)
        if not campaign:
            flash(f"Campaign {campaign_id} not found", "error")
            return redirect(url_for("index"))

        if not current_user.is_admin and campaign.get("user_id") != current_user.user_id:
            flash("You do not have permission to trigger DAG for this campaign.", "error")
            return redirect(url_for("index"))

        airflow_client = get_airflow_client()
        if not airflow_client:
            flash("Airflow API is not configured.", "error")
            return redirect(url_for("view_campaign", campaign_id=campaign_id))

        # Trigger DAG with campaign_id in conf
        airflow_client.trigger_dag(dag_id=DEFAULT_DAG_ID, conf={"campaign_id": campaign_id})
        flash("DAG triggered successfully!", "success")
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)
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
