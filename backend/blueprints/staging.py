"""Staging slots API: list, update, release, and health checks."""

import logging
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.services import get_staging_service, get_user_service

logger = logging.getLogger(__name__)
staging_bp = Blueprint("staging", __name__, url_prefix="/api/staging")


def _require_admin():
    """Ensure current user is admin. Returns (None, None) if ok, else (response, status_code)."""
    user_id = get_jwt_identity()
    user_service = get_user_service()
    user_data = user_service.get_user_by_id(int(user_id))
    if not user_data or user_data.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    return None, None


def _serialize_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Convert slot dict for JSON: datetimes to ISO strings."""
    out = dict(slot)
    for key in ("deployed_at", "last_health_check_at", "created_at", "updated_at"):
        val = out.get(key)
        if isinstance(val, datetime):
            out[key] = val.isoformat()
    return out


@staging_bp.route("/slots", methods=["GET"])
@jwt_required()
def list_slots():
    """Return all staging slots (admin only)."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        service = get_staging_service()
        slots = service.get_all_slots()
        return jsonify([_serialize_slot(s) for s in slots])
    except Exception as e:
        logger.exception("Failed to list staging slots")
        return jsonify({"error": str(e)}), 500


@staging_bp.route("/slots/check-health", methods=["POST"])
@jwt_required()
def check_all_health():
    """Check health for all staging slots (admin only)."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        service = get_staging_service()
        results = service.check_all_slots_health()
        # Serialize datetime values in each result
        out = {}
        for slot_id, data in results.items():
            out[slot_id] = dict(data)
            if "last_health_check_at" in out[slot_id] and isinstance(
                out[slot_id]["last_health_check_at"], datetime
            ):
                out[slot_id]["last_health_check_at"] = out[slot_id][
                    "last_health_check_at"
                ].isoformat()
        return jsonify(out)
    except Exception as e:
        logger.exception("Failed to check all staging slot health")
        return jsonify({"error": str(e)}), 500


@staging_bp.route("/slots/<int:slot_id>", methods=["GET"])
@jwt_required()
def get_slot(slot_id: int):
    """Return one staging slot by id (admin only)."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        service = get_staging_service()
        slot = service.get_slot_by_id(slot_id)
        if not slot:
            return jsonify({"error": f"Slot {slot_id} not found"}), 404
        return jsonify(_serialize_slot(slot))
    except Exception as e:
        logger.exception("Failed to get staging slot %s", slot_id)
        return jsonify({"error": str(e)}), 500


@staging_bp.route("/slots/<int:slot_id>", methods=["PUT"])
@jwt_required()
def update_slot(slot_id: int):
    """Update staging slot status/metadata (admin only)."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        service = get_staging_service()
        slot = service.get_slot_by_id(slot_id)
        if not slot:
            return jsonify({"error": f"Slot {slot_id} not found"}), 404
        data = request.get_json() or {}
        service.update_slot_status(
            slot_id=slot_id,
            status=data.get("status", slot["status"]),
            owner=data.get("owner"),
            branch=data.get("branch"),
            issue_id=data.get("issue_id"),
            deployed_at=data.get("deployed_at"),
            purpose=data.get("purpose"),
        )
        updated = service.get_slot_by_id(slot_id)
        return jsonify(_serialize_slot(updated))
    except Exception as e:
        logger.exception("Failed to update staging slot %s", slot_id)
        return jsonify({"error": str(e)}), 500


@staging_bp.route("/slots/<int:slot_id>/release", methods=["POST"])
@jwt_required()
def release_slot(slot_id: int):
    """Release a staging slot (admin only)."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        service = get_staging_service()
        slot = service.get_slot_by_id(slot_id)
        if not slot:
            return jsonify({"error": f"Slot {slot_id} not found"}), 404
        service.release_slot(slot_id)
        updated = service.get_slot_by_id(slot_id)
        return jsonify(_serialize_slot(updated))
    except Exception as e:
        logger.exception("Failed to release staging slot %s", slot_id)
        return jsonify({"error": str(e)}), 500


@staging_bp.route("/slots/<int:slot_id>/check-health", methods=["POST"])
@jwt_required()
def check_slot_health(slot_id: int):
    """Check health for one staging slot (admin only)."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        service = get_staging_service()
        result = service.check_slot_health(slot_id)
        out = dict(result)
        if "last_health_check_at" in out and isinstance(out["last_health_check_at"], datetime):
            out["last_health_check_at"] = out["last_health_check_at"].isoformat()
        return jsonify(out)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Failed to check health for staging slot %s", slot_id)
        return jsonify({"error": str(e)}), 500
