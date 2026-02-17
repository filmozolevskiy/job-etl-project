import logging

from config import get_airflow_ui_url
from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.errors import _sanitize_error_message
from utils.services import get_campaign_service, get_job_service, get_user_service

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("", methods=["GET"])
@jwt_required()
def api_dashboard():
    """Get dashboard statistics."""
    try:
        user_id = get_jwt_identity()
        campaign_service = get_campaign_service()
        job_service = get_job_service()
        user_service = get_user_service()

        # Get user info to check if admin
        user = user_service.get_user_by_id(user_id)
        is_admin = user.get("is_admin", False) if user else False

        # If admin, show all data, otherwise only user's data
        target_user_id = None if is_admin else user_id

        stats_raw = campaign_service.get_dashboard_stats(user_id=target_user_id)
        recent_jobs = job_service.get_recent_jobs(user_id=target_user_id, limit=5)

        # Format for frontend DashboardStats interface
        formatted_stats = {
            "active_campaigns_count": stats_raw.get("active_campaigns", 0),
            "total_campaigns_count": stats_raw.get("total_campaigns", 0),
            "jobs_processed_count": stats_raw.get("jobs_processed", 0),
            "success_rate": stats_raw.get("success_rate", 0),
            "recent_jobs": recent_jobs,
            "activity_data": stats_raw.get("activity_data", []),
            "airflow_ui_url": get_airflow_ui_url(),
        }

        return jsonify(formatted_stats), 200

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return jsonify({"error": _sanitize_error_message(e)}), 500
