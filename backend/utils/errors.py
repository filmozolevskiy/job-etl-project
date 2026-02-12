def _sanitize_error_message(error: Exception) -> str:
    """Sanitize error messages to avoid leaking sensitive information.

    Args:
        error: Exception object

    Returns:
        Sanitized error message safe for client display
    """
    error_str = str(error).lower()

    # Remove potential file paths
    if "/" in str(error) or "\\" in str(error):
        return "File operation failed. Please check file permissions."

    # Remove database connection strings
    if "password" in error_str or "connection" in error_str or "database" in error_str:
        return "Database operation failed. Please try again."

    # Remove API keys
    if "api" in error_str and ("key" in error_str or "token" in error_str):
        return "API authentication failed. Please check configuration."

    # Generic fallback for unknown errors
    return "An unexpected error occurred. Please try again later."
