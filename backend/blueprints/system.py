import logging
import os
from pathlib import Path
from flask import Blueprint, jsonify, send_from_directory

from utils.services import get_airflow_client, build_db_connection_string
from shared import PostgreSQLDatabase
from config import Config

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


@system_bp.route("/api/health")
def api_health():
    """Health check endpoint."""
    try:
        db_conn_str = build_db_connection_string()
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
        return jsonify({"success": True, "message": "DAG triggered successfully for all campaigns!"}), 200
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
