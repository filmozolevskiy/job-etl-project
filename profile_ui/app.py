"""
Profile Management UI

Flask web interface for managing job search profiles.
Provides CRUD operations for marts.profile_preferences table.
"""

import logging
import os
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")


def get_db_connection():
    """
    Get database connection using environment variables.

    Returns:
        psycopg2 connection object
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        database=os.getenv("POSTGRES_DB", "job_search_db"),
    )


def get_next_profile_id():
    """
    Get the next available profile_id.

    Returns:
        int: Next profile_id to use
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(profile_id), 0) + 1 as next_id
                FROM marts.profile_preferences
            """)
            result = cur.fetchone()
            return result[0] if result else 1
    finally:
        conn.close()


@app.route("/")
def index():
    """List all profiles."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    profile_id,
                    profile_name,
                    is_active,
                    query,
                    location,
                    country,
                    email,
                    total_run_count,
                    last_run_at,
                    last_run_status,
                    last_run_job_count,
                    created_at,
                    updated_at
                FROM marts.profile_preferences
                ORDER BY profile_id DESC
            """)
            profiles = cur.fetchall()

        return render_template("list_profiles.html", profiles=profiles)
    except Exception as e:
        logger.error(f"Error fetching profiles: {e}", exc_info=True)
        flash(f"Error loading profiles: {str(e)}", "error")
        return render_template("list_profiles.html", profiles=[])
    finally:
        conn.close()


@app.route("/profile/<int:profile_id>")
def view_profile(profile_id):
    """View a single profile with details."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    profile_id,
                    profile_name,
                    is_active,
                    query,
                    location,
                    country,
                    date_window,
                    email,
                    skills,
                    min_salary,
                    max_salary,
                    remote_preference,
                    seniority,
                    total_run_count,
                    last_run_at,
                    last_run_status,
                    last_run_job_count,
                    created_at,
                    updated_at
                FROM marts.profile_preferences
                WHERE profile_id = %s
            """,
                (profile_id,),
            )

            profile = cur.fetchone()

            if not profile:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))

            return render_template("view_profile.html", profile=profile)
    except Exception as e:
        logger.error(f"Error fetching profile {profile_id}: {e}", exc_info=True)
        flash(f"Error loading profile: {str(e)}", "error")
        return redirect(url_for("index"))
    finally:
        conn.close()


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

        # Get next profile_id
        profile_id = get_next_profile_id()
        now = datetime.now()

        # Insert into database
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO marts.profile_preferences (
                        profile_id,
                        profile_name,
                        is_active,
                        query,
                        location,
                        country,
                        date_window,
                        email,
                        skills,
                        min_salary,
                        max_salary,
                        remote_preference,
                        seniority,
                        created_at,
                        updated_at,
                        total_run_count,
                        last_run_status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 'pending'
                    )
                """,
                    (
                        profile_id,
                        profile_name,
                        is_active,
                        query,
                        location,
                        country.lower(),
                        date_window,
                        email if email else None,
                        skills if skills else None,
                        min_salary_val,
                        max_salary_val,
                        remote_preference if remote_preference else None,
                        seniority if seniority else None,
                        now,
                        now,
                    ),
                )
                conn.commit()

            flash(f"Profile '{profile_name}' created successfully!", "success")
            return redirect(url_for("view_profile", profile_id=profile_id))
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating profile: {e}", exc_info=True)
            flash(f"Error creating profile: {str(e)}", "error")
            return render_template("create_profile.html", form_data=request.form)
        finally:
            conn.close()

    # GET request - show form
    return render_template("create_profile.html")


@app.route("/profile/<int:profile_id>/edit", methods=["GET", "POST"])
def edit_profile(profile_id):
    """Edit an existing profile."""
    conn = get_db_connection()

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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM marts.profile_preferences WHERE profile_id = %s", (profile_id,)
                )
                profile = cur.fetchone()
            return render_template("edit_profile.html", profile=profile)

        # Convert salary to numeric or None
        min_salary_val = float(min_salary) if min_salary else None
        max_salary_val = float(max_salary) if max_salary else None

        # Update database
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE marts.profile_preferences SET
                        profile_name = %s,
                        is_active = %s,
                        query = %s,
                        location = %s,
                        country = %s,
                        date_window = %s,
                        email = %s,
                        skills = %s,
                        min_salary = %s,
                        max_salary = %s,
                        remote_preference = %s,
                        seniority = %s,
                        updated_at = %s
                    WHERE profile_id = %s
                """,
                    (
                        profile_name,
                        is_active,
                        query,
                        location,
                        country.lower(),
                        date_window,
                        email if email else None,
                        skills if skills else None,
                        min_salary_val,
                        max_salary_val,
                        remote_preference if remote_preference else None,
                        seniority if seniority else None,
                        datetime.now(),
                        profile_id,
                    ),
                )
                conn.commit()

            flash(f"Profile '{profile_name}' updated successfully!", "success")
            return redirect(url_for("view_profile", profile_id=profile_id))
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating profile {profile_id}: {e}", exc_info=True)
            flash(f"Error updating profile: {str(e)}", "error")
            # Re-fetch profile for display
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM marts.profile_preferences WHERE profile_id = %s", (profile_id,)
                )
                profile = cur.fetchone()
            return render_template("edit_profile.html", profile=profile)
        finally:
            conn.close()

    # GET request - fetch and display profile
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM marts.profile_preferences WHERE profile_id = %s
            """,
                (profile_id,),
            )
            profile = cur.fetchone()

            if not profile:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))

            return render_template("edit_profile.html", profile=profile)
    except Exception as e:
        logger.error(f"Error fetching profile {profile_id}: {e}", exc_info=True)
        flash(f"Error loading profile: {str(e)}", "error")
        return redirect(url_for("index"))
    finally:
        conn.close()


@app.route("/profile/<int:profile_id>/toggle-active", methods=["POST"])
def toggle_active(profile_id):
    """Toggle is_active status of a profile."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get current status
            cur.execute(
                "SELECT is_active FROM marts.profile_preferences WHERE profile_id = %s",
                (profile_id,),
            )
            result = cur.fetchone()

            if not result:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))

            new_status = not result[0]

            # Update status
            cur.execute(
                """
                UPDATE marts.profile_preferences
                SET is_active = %s, updated_at = %s
                WHERE profile_id = %s
            """,
                (new_status, datetime.now(), profile_id),
            )
            conn.commit()

            status_text = "activated" if new_status else "deactivated"
            flash(f"Profile {profile_id} {status_text} successfully!", "success")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error toggling profile {profile_id}: {e}", exc_info=True)
        flash(f"Error updating profile: {str(e)}", "error")
    finally:
        conn.close()

    return redirect(url_for("view_profile", profile_id=profile_id))


@app.route("/profile/<int:profile_id>/delete", methods=["POST"])
def delete_profile(profile_id):
    """Delete a profile."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get profile name for flash message
            cur.execute(
                "SELECT profile_name FROM marts.profile_preferences WHERE profile_id = %s",
                (profile_id,),
            )
            result = cur.fetchone()

            if not result:
                flash(f"Profile {profile_id} not found", "error")
                return redirect(url_for("index"))

            profile_name = result[0]

            # Delete profile
            cur.execute(
                "DELETE FROM marts.profile_preferences WHERE profile_id = %s", (profile_id,)
            )
            conn.commit()

            flash(f"Profile '{profile_name}' deleted successfully!", "success")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting profile {profile_id}: {e}", exc_info=True)
        flash(f"Error deleting profile: {str(e)}", "error")
    finally:
        conn.close()

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
