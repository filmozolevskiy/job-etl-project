"""Remote work type patterns for job enrichment.

This module contains patterns used to identify remote work types in job titles
and descriptions. Patterns are organized by work type.
"""

# Remote work type patterns
# Each key represents a work type, and the value is a list of patterns
# that indicate that work type in job titles/descriptions
REMOTE_PATTERNS = {
    # Note: Order matters! Check hybrid first (most specific), then remote, then onsite
    # This ensures "hybrid working environment, allowing for both remote and on-site"
    # matches "hybrid" instead of "remote"
    "hybrid": [
        "hybrid working environment",
        "hybrid work environment",
        "hybrid environment",
        "hybrid remote",
        "hybrid work",
        "hybrid position",
        "hybrid role",
        "hybrid",
        "partially remote",
        "part-time remote",
        "flexible remote",
        "remote flexible",
        "remote/hybrid",
        "hybrid/remote",
        "some remote",
        "occasional remote",
        "both remote and on-site",
        "both remote and onsite",
        "both remote and on site",
        "remote and on-site",
        "remote and onsite",
        "remote and on site",
        "combination of remote and on-site",
        "combination of remote and onsite",
    ],
    "remote": [
        "fully remote",
        "100% remote",
        "fully-remote",
        "remote work",
        "remote position",
        "remote role",
        "remote opportunity",
        "remote job",
        "work from anywhere",
        "wfa",
        "distributed team",
        "distributed",
        "remote",
        "remotely",
        "work from home",
        "work-from-home",
        "wfh",
        "work remotely",
    ],
    "onsite": [
        "on-site",
        "onsite",
        "on site",
        "in-office",
        "in office",
        "in person",
        "in-person",
        "office-based",
        "office based",
        "location-based",
        "location based",
        "must be located",
        "must relocate",
        "relocation required",
    ],
}
