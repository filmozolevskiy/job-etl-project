import logging
from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..utils.services import get_campaign_service, get_job_service, get_user_service
from ..utils.errors import _sanitize_error_message

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

        stats = campaign_service.get_dashboard_stats(user_id=target_user_id)
        recent_jobs = job_service.get_recent_jobs(user_id=target_user_id, limit=5)

        return (
            jsonify(
                {
                    "stats": stats,
                    "recent_jobs": recent_jobs,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return jsonify({"error": _sanitize_error_message(e)}), 500
