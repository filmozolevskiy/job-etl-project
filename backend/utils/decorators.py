import logging
from datetime import datetime
from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from .services import get_user_service

logger = logging.getLogger(__name__)

# Rate limiting storage (in-memory, resets on restart)
_rate_limit_storage: dict[str, list[float]] = {}


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
