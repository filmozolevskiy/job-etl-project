import logging

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.errors import _sanitize_error_message
from utils.services import get_cover_letter_service, get_resume_service

logger = logging.getLogger(__name__)
documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


@documents_bp.route("", methods=["GET"])
@jwt_required()
def api_get_documents():
    """Get documents list API endpoint."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        cover_letter_service = get_cover_letter_service()

        resumes = resume_service.get_user_resumes(user_id=user_id, in_documents_section=True)
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=user_id, in_documents_section=True
        )

        return jsonify({"resumes": resumes or [], "cover_letters": cover_letters or []}), 200
    except Exception as e:
        logger.error(f"Error fetching documents: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/resume/upload", methods=["POST"])
@jwt_required()
def api_upload_resume_documents():
    """Upload a resume (documents section) API endpoint."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        user_id = get_jwt_identity()
        file = request.files["file"]
        resume_name = request.form.get("resume_name", "").strip() or None

        resume_service = get_resume_service()
        resume_service.upload_resume(
            user_id=user_id,
            file=file,
            resume_name=resume_name,
            in_documents_section=True,
        )

        return jsonify({"message": "Resume uploaded successfully"}), 201
    except Exception as e:
        logger.error(f"Error uploading resume (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/resume/<int:resume_id>", methods=["DELETE"])
@jwt_required()
def api_delete_resume_documents(resume_id: int):
    """Delete a resume (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        result = resume_service.delete_resume(resume_id=resume_id, user_id=user_id)

        if not result:
            return jsonify({"error": "Resume not found"}), 404

        return jsonify({"message": "Resume deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting resume (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/resume/<int:resume_id>/download", methods=["GET"])
@jwt_required()
def api_download_resume_documents(resume_id: int):
    """Download a resume (documents section) API endpoint."""
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
    except Exception as e:
        logger.error(f"Error downloading resume (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/cover-letter/create", methods=["POST"])
@jwt_required()
def api_create_cover_letter_documents():
    """Create or upload a cover letter (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()

        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or None
            cover_letter_service.upload_cover_letter_file(
                user_id=user_id,
                file=file,
                cover_letter_name=cover_letter_name,
                jsearch_job_id=None,
                in_documents_section=True,
            )
        else:
            cover_letter_text = request.form.get("cover_letter_text", "").strip()
            cover_letter_name = request.form.get("cover_letter_name", "").strip() or "Cover Letter"
            if not cover_letter_text:
                return jsonify({"error": "Cover letter text is required"}), 400

            cover_letter_service.create_cover_letter(
                user_id=user_id,
                cover_letter_name=cover_letter_name,
                cover_letter_text=cover_letter_text,
                jsearch_job_id=None,
                in_documents_section=True,
            )

        return jsonify({"message": "Cover letter created successfully"}), 201
    except Exception as e:
        logger.error(f"Error creating cover letter (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/cover-letter/<int:cover_letter_id>", methods=["GET", "DELETE"])
@jwt_required()
def api_cover_letter_documents(cover_letter_id: int):
    """Get or delete a cover letter (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()

        if request.method == "DELETE":
            result = cover_letter_service.delete_cover_letter(
                cover_letter_id=cover_letter_id, user_id=user_id
            )
            if not result:
                return jsonify({"error": "Cover letter not found"}), 404
            return jsonify({"message": "Cover letter deleted successfully"}), 200

        cover_letter = cover_letter_service.get_cover_letter_by_id(
            cover_letter_id=cover_letter_id, user_id=user_id
        )
        if not cover_letter:
            return jsonify({"error": "Cover letter not found"}), 404

        return jsonify(
            {
                "cover_letter_id": cover_letter.get("cover_letter_id"),
                "cover_letter_name": cover_letter.get("cover_letter_name"),
                "cover_letter_text": cover_letter.get("cover_letter_text"),
                "file_path": cover_letter.get("file_path"),
            }
        ), 200
    except Exception as e:
        logger.error(f"Error fetching cover letter (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/cover-letter/<int:cover_letter_id>/download", methods=["GET"])
@jwt_required()
def api_download_cover_letter_documents(cover_letter_id: int):
    """Download a cover letter (documents section) API endpoint."""
    try:
        user_id = get_jwt_identity()
        cover_letter_service = get_cover_letter_service()
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
        if cover_letter.get("cover_letter_text"):
            text_content = cover_letter["cover_letter_text"]
            filename = f"{cover_letter.get('cover_letter_name', 'cover_letter')}.txt"
            return Response(
                text_content.encode("utf-8"),
                mimetype="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        return jsonify({"error": "Cover letter has no content to download"}), 400
    except Exception as e:
        logger.error(f"Error downloading cover letter (API): {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


# Legacy/User routes
@documents_bp.route("/user/resumes", methods=["GET"])
@jwt_required()
def get_user_resumes():
    """Get all resumes for the current user."""
    try:
        user_id = get_jwt_identity()
        resume_service = get_resume_service()
        resumes = resume_service.get_user_resumes(user_id=user_id)
        return jsonify({"resumes": resumes or []}), 200
    except Exception as e:
        logger.error(f"Error fetching resumes: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500


@documents_bp.route("/user/cover-letters", methods=["GET"])
@jwt_required()
def get_user_cover_letters():
    """Get all cover letters for the current user."""
    try:
        user_id = get_jwt_identity()
        job_id = request.args.get("job_id")
        cover_letter_service = get_cover_letter_service()
        cover_letters = cover_letter_service.get_user_cover_letters(
            user_id=user_id, jsearch_job_id=job_id
        )
        return jsonify({"cover_letters": cover_letters or []}), 200
    except Exception as e:
        logger.error(f"Error fetching cover letters: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error_message(e)}), 500
