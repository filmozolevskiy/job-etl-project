import logging
import os
from pathlib import Path
from flask import Blueprint, jsonify, send_from_directory

from utils.services import get_airflow_client, build_db_connection_string
from shared import PostgreSQLDatabase
from config import Config

logger = logging.getLogger(__name__)
system_bp = Blueprint("system", __name__)


def _resolved_environment() -> str:
    """Resolve effective environment. Slot 10 is treated as production."""
    slot = os.getenv("STAGING_SLOT")
    if slot == "10":
        return "production"
    return os.getenv("ENVIRONMENT", "development")


@system_bp.route("/api/version")
def api_version():
    """Return deployment version and metadata."""
    env = _resolved_environment()
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

    env = _resolved_environment()
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


@system_bp.route("/assets/<path:filename>")
def serve_react_assets(filename: str):
    """Serve React app static assets."""
    if os.path.exists("/app/frontend/dist"):
        react_build_dir = Path("/app/frontend/dist")
    else:
        react_build_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    assets_dir = react_build_dir / "assets"
    if assets_dir.exists():
        return send_from_directory(str(assets_dir), filename)
    return jsonify({"error": "Asset not found"}), 404


@system_bp.route("/vite.svg")
def serve_vite_svg():
    """Serve vite.svg icon."""
    if os.path.exists("/app/frontend/dist"):
        react_build_dir = Path("/app/frontend/dist")
    else:
        react_build_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    vite_svg = react_build_dir / "vite.svg"
    if vite_svg.exists():
        return send_from_directory(str(react_build_dir), "vite.svg")
    return jsonify({"error": "File not found"}), 404


@system_bp.route("/", defaults={"path": ""})
@system_bp.route("/<path:path>")
def serve_react_app(path: str):
    """Catch-all route to serve React SPA."""
    if path.startswith("api/"):
        return jsonify({"error": "API endpoint not found"}), 404

    if path.startswith("assets/") or path == "vite.svg":
        return jsonify({"error": "Asset not found"}), 404

    if os.path.exists("/app/frontend/dist"):
        react_build_dir = Path("/app/frontend/dist")
    else:
        react_build_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    if not react_build_dir.exists() or not (react_build_dir / "index.html").exists():
        return jsonify(
            {
                "message": "React app is not built yet. Frontend will be served from /frontend/dist/index.html"
            }
        ), 503

    return send_from_directory(str(react_build_dir), "index.html")
