import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from utils.services import get_user_service, get_auth_service
from utils.errors import _sanitize_error_message

logger = logging.getLogger(__name__)
account_bp = Blueprint("account", __name__, url_prefix="/api/account")


@account_bp.route("", methods=["GET"])
@jwt_required()
def api_get_account():
    """Get user account information API endpoint."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)
        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)

        if not user_data:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"user": user_data}), 200
    except Exception as e:
        logger.error(f"Error fetching account: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@account_bp.route("/change-password", methods=["POST"])
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
        user = auth_service.authenticate_user(
            username=user_data["username"], password=current_password
        )
        if not user:
            return jsonify({"error": "Current password is incorrect"}), 400

        try:
            user_service.update_user_password(user_id, new_password)
            logger.info(f"Password updated successfully for user {user_id}")
            return jsonify({"message": "Password updated successfully"}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error changing password: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500
