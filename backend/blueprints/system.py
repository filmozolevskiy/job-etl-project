import logging
import os

from config import Config
from flask import Blueprint, jsonify
from shared import PostgreSQLDatabase
from utils.services import build_db_connection_string, get_airflow_client

logger = logging.getLogger(__name__)
system_bp = Blueprint("system", __name__)


def api_version():
    """Return deployment version and metadata."""
    env = os.getenv("ENVIRONMENT", "development")
    payload = {
        "environment": env,
        "branch": os.getenv("DEPLOYED_BRANCH"),
        "commit_sha": os.getenv("DEPLOYED_SHA"),
        "deployed_at": os.getenv("DEPLOYED_AT"),
    }
    if env != "production":
        slot = os.getenv("STAGING_SLOT")
        if slot:
            payload["slot"] = slot
    return jsonify(payload)


@system_bp.route("/ping")
def api_ping():
    """Lightweight connectivity check - no DB, returns immediately."""
    return jsonify({"status": "ok"}), 200


@system_bp.route("/health")
def api_health():
    """Health check endpoint with DB connectivity check (5s timeout)."""
    try:
        db_conn_str = build_db_connection_string()
        # Add connect_timeout so health check doesn't hang on unreachable DB
        sep = "&" if "?" in db_conn_str else "?"
        db_conn_str = f"{db_conn_str}{sep}connect_timeout=5"
        db = PostgreSQLDatabase(connection_string=db_conn_str)
        with db.get_cursor() as cur:
            cur.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    env = os.getenv("ENVIRONMENT", "development")
    response = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "environment": env,
    }
    staging_slot = os.getenv("STAGING_SLOT")
    if staging_slot and env != "production":
        response["staging_slot"] = int(staging_slot)
    return jsonify(response)


@system_bp.route("/api/trigger-all-dags", methods=["POST"])
def trigger_all_dags():
    """Trigger DAG run for all active campaigns."""
    try:
        airflow_client = get_airflow_client()
        if not airflow_client:
            return jsonify({"error": "Airflow API is not configured."}), 500

        airflow_client.trigger_dag(dag_id=Config.DEFAULT_DAG_ID, conf={})
        return jsonify(
            {"success": True, "message": "DAG triggered successfully for all campaigns!"}
        ), 200
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
