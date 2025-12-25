"""
Job Ranker Service

Ranks jobs based on profile preferences and writes scores to marts.dim_ranking.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from psycopg2.extras import execute_values
from shared import Database

from .queries import GET_ACTIVE_PROFILES_FOR_RANKING, GET_JOBS_FOR_PROFILE, INSERT_RANKINGS

logger = logging.getLogger(__name__)


class JobRanker:
    """
    Service for ranking jobs based on profile preferences.

    Reads jobs from marts.fact_jobs and profiles from marts.profile_preferences,
    scores each job/profile pair, and writes rankings to marts.dim_ranking.
    """

    def __init__(self, database: Database):
        """
        Initialize the job ranker.

        Args:
            database: Database connection interface (implements Database protocol)

        Raises:
            ValueError: If database is None
        """
        if not database:
            raise ValueError("Database is required")

        self.db = database
        self._currency_rates = None  # Lazy-loaded currency rates

    def get_active_profiles(self) -> list[dict[str, Any]]:
        """
        Get all active profiles from marts.profile_preferences.

        Returns:
            List of active profile dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ACTIVE_PROFILES_FOR_RANKING)

            columns = [desc[0] for desc in cur.description]
            profiles = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.info(f"Found {len(profiles)} active profile(s) for ranking")
            return profiles

    def get_jobs_for_profile(self, profile_id: int) -> list[dict[str, Any]]:
        """
        Get jobs that were extracted for a specific profile.

        Args:
            profile_id: Profile ID to get jobs for

        Returns:
            List of job dictionaries from fact_jobs
        """
        with self.db.get_cursor() as cur:
            # Get jobs that were extracted for this profile
            # fact_jobs now includes profile_id, so we can filter directly
            cur.execute(GET_JOBS_FOR_PROFILE, (profile_id,))

            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.debug(f"Found {len(jobs)} jobs for profile {profile_id}")
            return jobs

    def calculate_job_score(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Calculate match score for a single job against a profile.

        This is a pure calculation function that computes how well a job matches a profile.
        It does NOT write to database or modify any state - it only returns a score.

        Scoring factors support multiple preferences (comma-separated values):
        - Remote Preference: Can select multiple (remote, hybrid, onsite)
        - Seniority: Can select multiple levels (entry, mid, senior, lead)
        - Company Size: Can select multiple ranges
        - Employment Type: Can select multiple types

        The scoring returns the best match score if job matches any of the selected preferences.

        Scoring factors (0-100 scale):
        - Location match: 15 points
        - Salary match: 15 points
        - Company size match: 10 points
        - Skills match: 15 points
        - Position name/title match: 15 points
        - Employment type match: 5 points
        - Seniority level match: 10 points
        - Remote type match: 10 points
        - Recency: 5 points

        Args:
            job: Job dictionary from fact_jobs
            profile: Profile dictionary from profile_preferences

        Returns:
            Match score from 0-100 (higher = better match)
        """
        score = 0.0

        # Factor 1: Location match (0-15 points)
        location_score = self._score_location_match(job, profile)
        score += location_score * 15.0

        # Factor 2: Salary match (0-15 points)
        salary_score = self._score_salary_match(job, profile)
        score += salary_score * 15.0

        # Factor 3: Company size match (0-10 points)
        company_size_score = self._score_company_size_match(job, profile)
        score += company_size_score * 10.0

        # Factor 4: Skills match (0-15 points)
        skills_score = self._score_skills_match(job, profile)
        score += skills_score * 15.0

        # Factor 5: Position name/title match (0-15 points)
        keyword_score = self._score_keyword_match(job, profile)
        score += keyword_score * 15.0

        # Factor 6: Employment type match (0-5 points)
        employment_type_score = self._score_employment_type_match(job, profile)
        score += employment_type_score * 5.0

        # Factor 7: Seniority level match (0-10 points)
        seniority_score = self._score_seniority_match(job, profile)
        score += seniority_score * 10.0

        # Factor 8: Remote type match (0-10 points)
        remote_type_score = self._score_remote_type_match(job, profile)
        score += remote_type_score * 10.0

        # Factor 9: Recency (0-5 points)
        recency_score = self._score_recency(job)
        score += recency_score * 5.0

        # Ensure score is between 0 and 100
        return max(0.0, min(100.0, score))

    def _score_location_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score location match between job and profile (0-1 scale).

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Location match score (0.0-1.0)
        """
        job_location = (job.get("job_location") or "").lower()
        profile_location = (profile.get("location") or "").lower()
        profile_country = (profile.get("country") or "").lower()

        if not job_location:
            return 0.0

        # Exact location match
        if profile_location and profile_location in job_location:
            return 1.0

        # Country match
        if profile_country:
            # Common country name mappings
            country_mappings = {
                "ca": ["canada", "canadian"],
                "us": ["united states", "usa", "u.s.", "america"],
                "uk": ["united kingdom", "england", "britain"],
            }

            country_terms = country_mappings.get(profile_country, [profile_country])
            for term in country_terms:
                if term in job_location:
                    return 0.7  # Partial match for country

        return 0.0

    def _score_keyword_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score keyword match between profile query and job title (0-1 scale).

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Keyword match score (0.0-1.0)
        """
        job_title = (job.get("job_title") or "").lower()
        profile_query = (profile.get("query") or "").lower()

        if not profile_query or not job_title:
            return 0.0

        # Extract keywords from profile query
        query_keywords = set(re.findall(r"\b\w+\b", profile_query))

        if not query_keywords:
            return 0.0

        # Count matching keywords
        job_words = set(re.findall(r"\b\w+\b", job_title))
        matching_keywords = query_keywords.intersection(job_words)

        if not matching_keywords:
            return 0.0

        # Score based on percentage of keywords matched
        match_ratio = len(matching_keywords) / len(query_keywords)

        # Boost score if all keywords match
        if match_ratio == 1.0:
            return 1.0

        # Partial match score
        return match_ratio * 0.8  # Cap partial matches at 80%

    def _score_recency(self, job: dict[str, Any]) -> float:
        """
        Score job recency (newer = higher score, 0-1 scale).

        Args:
            job: Job dictionary

        Returns:
            Recency score (0.0-1.0)
        """
        posted_at = job.get("job_posted_at_datetime_utc")

        if not posted_at:
            return 0.5  # Neutral score if date unknown

        # Calculate days since posting
        if isinstance(posted_at, str):
            try:
                posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return 0.5

        now = datetime.now(posted_at.tzinfo) if posted_at.tzinfo else datetime.now()
        days_old = (now - posted_at).days

        # Score based on age:
        # 0 days = 1.0
        # 7 days = 0.7
        # 30 days = 0.3
        # 90+ days = 0.0

        if days_old < 0:
            return 1.0  # Future date (shouldn't happen, but handle gracefully)
        elif days_old == 0:
            return 1.0
        elif days_old <= 7:
            return 1.0 - (days_old * 0.04)  # Linear decay: 0.96, 0.92, ..., 0.72
        elif days_old <= 30:
            return 0.72 - ((days_old - 7) * 0.018)  # Continue decay to 0.3
        elif days_old <= 90:
            return 0.3 - ((days_old - 30) * 0.005)  # Slow decay to 0.0
        else:
            return 0.0

    def _load_currency_rates(self) -> dict[str, float]:
        """
        Load currency exchange rates from currency_rates.json.

        Returns:
            Dictionary mapping currency codes to exchange rates (USD per unit of currency)
        """
        if self._currency_rates is not None:
            return self._currency_rates

        # Try to find currency_rates.json in multiple locations
        possible_paths = [
            Path(__file__).parent / "currency_rates.json",
            Path("/opt/airflow/services/ranker/currency_rates.json"),
            Path("services/ranker/currency_rates.json"),
        ]

        for path in possible_paths:
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                        rates = data.get("rates", {})
                        if rates:
                            self._currency_rates = rates
                            logger.debug(f"Loaded currency rates from {path}")
                            return self._currency_rates
                except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to load currency rates from {path}: {e}")

        # Default to USD only if file not found
        logger.warning("Currency rates file not found, defaulting to USD only")
        self._currency_rates = {"USD": 1.0}
        return self._currency_rates

    def _convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """
        Convert an amount from one currency to another using exchange rates.

        Args:
            amount: Amount to convert
            from_currency: Source currency code (e.g., 'USD', 'CAD')
            to_currency: Target currency code (e.g., 'USD', 'CAD')

        Returns:
            Converted amount
        """
        if not self._validate_currency(from_currency) or not self._validate_currency(to_currency):
            logger.warning(f"Invalid currency codes: {from_currency} -> {to_currency}")
            return amount  # Return original amount if invalid

        if from_currency == to_currency:
            return amount

        rates = self._load_currency_rates()

        # Convert via USD as intermediate currency
        # Rate represents USD per unit of currency
        # To convert FROM currency TO USD: multiply by rate
        # To convert FROM USD TO currency: divide by rate

        from_rate = rates.get(from_currency.upper(), 1.0)
        to_rate = rates.get(to_currency.upper(), 1.0)

        # Convert to USD first
        usd_amount = amount * from_rate

        # Convert from USD to target currency
        converted_amount = usd_amount / to_rate

        return converted_amount

    def _validate_currency(self, currency: str | None) -> bool:
        """
        Validate currency code format.

        Args:
            currency: Currency code to validate

        Returns:
            True if valid (3-letter uppercase alphabetic), False otherwise
        """
        if not currency:
            return False
        return bool(re.match(r"^[A-Z]{3}$", currency.upper()))

    def _normalize_salary_to_annual(self, amount: float, period: str | None) -> float:
        """
        Normalize salary to annual amount based on period.

        Args:
            amount: Salary amount
            period: Salary period (year, month, week, day, hour)

        Returns:
            Annual salary amount
        """
        if not period:
            return amount  # Assume annual if not specified

        period_lower = period.lower()
        if period_lower in ("year", "annual", "annually", "yr", "y"):
            return amount
        elif period_lower in ("month", "monthly", "mo", "m"):
            return amount * 12
        elif period_lower in ("week", "weekly", "wk", "w"):
            return amount * 52
        elif period_lower in ("day", "daily", "d"):
            return amount * 260  # ~260 working days per year
        elif period_lower in ("hour", "hourly", "hr", "h"):
            return amount * 2080  # ~2080 working hours per year (40 hrs/week * 52 weeks)
        else:
            # Unknown period, assume annual
            logger.warning(f"Unknown salary period: {period}, assuming annual")
            return amount

    def _score_salary_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score salary match between job and profile (0-1 scale).

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Salary match score (0.0-1.0)
        """
        profile_min = profile.get("min_salary")
        profile_max = profile.get("max_salary")
        profile_currency = profile.get("currency") or "USD"

        job_min = job.get("job_min_salary")
        job_max = job.get("job_max_salary")
        job_currency = job.get("job_salary_currency")
        job_period = job.get("job_salary_period")

        # If no salary data, return neutral score
        if not profile_min and not profile_max:
            return 0.5  # Neutral if profile has no salary preference

        if not job_min and not job_max:
            return 0.3  # Lower score if job has no salary info

        # Normalize job salary to annual
        if job_min:
            job_min_annual = self._normalize_salary_to_annual(job_min, job_period)
        else:
            job_min_annual = None

        if job_max:
            job_max_annual = self._normalize_salary_to_annual(job_max, job_period)
        else:
            job_max_annual = None

        # Convert job salary to profile currency
        if job_min_annual and job_currency and self._validate_currency(job_currency):
            job_min_annual = self._convert_currency(job_min_annual, job_currency, profile_currency)

        if job_max_annual and job_currency and self._validate_currency(job_currency):
            job_max_annual = self._convert_currency(job_max_annual, job_currency, profile_currency)

        # Calculate match score
        job_avg = None
        if job_min_annual and job_max_annual:
            job_avg = (job_min_annual + job_max_annual) / 2
        elif job_min_annual:
            job_avg = job_min_annual
        elif job_max_annual:
            job_avg = job_max_annual

        if not job_avg:
            return 0.3

        profile_avg = None
        if profile_min and profile_max:
            profile_avg = (profile_min + profile_max) / 2
        elif profile_min:
            profile_avg = profile_min
        elif profile_max:
            profile_avg = profile_max

        if not profile_avg:
            return 0.5

        # Score based on how close job salary is to profile preference
        ratio = job_avg / profile_avg if profile_avg > 0 else 0

        if ratio >= 1.0:
            # Job pays at or above preference
            if ratio <= 1.2:
                return 1.0  # Perfect match (within 20% above)
            elif ratio <= 1.5:
                return 0.9  # Good match (20-50% above)
            else:
                return 0.7  # Acceptable (50%+ above)
        else:
            # Job pays below preference
            if ratio >= 0.9:
                return 0.8  # Close (within 10% below)
            elif ratio >= 0.7:
                return 0.5  # Moderate (10-30% below)
            elif ratio >= 0.5:
                return 0.3  # Low (30-50% below)
            else:
                return 0.1  # Very low (50%+ below)

    def _parse_company_size_numeric(self, company_size: str) -> float | None:
        """
        Parse company size string to numeric value for comparison.

        Handles various formats:
        - Range format: "501-1000" -> midpoint (750.0)
        - Single number: "500" -> 500.0
        - Text with number: "About 200 employees" -> 200.0

        Args:
            company_size: Company size string from job data

        Returns:
            Numeric value (float) or None if parsing fails
        """
        company_size_str = str(company_size).strip()

        if "-" in company_size_str:
            # Range format, take the midpoint
            parts = company_size_str.split("-")
            try:
                min_size = int(parts[0].strip())
                max_size = int(parts[1].strip())
                return (min_size + max_size) / 2
            except (ValueError, IndexError):
                pass
        else:
            # Try to extract number
            numbers = re.findall(r"\d+", company_size_str)
            if numbers:
                try:
                    return float(int(numbers[0]))
                except ValueError:
                    pass

        return None

    def _score_company_size_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score company size match (0-1 scale).

        Supports multiple company size preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Company size match score (0.0-1.0)
        """
        profile_preference_str = profile.get("company_size_preference") or ""
        company_size = job.get("company_size")

        if not profile_preference_str:
            return 0.5  # Neutral if profile has no preference

        if not company_size:
            return 0.3  # Lower score if job has no company size info

        # Parse comma-separated preferences
        profile_preferences = [p.strip() for p in profile_preference_str.split(",") if p.strip()]

        # Normalize company size values
        company_size_str = str(company_size).strip()

        # Company size ranges
        size_ranges = {
            "1-50": (1, 50),
            "51-200": (51, 200),
            "201-500": (201, 500),
            "501-1000": (501, 1000),
            "1001-5000": (1001, 5000),
            "5001-10000": (5001, 10000),
            "10000+": (10001, float("inf")),
        }

        # Extract numeric value from company_size
        job_size_num = self._parse_company_size_numeric(company_size_str)

        # Find best match among preferences
        best_score = 0.0

        for profile_preference in profile_preferences:
            if job_size_num is None:
                # Try exact match on string
                if profile_preference.lower() in company_size_str.lower():
                    best_score = max(best_score, 1.0)
                continue

            # Check if job size falls within profile preference range
            if profile_preference in size_ranges:
                min_size, max_size = size_ranges[profile_preference]
                if min_size <= job_size_num <= max_size:
                    best_score = max(best_score, 1.0)
                    continue

                # Score based on proximity to preferred range
                if job_size_num < min_size:
                    # Job is smaller - check if adjacent range
                    ratio = job_size_num / min_size if min_size > 0 else 0
                    if ratio >= 0.7:
                        best_score = max(best_score, 0.6)  # Close to lower bound
                    else:
                        best_score = max(best_score, 0.3)  # Much smaller
                else:
                    # Job is larger - check if adjacent range
                    if max_size == float("inf"):
                        best_score = max(best_score, 0.8)  # Profile wants large, job is large
                    else:
                        ratio = max_size / job_size_num if job_size_num > 0 else 0
                        if ratio >= 0.7:
                            best_score = max(best_score, 0.6)  # Close to upper bound
                        else:
                            best_score = max(best_score, 0.3)  # Much larger

            # Exact string match as fallback
            if profile_preference.lower() in company_size_str.lower():
                best_score = max(best_score, 1.0)

        return best_score if best_score > 0 else 0.3

    def _score_skills_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score skills match between job and profile (0-1 scale).

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Skills match score (0.0-1.0)
        """
        profile_skills_str = profile.get("skills") or ""
        job_skills = job.get("extracted_skills")

        if not profile_skills_str:
            return 0.5  # Neutral if profile has no skills preference

        if not job_skills:
            return 0.3  # Lower score if job has no skills info

        # Parse profile skills (semicolon or comma separated)
        profile_skills = set()
        for skill in re.split(r"[;,]", profile_skills_str):
            skill = skill.strip().lower()
            if skill:
                profile_skills.add(skill)

        if not profile_skills:
            return 0.5

        # Parse job skills (JSON array)
        job_skills_set = set()
        if isinstance(job_skills, list):
            for skill in job_skills:
                if isinstance(skill, str):
                    job_skills_set.add(skill.lower().strip())
        elif isinstance(job_skills, str):
            try:
                skills_list = json.loads(job_skills)
                if isinstance(skills_list, list):
                    for skill in skills_list:
                        if isinstance(skill, str):
                            job_skills_set.add(skill.lower().strip())
            except (json.JSONDecodeError, TypeError):
                pass

        if not job_skills_set:
            return 0.3

        # Calculate match ratio
        matching_skills = profile_skills.intersection(job_skills_set)
        match_ratio = len(matching_skills) / len(profile_skills) if profile_skills else 0

        # Score based on percentage of profile skills found in job
        if match_ratio >= 1.0:
            return 1.0  # All profile skills found
        elif match_ratio >= 0.7:
            return 0.8  # Most skills found
        elif match_ratio >= 0.5:
            return 0.6  # Half skills found
        elif match_ratio >= 0.3:
            return 0.4  # Some skills found
        else:
            return 0.2  # Few skills found

    def _score_employment_type_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score employment type match (0-1 scale).

        Supports multiple employment type preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Employment type match score (0.0-1.0)
        """
        profile_preference_str = (profile.get("employment_type_preference") or "").upper()
        job_employment_type = (job.get("job_employment_type") or "").upper()
        job_employment_types = job.get("job_employment_types")  # JSONB array
        employment_types = job.get("employment_types")  # Comma-separated string

        if not profile_preference_str:
            return 0.5  # Neutral if profile has no preference

        if not job_employment_type and not job_employment_types and not employment_types:
            return 0.3  # Lower score if job has no employment type info

        # Parse comma-separated preferences
        profile_preferences = [p.strip() for p in profile_preference_str.split(",") if p.strip()]

        # Collect all job employment types
        job_types_set = set()
        if job_employment_type:
            job_types_set.add(job_employment_type)

        # Check job_employment_types array (JSONB)
        if job_employment_types:
            if isinstance(job_employment_types, list):
                job_types_set.update([et.upper() for et in job_employment_types])
            elif isinstance(job_employment_types, str):
                try:
                    types_list = json.loads(job_employment_types)
                    if isinstance(types_list, list):
                        job_types_set.update([et.upper() for et in types_list])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Check employment_types (comma-separated string)
        if employment_types:
            types_list = [et.strip().upper() for et in str(employment_types).split(",")]
            job_types_set.update(types_list)

        # Check if any preference matches any job type
        for profile_preference in profile_preferences:
            if profile_preference in job_types_set:
                return 1.0  # Exact match

        # Partial match check (e.g., "Full-time" contains "FULLTIME")
        job_types_combined = " ".join(job_types_set).upper()
        for profile_preference in profile_preferences:
            if profile_preference in job_types_combined:
                return 0.8  # Partial match

        return 0.2  # No match

    def _score_seniority_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score seniority level match between job and profile (0-1 scale).

        Supports multiple seniority preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Seniority match score (0.0-1.0)
        """
        profile_seniority_str = (profile.get("seniority") or "").lower()
        job_seniority = (job.get("seniority_level") or "").lower()

        if not profile_seniority_str:
            return 0.5  # Neutral if profile has no seniority preference

        if not job_seniority:
            return 0.3  # Lower score if job has no seniority info

        # Parse comma-separated preferences
        profile_seniorities = [s.strip() for s in profile_seniority_str.split(",") if s.strip()]

        # Check for exact match with any preference
        if job_seniority in profile_seniorities:
            return 1.0

        # Seniority hierarchy for partial matches
        seniority_levels = {
            "intern": 1,
            "entry": 2,
            "junior": 2,
            "mid": 3,
            "senior": 4,
            "lead": 5,
            "executive": 6,
        }

        job_level = seniority_levels.get(job_seniority, 0)
        if job_level == 0:
            return 0.3  # Unknown job level

        # Find best match among preferences
        best_score = 0.0
        for profile_seniority in profile_seniorities:
            profile_level = seniority_levels.get(profile_seniority, 0)
            if profile_level == 0:
                continue

            # Score based on level difference
            level_diff = abs(profile_level - job_level)
            if level_diff == 0:
                score = 1.0
            elif level_diff == 1:
                score = 0.7  # Adjacent level (e.g., mid vs senior)
            elif level_diff == 2:
                score = 0.4  # Two levels apart
            else:
                score = 0.2  # Three or more levels apart

            best_score = max(best_score, score)

        return best_score if best_score > 0 else 0.3

    def _score_remote_type_match(self, job: dict[str, Any], profile: dict[str, Any]) -> float:
        """
        Score remote work type match between job and profile (0-1 scale).

        Supports multiple remote preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            profile: Profile dictionary

        Returns:
            Remote type match score (0.0-1.0)
        """
        profile_remote_str = (profile.get("remote_preference") or "").lower()
        job_remote_type = (job.get("remote_work_type") or "").lower()
        job_is_remote = job.get("job_is_remote", False)

        if not profile_remote_str:
            return 0.5  # Neutral if profile has no remote preference

        # If job has remote_work_type, use that; otherwise use job_is_remote
        if not job_remote_type:
            if job_is_remote:
                job_remote_type = "remote"
            else:
                job_remote_type = "onsite"

        # Parse comma-separated preferences
        profile_remotes = [r.strip() for r in profile_remote_str.split(",") if r.strip()]

        # Check for exact match with any preference
        if job_remote_type in profile_remotes:
            return 1.0

        # Find best match among preferences
        best_score = 0.0
        for profile_remote in profile_remotes:
            # Partial matches
            if profile_remote == "hybrid":
                # Hybrid matches both remote and onsite
                if job_remote_type in ("remote", "onsite"):
                    best_score = max(best_score, 0.7)
            elif profile_remote == "remote":
                # Remote preference matches hybrid but not onsite
                if job_remote_type == "hybrid":
                    best_score = max(best_score, 0.7)
                elif job_remote_type == "onsite":
                    best_score = max(best_score, 0.2)
            elif profile_remote == "onsite":
                # Onsite preference matches hybrid but not remote
                if job_remote_type == "hybrid":
                    best_score = max(best_score, 0.7)
                elif job_remote_type == "remote":
                    best_score = max(best_score, 0.2)

        return best_score if best_score > 0 else 0.3

    def rank_jobs_for_profile(self, profile: dict[str, Any]) -> int:
        """
        Process and save rankings for all jobs belonging to a profile (workflow method).

        This method orchestrates the full ranking workflow:
        1. Retrieves all jobs extracted for this profile
        2. Calculates match scores for each job using calculate_job_score()
        3. Writes all rankings to marts.dim_ranking table

        This is the main entry point for ranking jobs - it handles the complete process
        from fetching jobs to persisting rankings in the database.

        Args:
            profile: Profile dictionary from profile_preferences

        Returns:
            Number of jobs ranked and saved to database
        """
        profile_id = profile["profile_id"]
        profile_name = profile["profile_name"]

        logger.info(f"Ranking jobs for profile {profile_id} ({profile_name})")

        # Get jobs for this profile
        jobs = self.get_jobs_for_profile(profile_id)

        if not jobs:
            logger.info(f"No jobs found for profile {profile_id}")
            return 0

        # Calculate scores for each job
        rankings = []
        now = datetime.now()
        today = date.today()

        for job in jobs:
            score = self.calculate_job_score(job, profile)
            rankings.append(
                {
                    "jsearch_job_id": job["jsearch_job_id"],
                    "profile_id": profile_id,
                    "rank_score": round(score, 2),
                    "ranked_at": now,
                    "ranked_date": today,
                    "dwh_load_timestamp": now,
                    "dwh_source_system": "ranker",
                }
            )

        # Write to database
        self._write_rankings(rankings)

        logger.info(
            f"Ranked {len(rankings)} jobs for profile {profile_id} (avg score: {sum(r['rank_score'] for r in rankings) / len(rankings):.2f})"
        )

        return len(rankings)

    def _write_rankings(self, rankings: list[dict[str, Any]]):
        """
        Write rankings to marts.dim_ranking table.
        Uses INSERT ... ON CONFLICT to update existing rankings.

        Args:
            rankings: List of ranking dictionaries
        """
        if not rankings:
            return

        with self.db.get_cursor() as cur:
            # Prepare data for bulk insert
            rows = []
            for ranking in rankings:
                rows.append(
                    (
                        ranking["jsearch_job_id"],
                        ranking["profile_id"],
                        ranking["rank_score"],
                        ranking["ranked_at"],
                        ranking["ranked_date"],
                        ranking["dwh_load_timestamp"],
                        ranking["dwh_source_system"],
                    )
                )

            # Bulk insert/update using execute_values
            execute_values(cur, INSERT_RANKINGS, rows)

    def rank_all_jobs(self) -> dict[int, int]:
        """
        Rank jobs for all active profiles.

        Returns:
            Dictionary mapping profile_id to number of jobs ranked
        """
        profiles = self.get_active_profiles()

        if not profiles:
            logger.warning("No active profiles found for ranking")
            return {}

        results = {}
        for profile in profiles:
            try:
                count = self.rank_jobs_for_profile(profile)
                results[profile["profile_id"]] = count
            except Exception as e:
                logger.error(
                    f"Failed to rank jobs for profile {profile['profile_id']}: {e}", exc_info=True
                )
                results[profile["profile_id"]] = 0

        total_ranked = sum(results.values())
        logger.info(f"Ranking complete. Total jobs ranked: {total_ranked}")

        return results
