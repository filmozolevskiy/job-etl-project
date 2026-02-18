import atexit
import logging
import os

from blueprints.account import account_bp
from blueprints.auth import auth_bp
from blueprints.campaigns import campaigns_bp
from blueprints.dashboard import dashboard_bp
from blueprints.documents import documents_bp
from blueprints.jobs import jobs_bp
from blueprints.system import system_bp
from config import Config
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """Application factory function."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize JWT
    jwt = JWTManager(app)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"msg": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        logger.error(f"Invalid token error: {str(error)}")
        return jsonify({"msg": f"Invalid token: {str(error)}"}), 422

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"msg": "Missing authorization header"}), 401

    # Initialize CORS
    CORS(
        app,
        origins=Config.CORS_ORIGINS,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
    )

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(system_bp)

    # Close connection pools on process exit for graceful cleanup
    from services.shared import close_all_pools

    atexit.register(close_all_pools)

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.getenv("ENVIRONMENT", "development") == "development"
    app.run(host="0.0.0.0", port=5000, debug=debug, use_reloader=debug)
