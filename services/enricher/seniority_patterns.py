"""Seniority level patterns for job enrichment.

This module contains patterns used to identify seniority levels in job titles
and descriptions. Patterns are organized by seniority level, from lowest to highest.
"""

# Seniority level patterns
# Each key represents a seniority level, and the value is a list of patterns
# that indicate that seniority level in job titles/descriptions
SENIORITY_PATTERNS = {
    "intern": ["intern", "internship", "co-op", "coop"],
    "junior": [
        "junior",
        "jr",
        "entry",
        "entry-level",
        "entry level",
        "associate",
        "associate level",
    ],
    "mid": ["mid", "mid-level", "mid level", "intermediate", "level 2", "ii"],
    "senior": ["senior", "sr", "lead", "leading", "principal", "staff", "level 3", "iii", "iv"],
    "executive": ["director", "vp", "vice president", "cfo", "cto", "ceo", "executive"],
}
