"""
Profile Management UI

Flask web interface for managing job search profiles.
Provides CRUD operations for marts.profile_preferences table.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

# Add services directory to path

# Add services to path - works in both dev and container
# In container: /app/services
# In dev: ../services from profile_ui/
if Path("/app").exists():
    # Running in container - services are at /app/services
    sys.path.insert(0, "/app/services")
else:
    # Running locally - services are at ../services from profile_ui/
    services_path = Path(__file__).parent.parent / "services"
    sys.path.insert(0, str(services_path))

from profile_management import ProfileService
from shared import PostgreSQLDatabase

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")


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


def get_profile_service() -> ProfileService:
    """
    Get ProfileService instance with database connection.

    Returns:
        ProfileService instance
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    return ProfileService(database=database)


@app.route("/")
def index():
    """List all profiles."""
    try:
        service = get_profile_service()
        profiles = service.get_all_profiles()
        return render_template("list_profiles.html", profiles=profiles)
    except Exception as e:
        logger.error(f"Error fetching profiles: {e}", exc_info=True)
        flash(f"Error loading profiles: {str(e)}", "error")
        return render_template("list_profiles.html", profiles=[])


@app.route("/profile/<int:profile_id>")
def view_profile(profile_id):
    """View a single profile with details."""
    try:
        service = get_profile_service()
        profile = service.get_profile_by_id(profile_id)

        if not profile:
            flash(f"Profile {profile_id} not found", "error")
            return redirect(url_for("index"))

        return render_template("view_profile.html", profile=profile)
    except Exception as e:
        logger.error(f"Error fetching profile {profile_id}: {e}", exc_info=True)
        flash(f"Error loading profile: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/profile/create", methods=["GET", "POST"])
def create_profile():
    """Create a new profile."""
    if request.method == "POST":
        # Get form data
        profile_name = request.form.get("profile_name", "").strip()
        query = request.form.get("query", "").strip()
        location = request.form.get("location", "").strip()
        country = request.form.get("country", "").strip().lower()
        date_window = request.form.get("date_window", "week")
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        min_salary = request.form.get("min_salary", "").strip()
        max_salary = request.form.get("max_salary", "").strip()
        currency = request.form.get("currency", "").strip().upper()
        remote_preference = request.form.get("remote_preference", "").strip()
        seniority = request.form.get("seniority", "").strip()
        is_active = request.form.get("is_active") == "on"

        # Validation
        errors = []
        if not profile_name:
            errors.append("Profile name is required")
        if not query:
            errors.append("Search query is required")
        if not country:
            errors.append("Country is required")
        if email and "@" not in email:
            errors.append("Invalid email format")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("create_profile.html", form_data=request.form)

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary else None
        max_salary_val = float(max_salary) if max_salary else None

        try:
            service = get_profile_service()
            profile_id = service.create_profile(
                profile_name=profile_name,
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
                is_active=is_active,
            )

            flash(f"Profile '{profile_name}' created successfully!", "success")
            return redirect(url_for("view_profile", profile_id=profile_id))
        except ValueError as e:
            logger.error(f"Validation error creating profile: {e}", exc_info=True)
            flash(f"Validation error: {str(e)}", "error")
            return render_template("create_profile.html", form_data=request.form)
        except Exception as e:
            logger.error(f"Error creating profile: {e}", exc_info=True)
            flash(f"Error creating profile: {str(e)}", "error")
            return render_template("create_profile.html", form_data=request.form)

    # GET request - show form
    return render_template("create_profile.html")


@app.route("/profile/<int:profile_id>/edit", methods=["GET", "POST"])
def edit_profile(profile_id):
    """Edit an existing profile."""
    service = get_profile_service()

    if request.method == "POST":
        # Get form data
        profile_name = request.form.get("profile_name", "").strip()
        query = request.form.get("query", "").strip()
        location = request.form.get("location", "").strip()
        country = request.form.get("country", "").strip().lower()
        date_window = request.form.get("date_window", "week")
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        min_salary = request.form.get("min_salary", "").strip()
        max_salary = request.form.get("max_salary", "").strip()
        currency = request.form.get("currency", "").strip().upper()
        remote_preference = request.form.get("remote_preference", "").strip()
        seniority = request.form.get("seniority", "").strip()
        is_active = request.form.get("is_active") == "on"

        # Validation
        errors = []
        if not profile_name:
            errors.append("Profile name is required")
        if not query:
            errors.append("Search query is required")
        if not country:
            errors.append("Country is required")
        if email and "@" not in email:
            errors.append("Invalid email format")

        if errors:
            for error in errors:
                flash(error, "error")
            # Re-fetch profile for display
            profile = service.get_profile_by_id(profile_id)
            if not profile:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))
            return render_template("edit_profile.html", profile=profile)

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary else None
        max_salary_val = float(max_salary) if max_salary else None

        try:
            service.update_profile(
                profile_id=profile_id,
                profile_name=profile_name,
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
                is_active=is_active,
            )

            flash(f"Profile '{profile_name}' updated successfully!", "success")
            return redirect(url_for("view_profile", profile_id=profile_id))
        except ValueError as e:
            logger.error(f"Validation error updating profile {profile_id}: {e}", exc_info=True)
            flash(f"Validation error: {str(e)}", "error")
            # Re-fetch profile for display
            profile = service.get_profile_by_id(profile_id)
            if not profile:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))
            return render_template("edit_profile.html", profile=profile)
        except Exception as e:
            logger.error(f"Error updating profile {profile_id}: {e}", exc_info=True)
            flash(f"Error updating profile: {str(e)}", "error")
            # Re-fetch profile for display
            profile = service.get_profile_by_id(profile_id)
            if not profile:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))
            return render_template("edit_profile.html", profile=profile)

    # GET request - fetch and display profile
    try:
        profile = service.get_profile_by_id(profile_id)

        if not profile:
            flash(f"Profile {profile_id} not found", "error")
            return redirect(url_for("index"))

        return render_template("edit_profile.html", profile=profile)
    except Exception as e:
        logger.error(f"Error fetching profile {profile_id}: {e}", exc_info=True)
        flash(f"Error loading profile: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/profile/<int:profile_id>/toggle-active", methods=["POST"])
def toggle_active(profile_id):
    """Toggle is_active status of a profile."""
    try:
        service = get_profile_service()
        new_status = service.toggle_active(profile_id)

        status_text = "activated" if new_status else "deactivated"
        flash(f"Profile {profile_id} {status_text} successfully!", "success")
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Error toggling profile {profile_id}: {e}", exc_info=True)
        flash(f"Error updating profile: {str(e)}", "error")

    return redirect(url_for("view_profile", profile_id=profile_id))


@app.route("/profile/<int:profile_id>/delete", methods=["POST"])
def delete_profile(profile_id):
    """Delete a profile."""
    try:
        service = get_profile_service()
        profile_name = service.delete_profile(profile_id)

        flash(f"Profile '{profile_name}' deleted successfully!", "success")
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Error deleting profile {profile_id}: {e}", exc_info=True)
        flash(f"Error deleting profile: {str(e)}", "error")

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
