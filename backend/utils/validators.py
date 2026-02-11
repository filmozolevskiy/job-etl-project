# Ranking weights configuration
# Maps form field names (HTML input names) to JSON keys used in the database.
# This mapping ensures consistency between the UI form fields and the stored ranking_weights JSONB structure.
# Each weight represents a percentage (0-100) that contributes to the total ranking score.
RANKING_WEIGHT_MAPPING = {
    "ranking_weight_location_match": "location_match",  # Location matching score
    "ranking_weight_salary_match": "salary_match",  # Salary range matching score
    "ranking_weight_company_size_match": "company_size_match",  # Company size preference match
    "ranking_weight_skills_match": "skills_match",  # Skills overlap score
    "ranking_weight_keyword_match": "keyword_match",  # Job title/description keyword match
    "ranking_weight_employment_type_match": "employment_type_match",  # Employment type preference
    "ranking_weight_seniority_match": "seniority_match",  # Seniority level match
    "ranking_weight_remote_type_match": "remote_type_match",  # Remote/hybrid/onsite preference
    "ranking_weight_recency": "recency",  # Job posting recency (newer = higher)
}

WEIGHT_SUM_TOLERANCE = 0.1
MIN_WEIGHT = 0.0
MAX_WEIGHT = 100.0


def extract_ranking_weights(form_data) -> dict[str, float]:
    """
    Extract and validate ranking weights from form data.

    Maps form field names to JSON keys and validates:
    - Each weight is a valid number between 0 and 100
    - All weights sum to exactly 100% (within tolerance)

    Args:
        form_data: Flask request.form object containing ranking weight inputs

    Returns:
        Dictionary mapping JSON keys to float values (percentages), empty dict if no weights provided

    Raises:
        ValueError: If weights are invalid:
            - Non-numeric values
            - Values outside 0-100 range
            - Sum not equal to 100% (within tolerance)
    """
    weights = {}

    for form_field, json_key in RANKING_WEIGHT_MAPPING.items():
        value = form_data.get(form_field, "").strip()
        if value:
            try:
                weight = float(value)
                if weight < MIN_WEIGHT or weight > MAX_WEIGHT:
                    raise ValueError(
                        f"Ranking weight for '{json_key}' must be between {MIN_WEIGHT} and {MAX_WEIGHT}, got {weight}"
                    )
                weights[json_key] = weight
            except ValueError as e:
                # Re-raise if it's our custom validation error
                if "must be between" in str(e):
                    raise
                # Otherwise, it's a conversion error
                raise ValueError(f"Invalid number for ranking weight '{json_key}': {value}") from e

    # Validate sum if any weights provided
    if weights:
        total = sum(weights.values())
        if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Ranking weights must sum to 100%. Current total: {total:.1f}%")

    return weights


def _safe_strip(value) -> str:
    """Safely strip a value that may be None or non-string."""
    return value.strip() if isinstance(value, str) else ""


def _join_checkbox_values(form, field_name: str, allowed_values: set[str]) -> str:
    """
    Join multiple checkbox values into comma-separated string, filtering invalid values.

    Args:
        form: Flask request form object
        field_name: Name of the checkbox field
        allowed_values: Set of allowed values for validation

    Returns:
        Comma-separated string of valid values, or empty string if none
    """
    values = [v for v in form.getlist(field_name) if v in allowed_values]
    return ",".join(values) if values else ""


def _join_json_array_values(json_data: dict, field_name: str, allowed_values: set[str]) -> str:
    """
    Join multiple values from a JSON array into comma-separated string, filtering invalid values.

    Args:
        json_data: Dictionary from JSON request
        field_name: Name of the field containing the array
        allowed_values: Set of allowed values for validation

    Returns:
        Comma-separated string of valid values, or empty string if none
    """
    raw_values = json_data.get(field_name, [])
    if not isinstance(raw_values, list):
        return ""
    values = [v for v in raw_values if v in allowed_values]
    return ",".join(values) if values else ""
