"""Staging Management Service.

Service for managing staging slots in marts.staging_slots table.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import requests
from shared.database import Database

from .queries import (
    GET_ALL_SLOTS,
    GET_SLOT_BY_ID,
    RELEASE_SLOT,
    UPDATE_SLOT_HEALTH,
    UPDATE_SLOT_STATUS,
)

logger = logging.getLogger(__name__)


class StagingManagementService:
    """Service for managing staging slots."""

    def __init__(self, database: Database):
        """Initialize the staging management service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_all_slots(self) -> list[dict[str, Any]]:
        """Get all staging slots from the database.

        Returns:
            List of slot dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ALL_SLOTS)
            columns = [desc[0] for desc in cur.description]
            slots = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.debug(f"Retrieved {len(slots)} staging slot(s)")
        return slots

    def get_slot_by_id(self, slot_id: int) -> dict[str, Any] | None:
        """Get a single staging slot by ID.

        Args:
            slot_id: Slot ID to retrieve

        Returns:
            Slot dictionary or None if not found
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_SLOT_BY_ID, (slot_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def update_slot_status(
        self,
        slot_id: int,
        status: str,
        owner: str | None = None,
        branch: str | None = None,
        issue_id: str | None = None,
        deployed_at: datetime | str | None = None,
        purpose: str | None = None,
    ) -> None:
        """Update a staging slot's status and metadata.

        Args:
            slot_id: Slot ID to update
            status: New status (Available, In Use, Reserved)
            owner: Name of the owner
            branch: Git branch deployed
            issue_id: Linear issue ID
            deployed_at: Timestamp of deployment
            purpose: Purpose of deployment
        """
        if isinstance(deployed_at, str):
            try:
                deployed_at = datetime.fromisoformat(deployed_at.replace("Z", "+00:00"))
            except ValueError:
                deployed_at = datetime.now()
        elif deployed_at is None and status == "In Use":
            deployed_at = datetime.now()

        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_SLOT_STATUS,
                (status, owner, branch, issue_id, deployed_at, purpose, slot_id),
            )

        logger.info(f"Updated staging slot {slot_id} status to {status}")

    def release_slot(self, slot_id: int) -> None:
        """Release a staging slot (set to Available and clear metadata).

        Args:
            slot_id: Slot ID to release
        """
        with self.db.get_cursor() as cur:
            cur.execute(RELEASE_SLOT, (slot_id,))

        logger.info(f"Released staging slot {slot_id}")

    def check_slot_health(self, slot_id: int) -> dict[str, Any]:
        """Check the health of a specific staging slot.

        Probes the slot's API health endpoint and updates the database.

        Args:
            slot_id: Slot ID to check

        Returns:
            Health status dictionary
        """
        slot = self.get_slot_by_id(slot_id)
        if not slot:
            raise ValueError(f"Slot {slot_id} not found")

        api_url = slot.get("api_url")
        if not api_url:
            return {"status": "Unknown", "error": "No API URL configured"}

        health_url = f"{api_url}/health"
        health_status = "Down"
        metadata = {}

        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                health_status = "Healthy"
                metadata = response.json()
            else:
                health_status = "Degraded"
                metadata = {"status_code": response.status_code, "response": response.text[:100]}
        except requests.exceptions.RequestException as e:
            health_status = "Down"
            metadata = {"error": str(e)}

        # Update database
        now = datetime.now()
        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_SLOT_HEALTH,
                (health_status, now, json.dumps(metadata), slot_id),
            )

        logger.info(f"Checked health for slot {slot_id}: {health_status}")
        return {"health_status": health_status, "last_health_check_at": now, "metadata": metadata}

    def check_all_slots_health(self) -> dict[int, dict[str, Any]]:
        """Check health for all staging slots.

        Returns:
            Dictionary mapping slot_id to health status
        """
        slots = self.get_all_slots()
        results = {}
        for slot in slots:
            slot_id = slot["slot_id"]
            try:
                results[slot_id] = self.check_slot_health(slot_id)
            except Exception as e:
                logger.error(f"Failed to check health for slot {slot_id}: {e}")
                results[slot_id] = {"health_status": "Error", "error": str(e)}
        return results
