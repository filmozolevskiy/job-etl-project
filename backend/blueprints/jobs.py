import logging
from datetime import UTC, datetime

from documents import CoverLetterGenerationError
from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.decorators import rate_limit
from utils.errors import _sanitize_error_message
from utils.services import (
    get_campaign_service,
    get_cover_letter_generator,
    get_cover_letter_service,
    get_document_service,
    get_job_note_service,
    get_job_service,
    get_job_status_service,
    get_resume_service,
)

logger = logging.getLogger(__name__)
jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@jobs_bp.route("", methods=["GET"])
@jwt_required()
def api_list_jobs():
    """Jobs list API endpoint returning JSON list."""
    try:
        user_id_str = get_jwt_identity()
        if user_id_str is None:
            return jsonify({"error": "Invalid user identity in token"}), 401
        user_id = int(user_id_str)
        user_service = get_job_service()  # Wait, get_user_service was used in app.py
        # I'll use the correct service
        from utils.services import get_user_service

        user_service = get_user_service()
        user_data = user_service.get_user_by_id(user_id)
        is_admin = user_data.get("role") == "admin" if user_data else False

        campaign_id = request.args.get("campaign_id", type=int)
        job_service = get_job_service()

        if campaign_id:
            campaign_service = get_campaign_service()
            campaign = campaign_service.get_campaign_by_id(campaign_id)
            if not campaign:
                return jsonify({"error": f"Campaign {campaign_id} not found"}), 404

            if not is_admin and campaign.get("user_id") != user_id:
                return jsonify(
                    {"error": "You do not have permission to view jobs for this campaign"}
                ), 403

            jobs = job_service.get_jobs_for_campaign(campaign_id=campaign_id, user_id=user_id)
        else:
            jobs = job_service.get_jobs_for_user(user_id=user_id)

        return jsonify({"jobs": jobs or []}), 200
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>", methods=["GET"])
@jwt_required()
def api_get_job(job_id: str):
    """Get job details API endpoint."""
    try:
        user_id = get_jwt_identity()
        job_service = get_job_service()
        job = job_service.get_job_by_id(jsearch_job_id=job_id, user_id=user_id)

        if not job:
            return jsonify({"error": f"Job {job_id} not found"}), 404

        same_company_jobs = job_service.get_same_company_jobs(
            jsearch_job_id=job_id, user_id=user_id
        )
        response = jsonify({
            "job": job,
            "same_company_jobs": same_company_jobs,
        })
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response, 200
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/application-documents", methods=["GET"])
@jwt_required()
def api_get_job_application_documents(job_id: str):
    """Get application documents and user document lists for a job."""
    try:
        user_id = get_jwt_identity()
        document_service = get_document_service()
        resume_service = get_resume_service()
        cover_letter_service = get_cover_letter_service()

        application_doc = document_service.get_job_application_document(
            jsearch_job_id=job_id, user_id=user_id
        )
        user_resumes = resume_service.get_user_resumes(user_id=user_id, in_documents_section=True)
        user_cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=user_id, jsearch_job_id=None, in_documents_section=True
        )

        return jsonify(
            {
                "application_doc": application_doc,
                "user_resumes": user_resumes or [],
                "user_cover_letters": user_cover_letters or [],
            }
        ), 200
    except Exception as e:
        logger.error(f"Error fetching application documents for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/application-documents", methods=["PUT"])
@jobs_bp.route("/<job_id>/application-documents/update", methods=["POST"])
@jwt_required()
def api_update_job_application_documents(job_id: str):
    """Update application documents for a job."""
    try:
        user_id = get_jwt_identity()

        if request.is_json:
            data = request.get_json() or {}
            resume_id = data.get("resume_id")
            cover_letter_id = data.get("cover_letter_id")
            cover_letter_text = data.get("cover_letter_text")
            user_notes = data.get("user_notes")
        else:
            resume_id = request.form.get("resume_id", "").strip()
            cover_letter_id = request.form.get("cover_letter_id", "").strip()
            cover_letter_text = request.form.get("cover_letter_text", "").strip() or None
            user_notes = request.form.get("user_notes", "").strip() or None

        # Normalize IDs
        def normalize_id(val):
            if val is None:
                return None
            s_val = str(val).strip().lower()
            if s_val in ["", "none", "null"]:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        resume_id = normalize_id(resume_id)
        cover_letter_id = normalize_id(cover_letter_id)

        document_service = get_document_service()
        doc = document_service.get_job_application_document(jsearch_job_id=job_id, user_id=user_id)

        if doc:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )
        else:
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=user_id,
                resume_id=resume_id,
                cover_letter_id=cover_letter_id,
                cover_letter_text=cover_letter_text,
                user_notes=user_notes,
            )

        return jsonify({"message": "Application documents updated successfully"}), 200
    except Exception as e:
        logger.error(f"Error updating application documents for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/resume/upload", methods=["POST"])
@jwt_required()
def api_upload_job_resume(job_id: str):
    """Upload a resume and link it to a job application."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        user_id = get_jwt_identity()
        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume_result = resume_service.upload_resume(
            user_id=user_id,
            file=file,
            resume_name=resume_name,
            in_documents_section=False,
        )
        resume_id = (
            resume_result.get("resume_id") if isinstance(resume_result, dict) else resume_result
        )

        # Optionally link to job
        link_to_job = request.form.get("link_to_job", "true").lower() == "true"
        if link_to_job:
            document_service = get_document_service()
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=user_id,
                resume_id=resume_id,
            )

        return jsonify({"message": "Resume uploaded successfully", "resume_id": resume_id}), 201
    except Exception as e:
        logger.error(f"Error uploading resume for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/resume/<int:resume_id>/download", methods=["GET"])
@jwt_required()
def download_resume(job_id: str, resume_id: int):
    """Download a resume file."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        file_content, filename, mime_type = resume_service.download_resume(
            resume_id=resume_id, user_id=user_id
        )
        return Response(
            file_content,
            mimetype=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError:
        return jsonify({"error": "Resume not found"}), 404
    except Exception as e:
        logger.error(f"Error downloading resume: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/resume/<int:resume_id>/link", methods=["POST"])
@jwt_required()
def link_resume_to_job(job_id: str, resume_id: int):
    """Link an existing resume to a job."""
    try:
        user_id = get_jwt_identity()
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            resume_id=resume_id,
        )
        return jsonify({"success": True, "message": "Resume linked successfully!"}), 200
    except Exception as e:
        logger.error(f"Error linking resume: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/resume/<int:resume_id>/unlink", methods=["DELETE", "POST"])
@jwt_required()
def unlink_resume_from_job(job_id: str, resume_id: int):
    """Unlink a resume from a job."""
    try:
        user_id = get_jwt_identity()
        document_service = get_document_service()
        doc = document_service.get_job_application_document(jsearch_job_id=job_id, user_id=user_id)
        if doc and doc.get("resume_id") == resume_id:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=user_id,
                resume_id=None,
            )
            return jsonify({"success": True, "message": "Resume unlinked successfully!"}), 200
        else:
            return jsonify({"error": "Resume not linked to this job"}), 400
    except Exception as e:
        logger.error(f"Error unlinking resume: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/cover-letter/create", methods=["POST"])
@jwt_required()
def api_create_job_cover_letter(job_id: str):
    """Create or upload a cover letter for a job."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()
        document_service = get_document_service()

        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter = cover_letter_service.upload_cover_letter_file(
                user_id=user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=job_id,
                in_documents_section=False,
            )
        else:
            if request.is_json:
                data = request.get_json() or {}
                cover_letter_text = data.get("cover_letter_text", "").strip()
                cover_letter_name = data.get("cover_letter_name", "").strip() or "Cover Letter"
            else:
                cover_letter_text = request.form.get("cover_letter_text", "").strip()
                cover_letter_name = (
                    request.form.get("cover_letter_name", "").strip() or "Cover Letter"
                )

            if not cover_letter_text:
                return jsonify({"error": "Cover letter text is required"}), 400

            cover_letter = cover_letter_service.create_cover_letter(
                user_id=user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=cover_letter_text,
                jsearch_job_id=job_id,
                in_documents_section=False,
            )

        cover_letter_id = cover_letter.get("cover_letter_id")

        # Optionally link to job
        link_to_job = request.form.get("link_to_job", "true").lower() == "true"
        if link_to_job:
            document_service.link_documents_to_job(
                jsearch_job_id=job_id,
                user_id=user_id,
                cover_letter_id=cover_letter_id,
            )

        return jsonify(
            {
                "cover_letter_id": cover_letter_id,
                "cover_letter_text": cover_letter.get("cover_letter_text"),
                "cover_letter_name": cover_letter.get("cover_letter_name"),
            }
        ), 201
    except Exception as e:
        logger.error(f"Error creating cover letter for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/cover-letter/generate", methods=["POST"])
@jwt_required()
@rate_limit(max_calls=5, window_seconds=60)
def generate_cover_letter(job_id: str):
    """Generate a cover letter using AI."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json() or {}
        resume_id = data.get("resume_id")
        user_comments = data.get("user_comments")

        if not resume_id:
            return jsonify({"error": "resume_id is required"}), 400

        try:
            resume_id = int(resume_id)
        except (ValueError, TypeError):
            return jsonify({"error": "resume_id must be an integer"}), 400

        generator = get_cover_letter_generator()
        user_id = get_jwt_identity()
        cover_letter = generator.generate_cover_letter(
            resume_id=resume_id,
            jsearch_job_id=job_id,
            user_id=user_id,
            user_comments=user_comments,
        )

        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            cover_letter_id=cover_letter["cover_letter_id"],
        )

        return jsonify(
            {
                "cover_letter_text": cover_letter["cover_letter_text"],
                "cover_letter_id": cover_letter["cover_letter_id"],
                "cover_letter_name": cover_letter["cover_letter_name"],
            }
        )

    except CoverLetterGenerationError as e:
        logger.error(f"Cover letter generation failed: {e}", exc_info=True)
        return jsonify(
            {"error": "Failed to generate cover letter. Please check your resume and try again."}
        ), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error generating cover letter: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/cover-letter/generation-history", methods=["GET"])
@jwt_required()
def get_cover_letter_generation_history(job_id: str):
    """Get generation history for a job."""
    try:
        cover_letter_service = get_cover_letter_service()
        user_id = get_jwt_identity()
        history = cover_letter_service.get_generation_history(
            user_id=user_id,
            jsearch_job_id=job_id,
        )
        return jsonify({"history": history})
    except Exception as e:
        logger.error(f"Error fetching generation history: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/cover-letter/<int:cover_letter_id>/download", methods=["GET"])
@jwt_required()
def download_cover_letter(job_id: str, cover_letter_id: int):
    """Download a cover letter file or text."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()

        if cover_letter_id == 0:
            document_service = get_document_service()
            doc = document_service.get_job_application_document(
                jsearch_job_id=job_id, user_id=user_id
            )
            if doc and doc.get("cover_letter_text"):
                filename = f"cover_letter_{job_id}.txt"
                return Response(
                    doc["cover_letter_text"].encode("utf-8"),
                    mimetype="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            else:
                return jsonify({"error": "Cover letter text not found"}), 404

        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=user_id
        )

        if not cover_letter:
            return jsonify({"error": "Cover letter not found"}), 404

        if cover_letter.get("file_path"):
            file_content, filename, mime_type = cover_letter_service.download_cover_letter(
                cover_letter_id=cover_letter_id, user_id=user_id
            )
            return Response(
                file_content,
                mimetype=mime_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        elif cover_letter.get("cover_letter_text"):
            text_content = cover_letter["cover_letter_text"]
            filename = f"{cover_letter.get('cover_letter_name', 'cover_letter')}.txt"
            return Response(
                text_content.encode("utf-8"),
                mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:
            return jsonify({"error": "Cover letter has no content to download"}), 400
    except ValueError:
        return jsonify({"error": "Cover letter not found"}), 404
    except Exception as e:
        logger.error(f"Error downloading cover letter: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/cover-letter/<int:cover_letter_id>/link", methods=["POST"])
@jwt_required()
def link_cover_letter_to_job(job_id: str, cover_letter_id: int):
    """Link an existing cover letter to a job."""
    try:
        user_id = get_jwt_identity()
        document_service = get_document_service()
        document_service.link_documents_to_job(
            jsearch_job_id=job_id,
            user_id=user_id,
            cover_letter_id=cover_letter_id,
        )
        return jsonify({"success": True, "message": "Cover letter linked successfully!"}), 200
    except Exception as e:
        logger.error(f"Error linking cover letter: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/cover-letter/<int:cover_letter_id>/unlink", methods=["DELETE", "POST"])
@jwt_required()
def unlink_cover_letter_from_job(job_id: str, cover_letter_id: int):
    """Unlink a cover letter from a job."""
    try:
        user_id = get_jwt_identity()
        document_service = get_document_service()
        doc = document_service.get_job_application_document(jsearch_job_id=job_id, user_id=user_id)
        if doc and doc.get("cover_letter_id") == cover_letter_id:
            document_service.update_job_application_document(
                document_id=doc["document_id"],
                user_id=user_id,
                cover_letter_id=None,
            )
            return jsonify({"success": True, "message": "Cover letter unlinked successfully!"}), 200
        else:
            return jsonify({"error": "Cover letter not linked to this job"}), 400
    except Exception as e:
        logger.error(f"Error unlinking cover letter: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/notes", methods=["GET", "POST"])
@jobs_bp.route("/<job_id>/note", methods=["GET", "POST"])
@jwt_required()
def api_job_notes(job_id: str):
    """Get or create notes for a job."""
    try:
        note_service = get_job_note_service()
        user_id = get_jwt_identity()

        if request.method == "POST":
            if not request.is_json:
                return jsonify({"error": "Missing JSON in request"}), 400
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()
            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            note_id = note_service.add_note(
                jsearch_job_id=job_id, user_id=user_id, note_text=note_text
            )
            note = note_service.get_note_by_id(note_id=note_id, user_id=user_id)
            return jsonify(
                {"note": note, "success": True, "message": "Note added successfully"}
            ), 201

        notes = note_service.get_notes(jsearch_job_id=job_id, user_id=user_id)
        return jsonify({"notes": notes or []}), 200
    except Exception as e:
        logger.error(f"Error processing notes for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/notes/<int:note_id>", methods=["PUT", "DELETE"])
@jobs_bp.route("/<job_id>/note/<int:note_id>", methods=["PUT", "DELETE"])
@jwt_required()
def api_job_note_by_id(job_id: str, note_id: int):
    """Update or delete a note for a job."""
    try:
        note_service = get_job_note_service()
        user_id = get_jwt_identity()

        if request.method == "PUT":
            if not request.is_json:
                return jsonify({"error": "Missing JSON in request"}), 400
            data = request.get_json() or {}
            note_text = data.get("note_text", "").strip()
            if not note_text:
                return jsonify({"error": "Note text is required"}), 400

            success = note_service.update_note(
                note_id=note_id, user_id=user_id, note_text=note_text
            )
            if not success:
                return jsonify({"error": "Note not found or unauthorized"}), 404
            note = note_service.get_note_by_id(note_id=note_id, user_id=user_id)
            return jsonify(
                {"note": note, "success": True, "message": "Note updated successfully"}
            ), 200

        success = note_service.delete_note(note_id=note_id, user_id=user_id)
        if not success:
            return jsonify({"error": "Note not found or unauthorized"}), 404
        return jsonify({"message": "Note deleted successfully", "success": True}), 200
    except Exception as e:
        logger.error(f"Error processing note {note_id} for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/status", methods=["POST"])
@jwt_required()
def api_update_job_status(job_id: str):
    """Update job status API endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Missing JSON in request"}), 400

        user_id = get_jwt_identity()
        json_data = request.json
        status = json_data.get("status", "").strip()

        if not status:
            return jsonify({"error": "Status is required"}), 400

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
            return jsonify(
                {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            ), 400

        status_service = get_job_status_service()
        status_service.upsert_status(jsearch_job_id=job_id, user_id=user_id, status=status)

        # Auto-link generated cover letter when status changes to "applied"
        if status == "applied":
            try:
                cover_letter_service = get_cover_letter_service()
                generated_history = cover_letter_service.get_generation_history(
                    user_id=user_id,
                    jsearch_job_id=job_id,
                )
                if generated_history:
                    latest_generated = generated_history[0]
                    document_service = get_document_service()
                    existing_doc = document_service.get_job_application_document(
                        jsearch_job_id=job_id, user_id=user_id
                    )
                    if (
                        not existing_doc
                        or existing_doc.get("cover_letter_id")
                        != latest_generated["cover_letter_id"]
                    ):
                        document_service.link_documents_to_job(
                            jsearch_job_id=job_id,
                            user_id=user_id,
                            cover_letter_id=latest_generated["cover_letter_id"],
                        )
            except Exception as e:
                logger.warning(f"Error auto-linking cover letter for job {job_id}: {e}")

        return jsonify(
            {"message": "Job status updated successfully", "success": True, "status": status}
        ), 200
    except Exception as e:
        logger.error(f"Error updating job status: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@jobs_bp.route("/<job_id>/status/history", methods=["GET"])
@jwt_required()
def get_job_status_history(job_id: str):
    """Get status history for a job."""
    try:
        status_service = get_job_status_service()
        user_id = get_jwt_identity()
        all_history = status_service.get_status_history(jsearch_job_id=job_id, user_id=user_id)

        status_history = []
        for entry in all_history:
            if entry.get("change_type") != "note_change" and entry.get("status") not in [
                "note_added",
                "note_updated",
                "note_deleted",
            ]:
                if entry.get("created_at") and isinstance(entry["created_at"], datetime):
                    if entry["created_at"].tzinfo:
                        entry["created_at"] = entry["created_at"].astimezone(UTC).isoformat()
                    else:
                        entry["created_at"] = entry["created_at"].replace(tzinfo=UTC).isoformat()
                status_history.append(entry)

        return jsonify({"history": status_history}), 200
    except Exception as e:
        logger.error(f"Error fetching status history for job {job_id}: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500
