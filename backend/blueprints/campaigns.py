import logging
import re

from config import Config
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.errors import _sanitize_error_message
from utils.services import (
    get_airflow_client,
    get_campaign_service,
    get_job_service,
    get_user_service,
)
from utils.validators import _join_json_array_values, _safe_strip

logger = logging.getLogger(__name__)
campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/api/campaigns")


@campaigns_bp.route("/<int:campaign_id>/status", methods=["GET"])
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


@campaigns_bp.route("", methods=["GET"])
@jwt_required()
def api_list_campaigns():
    """Campaigns list API endpoint returning JSON list."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        service = get_campaign_service()
        job_service = get_job_service()

        if is_admin:
            campaigns = service.get_all_campaigns(user_id=None)
        else:
            campaigns = service.get_all_campaigns(user_id=user_id)

        campaign_ids = [c.get("campaign_id") for c in campaigns if c.get("campaign_id")]
        job_counts = {}
        if campaign_ids:
            try:
                job_counts = job_service.get_job_counts_for_campaigns(campaign_ids)
            except Exception as e:
                logger.debug(f"Could not get job counts for campaigns: {e}")

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


@campaigns_bp.route("/<int:campaign_id>", methods=["GET"])
@jwt_required()
def api_get_campaign(campaign_id: int):
    """Get campaign details API endpoint."""
    try:
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

        if not is_admin and campaign.get("user_id") != user_id:
            return jsonify({"error": "You do not have permission to view this campaign"}), 403

        return jsonify({"campaign": campaign}), 200
    except Exception as e:
        logger.error(f"Error fetching campaign {campaign_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@campaigns_bp.route("", methods=["POST"])
@jwt_required()
def api_create_campaign():
    """Create campaign API endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id = get_jwt_identity()
        json_data = request.json

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
            _join_json_array_values(
                json_data, "remote_preference", Config.ALLOWED_REMOTE_PREFERENCES
            )
            or None
        )
        seniority = (
            _join_json_array_values(json_data, "seniority", Config.ALLOWED_SENIORITY) or None
        )
        company_size_preference = (
            _join_json_array_values(
                json_data, "company_size_preference", Config.ALLOWED_COMPANY_SIZES
            )
            or None
        )
        employment_type_preference = (
            _join_json_array_values(
                json_data, "employment_type_preference", Config.ALLOWED_EMPLOYMENT_TYPES
            )
            or None
        )
        ranking_weights = json_data.get("ranking_weights") or None
        is_active = json_data.get("is_active", True)

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


@campaigns_bp.route("/<int:campaign_id>", methods=["PUT"])
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

        if not is_admin and campaign.get("user_id") != user_id:
            return jsonify({"error": "You do not have permission to update this campaign"}), 403

        json_data = request.json

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
            _join_json_array_values(
                json_data, "remote_preference", Config.ALLOWED_REMOTE_PREFERENCES
            )
            or None
        )
        seniority = (
            _join_json_array_values(json_data, "seniority", Config.ALLOWED_SENIORITY) or None
        )
        company_size_preference = (
            _join_json_array_values(
                json_data, "company_size_preference", Config.ALLOWED_COMPANY_SIZES
            )
            or None
        )
        employment_type_preference = (
            _join_json_array_values(
                json_data, "employment_type_preference", Config.ALLOWED_EMPLOYMENT_TYPES
            )
            or None
        )
        ranking_weights = json_data.get("ranking_weights") or None
        is_active = json_data.get("is_active", True)

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


@campaigns_bp.route("/<int:campaign_id>/toggle-active", methods=["POST"])
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


@campaigns_bp.route("/<int:campaign_id>", methods=["DELETE"])
@jwt_required()
def api_delete_campaign(campaign_id: int):
    """Delete campaign API endpoint."""
    try:
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


@campaigns_bp.route("/<int:campaign_id>/trigger-dag", methods=["POST"])
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
            )

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
            dag_id=Config.DEFAULT_DAG_ID, conf={"campaign_id": campaign_id}
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
