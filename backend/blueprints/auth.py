import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token

from utils.services import get_auth_service, get_user_service
from utils.errors import _sanitize_error_message

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def api_register():
    """Register a new user via API."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if not all([username, email, password]):
            return jsonify({"error": "Username, email, and password are required"}), 400

        auth_service = get_auth_service()
        user_id = auth_service.register_user(username, email, password)

        if not user_id:
            return jsonify({"error": "Registration failed"}), 400

        # Create access token for immediate login
        access_token = create_access_token(identity=str(user_id))
        return (
            jsonify(
                {
                    "message": "User registered successfully",
                    "user_id": user_id,
                    "access_token": access_token,
                }
            ),
            201,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({"error": _sanitize_error_message(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def api_login():
    """Login a user via API."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        username_or_email = data.get("username") or data.get("email")
        password = data.get("password")

        if not all([username_or_email, password]):
            return jsonify({"error": "Username/email and password are required"}), 400

        auth_service = get_auth_service()
        user = auth_service.login_user(username_or_email, password)

        if not user:
            return jsonify({"error": "Invalid username or password"}), 401

        # Create access token
        access_token = create_access_token(identity=str(user["id"]))
        return (
            jsonify(
                {
                    "message": "Login successful",
                    "access_token": access_token,
                    "user": {
                        "id": user["id"],
                        "username": user["username"],
                        "email": user["email"],
                        "is_admin": user.get("is_admin", False),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"error": _sanitize_error_message(e)}), 500
