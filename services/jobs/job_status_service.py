"""Service for managing job status."""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.database import Database

from .queries import (
    GET_JOB_STATUS,
    GET_STATUS_HISTORY_BY_JOB,
    GET_STATUS_HISTORY_BY_JOB_AND_USER,
    GET_STATUS_HISTORY_BY_USER,
    INSERT_STATUS_HISTORY,
    UPSERT_JOB_STATUS,
)

logger = logging.getLogger(__name__)


class JobStatusService:
    """Service for managing job status."""

    def __init__(self, database: Database):
        """Initialize the job status service.

        Args:
            database: Database connection interface
        """
        if not database:
            raise ValueError("Database is required")
        self.db = database

    def get_status(self, jsearch_job_id: str, user_id: int) -> dict[str, Any] | None:
        """Get status for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID

        Returns:
            Status dictionary or None if not found (defaults to 'waiting')
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_JOB_STATUS, (jsearch_job_id, user_id))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

            if not row:
                return None

            return dict(zip(columns, row))

    def upsert_status(self, jsearch_job_id: str, user_id: int, status: str) -> int:
        """Insert or update status for a job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID
            status: Application status (waiting, applied, approved, rejected, interview, offer, archived)

        Returns:
            Status ID
        """
        valid_statuses = [
            "waiting",
            "applied",
            "approved",
            "rejected",
            "interview",
            "offer",
            "archived",
        ]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

        try:
            # Get old status before updating
            old_status_record = self.get_status(jsearch_job_id, user_id)
            old_status = old_status_record["status"] if old_status_record else None

            with self.db.get_cursor() as cur:
                cur.execute(UPSERT_JOB_STATUS, (jsearch_job_id, user_id, status))
                result = cur.fetchone()
                if result:
                    status_id = result[0]
                    logger.info(
                        f"Upserted status {status} for job {jsearch_job_id} by user {user_id}"
                    )

                    # Record history if status changed
                    if old_status != status:
                        metadata = {
                            "old_status": old_status,
                            "new_status": status,
                        }
                        self.record_status_history(
                            jsearch_job_id=jsearch_job_id,
                            user_id=user_id,
                            status="status_changed",
                            change_type="status_change",
                            changed_by="user",
                            changed_by_user_id=user_id,
                            metadata=metadata,
                        )

                    return status_id
                else:
                    raise ValueError("Failed to upsert status")
        except Exception as e:
            logger.error(f"Error upserting status: {e}", exc_info=True)
            raise

    def record_status_history(
        self,
        jsearch_job_id: str,
        user_id: int,
        status: str,
        change_type: str,
        changed_by: str,
        changed_by_user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> int:
        """Record a status history entry.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID for whom this history entry is recorded
            status: Status value (job_found, updated_by_ai, approved, etc.)
            change_type: Category of change (extraction, enrichment, user_action, etc.)
            changed_by: Who made the change (system, user, ai_enricher, chatgpt_enricher)
            changed_by_user_id: User ID who made the change (None if system/AI)
            metadata: Dictionary with detailed change information
            notes: Optional notes about the change

        Returns:
            History ID
        """
        metadata_json = json.dumps(metadata) if metadata else None

        try:
            with self.db.get_cursor() as cur:
                cur.execute(
                    INSERT_STATUS_HISTORY,
                    (
                        jsearch_job_id,
                        user_id,
                        status,
                        change_type,
                        changed_by,
                        changed_by_user_id,
                        metadata_json,
                        notes,
                    ),
                )
                result = cur.fetchone()
                if result:
                    history_id = result[0]
                    logger.debug(
                        f"Recorded status history: {status} for job {jsearch_job_id}, user {user_id}"
                    )
                    return history_id
                else:
                    raise ValueError("Failed to record status history")
        except Exception as e:
            logger.error(f"Error recording status history: {e}", exc_info=True)
            raise

    def record_job_found(
        self,
        jsearch_job_id: str,
        user_id: int,
        campaign_id: int | None = None,
    ) -> int:
        """Record that a job was first found/extracted.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID who owns the campaign
            campaign_id: Optional campaign ID that found this job

        Returns:
            History ID
        """
        metadata = {}
        if campaign_id:
            metadata["campaign_id"] = campaign_id

        return self.record_status_history(
            jsearch_job_id=jsearch_job_id,
            user_id=user_id,
            status="job_found",
            change_type="extraction",
            changed_by="system",
            metadata=metadata if metadata else None,
        )

    def record_ai_update(
        self,
        jsearch_job_id: str,
        user_id: int,
        enrichment_type: str,
        enrichment_details: dict[str, Any] | None = None,
    ) -> int:
        """Record that a job was updated by AI enrichment.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID who owns the campaign
            enrichment_type: Type of enrichment (system or ai_enricher)
            enrichment_details: Dictionary with details about what was enriched

        Returns:
            History ID
        """
        # Map enrichment types to status values
        if enrichment_type == "system":
            status = "updated_by_system"
        elif enrichment_type == "ai_enricher":
            status = "updated_by_ai"
        else:
            # Fallback for old values during migration
            status = "updated_by_ai"
            if enrichment_type == "chatgpt_enricher":
                enrichment_type = "ai_enricher"
            elif enrichment_type == "ai_enricher_old":
                enrichment_type = "system"

        metadata = {"enrichment_type": enrichment_type}
        if enrichment_details:
            metadata.update(enrichment_details)

        return self.record_status_history(
            jsearch_job_id=jsearch_job_id,
            user_id=user_id,
            status=status,
            change_type="enrichment",
            changed_by=enrichment_type,
            metadata=metadata,
        )

    def record_document_change(
        self,
        jsearch_job_id: str,
        user_id: int,
        change_action: str,
        document_details: dict[str, Any] | None = None,
    ) -> int:
        """Record that documents were uploaded or changed for a job.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID who made the change
            change_action: Action type (uploaded or changed)
            document_details: Dictionary with document information (resume_id, cover_letter_id, etc.)

        Returns:
            History ID
        """
        status = "documents_uploaded" if change_action == "uploaded" else "documents_changed"
        metadata = {"action": change_action}
        if document_details:
            metadata.update(document_details)

        return self.record_status_history(
            jsearch_job_id=jsearch_job_id,
            user_id=user_id,
            status=status,
            change_type="document_change",
            changed_by="user",
            changed_by_user_id=user_id,
            metadata=metadata,
        )

    def record_note_change(
        self,
        jsearch_job_id: str,
        user_id: int,
        change_action: str,
        note_id: int | None = None,
        note_preview: str | None = None,
    ) -> int:
        """Record that a note was added, updated, or deleted.

        .. deprecated::
            Note changes are no longer tracked in job status history per product requirements.
            This method is kept for backward compatibility but should not be used in new code.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID who made the change
            change_action: Action type (added, updated, or deleted)
            note_id: Optional note ID
            note_preview: Optional preview of note content (truncated if long)

        Returns:
            History ID
        """
        status_map = {
            "added": "note_added",
            "updated": "note_updated",
            "deleted": "note_deleted",
        }
        status = status_map.get(change_action, "note_changed")

        metadata = {"action": change_action}
        if note_id:
            metadata["note_id"] = note_id
        if note_preview:
            # Truncate note preview to 200 characters
            metadata["note_preview"] = note_preview[:200]

        return self.record_status_history(
            jsearch_job_id=jsearch_job_id,
            user_id=user_id,
            status=status,
            change_type="note_change",
            changed_by="user",
            changed_by_user_id=user_id,
            metadata=metadata,
        )

    def get_status_history(
        self,
        jsearch_job_id: str,
        user_id: int,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get status history for a specific job and user.

        Args:
            jsearch_job_id: Job ID
            user_id: User ID
            limit: Maximum number of history entries to return (optional)

        Returns:
            List of history dictionaries, ordered by created_at ASC (oldest first)
        """
        if limit is not None and (limit <= 0 or limit > 10000):
            raise ValueError("limit must be between 1 and 10000")

        query = GET_STATUS_HISTORY_BY_JOB_AND_USER
        params: tuple[str, int] | tuple[str, int, int]
        if limit:
            query += " LIMIT %s"
            params = (jsearch_job_id, user_id, limit)
        else:
            params = (jsearch_job_id, user_id)

        with self.db.get_cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            history = []
            for row in rows:
                entry = dict(zip(columns, row))
                # Parse metadata JSONB if present
                if entry.get("metadata") and isinstance(entry["metadata"], str):
                    try:
                        entry["metadata"] = json.loads(entry["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                history.append(entry)

            return history

    def get_user_status_history(
        self,
        user_id: int,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get all status history for a user across all jobs.

        Args:
            user_id: User ID
            limit: Maximum number of history entries to return (optional)
            offset: Number of entries to skip for pagination

        Returns:
            List of history dictionaries, ordered by created_at ASC (oldest first)
        """
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if limit is not None and (limit <= 0 or limit > 10000):
            raise ValueError("limit must be between 1 and 10000")

        query = GET_STATUS_HISTORY_BY_USER
        params: tuple[int] | tuple[int, int] | tuple[int, int, int]
        if limit:
            query += " LIMIT %s OFFSET %s"
            params = (user_id, limit, offset)
        else:
            params = (user_id,)

        with self.db.get_cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            history = []
            for row in rows:
                entry = dict(zip(columns, row))
                # Parse metadata JSONB if present
                if entry.get("metadata") and isinstance(entry["metadata"], str):
                    try:
                        entry["metadata"] = json.loads(entry["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                history.append(entry)

            return history

    def get_job_status_history(
        self,
        jsearch_job_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get all status history for a job across all users.

        Args:
            jsearch_job_id: Job ID
            limit: Maximum number of history entries to return (optional)

        Returns:
            List of history dictionaries, ordered by created_at ASC (oldest first)
        """
        if limit is not None and (limit <= 0 or limit > 10000):
            raise ValueError("limit must be between 1 and 10000")

        query = GET_STATUS_HISTORY_BY_JOB
        params: tuple[str] | tuple[str, int]
        if limit:
            query += " LIMIT %s"
            params = (jsearch_job_id, limit)
        else:
            params = (jsearch_job_id,)

        with self.db.get_cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            history = []
            for row in rows:
                entry = dict(zip(columns, row))
                # Parse metadata JSONB if present
                if entry.get("metadata") and isinstance(entry["metadata"], str):
                    try:
                        entry["metadata"] = json.loads(entry["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                history.append(entry)

            return history
