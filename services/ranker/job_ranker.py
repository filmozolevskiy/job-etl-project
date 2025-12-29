"""
Job Ranker Service

Ranks jobs based on campaign preferences and writes scores to marts.dim_ranking_staging (accessed via marts.dim_ranking view).
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

from .queries import GET_ACTIVE_CAMPAIGNS_FOR_RANKING, GET_JOBS_FOR_CAMPAIGN, INSERT_RANKINGS

logger = logging.getLogger(__name__)


class JobRanker:
    """
    Service for ranking jobs based on campaign preferences.

    Reads jobs from marts.fact_jobs and campaigns from marts.job_campaigns,
    scores each job/campaign pair, and writes rankings to marts.dim_ranking_staging (accessed via marts.dim_ranking view).
    """

    def __init__(self, database: Database, config_path: str | None = None):
        """
        Initialize the job ranker.

        Args:
            database: Database connection interface (implements Database protocol)
            config_path: Optional path to ranking config JSON file. If not provided,
                        will look for ranking_config.json in the ranker directory.

        Raises:
            ValueError: If database is None
        """
        if not database:
            raise ValueError("Database is required")

        self.db = database
        self._currency_rates = None  # Lazy-loaded currency rates
        self._scoring_weights = self._load_scoring_weights(config_path)

    def get_active_campaigns(self) -> list[dict[str, Any]]:
        """
        Get all active campaigns from marts.job_campaigns.

        Returns:
            List of active campaign dictionaries
        """
        with self.db.get_cursor() as cur:
            cur.execute(GET_ACTIVE_CAMPAIGNS_FOR_RANKING)

            columns = [desc[0] for desc in cur.description]
            campaigns = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.info(f"Found {len(campaigns)} active campaign(s) for ranking")
            return campaigns

    def get_jobs_for_campaign(self, campaign_id: int) -> list[dict[str, Any]]:
        """
        Get jobs that were extracted for a specific campaign.

        Args:
            campaign_id: Campaign ID to get jobs for

        Returns:
            List of job dictionaries from fact_jobs
        """
        with self.db.get_cursor() as cur:
            # Get jobs that were extracted for this campaign
            # fact_jobs now includes campaign_id, so we can filter directly
            cur.execute(GET_JOBS_FOR_CAMPAIGN, (campaign_id,))

            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.debug(f"Found {len(jobs)} jobs for campaign {campaign_id}")
            return jobs

    def calculate_job_score(
        self, job: dict[str, Any], campaign: dict[str, Any]
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate match score for a single job against a campaign.

        This is a pure calculation function that computes how well a job matches a campaign.
        It does NOT write to database or modify any state - it only returns a score and explanation.

        Scoring factors support multiple preferences (comma-separated values):
        - Remote Preference: Can select multiple (remote, hybrid, onsite)
        - Seniority: Can select multiple levels (entry, mid, senior, lead)
        - Company Size: Can select multiple ranges
        - Employment Type: Can select multiple types

        The scoring returns the best match score if job matches any of the selected preferences.

        Scoring factors (percentages, should sum to 100%):
        - Location match: 15% (default, can be customized per campaign)
        - Salary match: 15% (default, can be customized per campaign)
        - Company size match: 10% (default, can be customized per campaign)
        - Skills match: 15% (default, can be customized per campaign)
        - Position name/title match: 15% (default, can be customized per campaign)
        - Employment type match: 5% (default, can be customized per campaign)
        - Seniority level match: 10% (default, can be customized per campaign)
        - Remote type match: 10% (default, can be customized per campaign)
        - Recency: 5% (default, can be customized per campaign)

        Note: If a campaign has custom weights set in the UI, those will be used instead of defaults.

        Args:
            job: Job dictionary from fact_jobs
            campaign: Campaign dictionary from job_campaigns

        Returns:
            Tuple of (match score from 0-100, explanation dictionary with scoring breakdown)
        """
        explanation = {}
        # Get weights from campaign if available, otherwise use config/default
        weights = self._get_weights_for_campaign(campaign)

        # Factor 1: Location match
        location_score = self._score_location_match(job, campaign)
        location_points = location_score * weights.get("location_match", 15.0)
        explanation["location_match"] = round(location_points, 2)

        # Factor 2: Salary match
        salary_score = self._score_salary_match(job, campaign)
        salary_points = salary_score * weights.get("salary_match", 15.0)
        explanation["salary_match"] = round(salary_points, 2)

        # Factor 3: Company size match
        company_size_score = self._score_company_size_match(job, campaign)
        company_size_points = company_size_score * weights.get("company_size_match", 10.0)
        explanation["company_size_match"] = round(company_size_points, 2)

        # Factor 4: Skills match
        skills_score = self._score_skills_match(job, campaign)
        skills_points = skills_score * weights.get("skills_match", 15.0)
        explanation["skills_match"] = round(skills_points, 2)

        # Factor 5: Position name/title match
        keyword_score = self._score_keyword_match(job, campaign)
        keyword_points = keyword_score * weights.get("keyword_match", 15.0)
        explanation["keyword_match"] = round(keyword_points, 2)

        # Factor 6: Employment type match
        employment_type_score = self._score_employment_type_match(job, campaign)
        employment_type_points = employment_type_score * weights.get("employment_type_match", 5.0)
        explanation["employment_type_match"] = round(employment_type_points, 2)

        # Factor 7: Seniority level match
        seniority_score = self._score_seniority_match(job, campaign)
        seniority_points = seniority_score * weights.get("seniority_match", 10.0)
        explanation["seniority_match"] = round(seniority_points, 2)

        # Factor 8: Remote type match
        remote_type_score = self._score_remote_type_match(job, campaign)
        remote_type_points = remote_type_score * weights.get("remote_type_match", 10.0)
        explanation["remote_type_match"] = round(remote_type_points, 2)

        # Factor 9: Recency
        recency_score = self._score_recency(job)
        recency_points = recency_score * weights.get("recency", 5.0)
        explanation["recency"] = round(recency_points, 2)

        # Calculate total score
        total_score = sum(explanation.values())

        # Ensure score is between 0 and 100
        final_score = max(0.0, min(100.0, total_score))
        explanation["total_score"] = round(final_score, 2)

        return final_score, explanation

    def _get_weights_for_campaign(self, campaign: dict[str, Any]) -> dict[str, float]:
        """
        Get scoring weights for a campaign.

        Checks if campaign has custom weights set in the UI (stored as JSONB).
        If ranking_weights is NULL/None or empty, falls back to config file or defaults.
        Weights are percentages and should sum to 100%.

        Note: ranking_weights should already be normalized to dict.
        This method handles the case where it might still be a string (for backward compatibility).

        Args:
            campaign: Campaign dictionary (may contain ranking_weights JSONB field, should be dict or None)

        Returns:
            Dictionary mapping factor names to weights (as percentages, e.g., 15.0 for 15%)
        """
        # Check if campaign has custom weights in JSONB column
        ranking_weights = campaign.get("ranking_weights")

        if ranking_weights:
            # Normalize to dict if still a string (backward compatibility)
            if isinstance(ranking_weights, str):
                try:
                    weights = json.loads(ranking_weights)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        f"Failed to parse ranking_weights JSON for campaign {campaign.get('campaign_id')}, using defaults"
                    )
                    return self._scoring_weights
            elif isinstance(ranking_weights, dict):
                weights = ranking_weights
            else:
                # Invalid type, use defaults
                logger.warning(
                    f"Invalid ranking_weights type {type(ranking_weights).__name__} for campaign {campaign.get('campaign_id')}, using defaults"
                )
                return self._scoring_weights

            # Validate that weights dict is not empty
            if weights:
                logger.debug(f"Using custom weights for campaign {campaign.get('campaign_id')}")
                return weights

        # Otherwise, use config/default weights
        return self._scoring_weights

    def _load_scoring_weights(self, config_path: str | None = None) -> dict[str, float]:
        """
        Load scoring weights from configuration file.

        Weights are percentages and should sum to 100%. These are used as fallback
        when a campaign doesn't have custom weights set in the UI.

        Args:
            config_path: Optional path to config file. If not provided, looks in
                        standard locations.

        Returns:
            Dictionary mapping factor names to weights (as percentages)
        """
        # Default weights
        default_weights = {
            "location_match": 15.0,
            "salary_match": 15.0,
            "company_size_match": 10.0,
            "skills_match": 15.0,
            "keyword_match": 15.0,
            "employment_type_match": 5.0,
            "seniority_match": 10.0,
            "remote_type_match": 10.0,
            "recency": 5.0,
        }

        # Try to find config file
        possible_paths = [
            config_path,
            Path(__file__).parent / "ranking_config.json",
            Path("/opt/airflow/services/ranker/ranking_config.json"),
            Path("services/ranker/ranking_config.json"),
        ]

        for path in possible_paths:
            if not path:
                continue

            path_obj = Path(path) if isinstance(path, str) else path
            if path_obj.exists():
                try:
                    with open(path_obj, encoding="utf-8") as f:
                        data = json.load(f)
                        weights = data.get("scoring_weights", {})
                        if weights:
                            logger.info(f"Loaded scoring weights from {path_obj}")
                            # Validate weights sum to ~100
                            total = sum(weights.values())
                            if abs(total - 100.0) > 0.1:
                                logger.warning(
                                    f"Scoring weights sum to {total}, expected ~100.0. Using loaded weights anyway."
                                )
                            return weights
                except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to load scoring weights from {path_obj}: {e}")

        # Use defaults if config not found
        logger.info("Using default scoring weights")
        return default_weights

    def _score_location_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score location match between job and campaign (0-1 scale).

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Location match score (0.0-1.0)
        """
        job_location = (job.get("job_location") or "").lower()
        campaign_location = (campaign.get("location") or "").lower()
        campaign_country = (campaign.get("country") or "").lower()

        if not job_location:
            return 0.0

        # Exact location match
        if campaign_location and campaign_location in job_location:
            return 1.0

        # Country match
        if campaign_country:
            # Common country name mappings
            country_mappings = {
                "ca": ["canada", "canadian"],
                "us": ["united states", "usa", "u.s.", "america"],
                "uk": ["united kingdom", "england", "britain"],
            }

            country_terms = country_mappings.get(campaign_country, [campaign_country])
            for term in country_terms:
                if term in job_location:
                    return 0.7  # Partial match for country

        return 0.0

    def _score_keyword_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score keyword match between campaign query and job title (0-1 scale).

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Keyword match score (0.0-1.0)
        """
        job_title = (job.get("job_title") or "").lower()
        campaign_query = (campaign.get("query") or "").lower()

        if not campaign_query or not job_title:
            return 0.0

        # Extract keywords from campaign query
        query_keywords = set(re.findall(r"\b\w+\b", campaign_query))

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

    def _score_salary_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score salary match between job and campaign (0-1 scale).

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Salary match score (0.0-1.0)
        """
        campaign_min = campaign.get("min_salary")
        campaign_max = campaign.get("max_salary")
        campaign_currency = campaign.get("currency") or "USD"

        job_min = job.get("job_min_salary")
        job_max = job.get("job_max_salary")
        job_currency = job.get("job_salary_currency")
        job_period = job.get("job_salary_period")

        # If no salary data, return neutral score
        if not campaign_min and not campaign_max:
            return 0.5  # Neutral if campaign has no salary preference

        if not job_min and not job_max:
            return 0.3  # Lower score if job has no salary info

        # Normalize job salary to annual
        # Note: Salaries are now stored as yearly integers in the database,
        # but we still normalize as a safety check in case period is different
        if job_min:
            # If period is 'year' or None, assume already yearly (from database conversion)
            if not job_period or job_period.lower() in ("year", "annual", "annually", "yr", "y"):
                job_min_annual = float(job_min)
            else:
                # Fallback normalization for edge cases
                job_min_annual = self._normalize_salary_to_annual(float(job_min), job_period)
        else:
            job_min_annual = None

        if job_max:
            # If period is 'year' or None, assume already yearly (from database conversion)
            if not job_period or job_period.lower() in ("year", "annual", "annually", "yr", "y"):
                job_max_annual = float(job_max)
            else:
                # Fallback normalization for edge cases
                job_max_annual = self._normalize_salary_to_annual(float(job_max), job_period)
        else:
            job_max_annual = None

        # Convert job salary to campaign currency
        if job_min_annual and job_currency and self._validate_currency(job_currency):
            job_min_annual = self._convert_currency(job_min_annual, job_currency, campaign_currency)

        if job_max_annual and job_currency and self._validate_currency(job_currency):
            job_max_annual = self._convert_currency(job_max_annual, job_currency, campaign_currency)

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

        # Campaign salaries are now stored as yearly integers
        campaign_avg = None
        if campaign_min and campaign_max:
            campaign_avg = (float(campaign_min) + float(campaign_max)) / 2
        elif campaign_min:
            campaign_avg = float(campaign_min)
        elif campaign_max:
            campaign_avg = float(campaign_max)

        if not campaign_avg:
            return 0.5

        # Score based on how close job salary is to campaign preference
        ratio = job_avg / campaign_avg if campaign_avg > 0 else 0

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

    def _score_company_size_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score company size match (0-1 scale).

        Supports multiple company size preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Company size match score (0.0-1.0)
        """
        campaign_preference_str = campaign.get("company_size_preference") or ""
        company_size = job.get("company_size")

        if not campaign_preference_str:
            return 0.5  # Neutral if campaign has no preference

        if not company_size:
            return 0.3  # Lower score if job has no company size info

        # Parse comma-separated preferences
        campaign_preferences = [p.strip() for p in campaign_preference_str.split(",") if p.strip()]

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

        for campaign_preference in campaign_preferences:
            if job_size_num is None:
                # Try exact match on string
                if campaign_preference.lower() in company_size_str.lower():
                    best_score = max(best_score, 1.0)
                continue

            # Check if job size falls within campaign preference range
            if campaign_preference in size_ranges:
                min_size, max_size = size_ranges[campaign_preference]
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
                        best_score = max(best_score, 0.8)  # Campaign wants large, job is large
                    else:
                        ratio = max_size / job_size_num if job_size_num > 0 else 0
                        if ratio >= 0.7:
                            best_score = max(best_score, 0.6)  # Close to upper bound
                        else:
                            best_score = max(best_score, 0.3)  # Much larger

            # Exact string match as fallback
            if campaign_preference.lower() in company_size_str.lower():
                best_score = max(best_score, 1.0)

        return best_score if best_score > 0 else 0.3

    def _score_skills_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score skills match between job and campaign (0-1 scale).

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Skills match score (0.0-1.0)
        """
        campaign_skills_str = campaign.get("skills") or ""
        job_skills = job.get("extracted_skills")

        if not campaign_skills_str:
            return 0.5  # Neutral if campaign has no skills preference

        if not job_skills:
            return 0.3  # Lower score if job has no skills info

        # Parse campaign skills (semicolon or comma separated)
        campaign_skills = set()
        for skill in re.split(r"[;,]", campaign_skills_str):
            skill = skill.strip().lower()
            if skill:
                campaign_skills.add(skill)

        if not campaign_skills:
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
        matching_skills = campaign_skills.intersection(job_skills_set)
        match_ratio = len(matching_skills) / len(campaign_skills) if campaign_skills else 0

        # Score based on percentage of campaign skills found in job
        if match_ratio >= 1.0:
            return 1.0  # All campaign skills found
        elif match_ratio >= 0.7:
            return 0.8  # Most skills found
        elif match_ratio >= 0.5:
            return 0.6  # Half skills found
        elif match_ratio >= 0.3:
            return 0.4  # Some skills found
        else:
            return 0.2  # Few skills found

    def _score_employment_type_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score employment type match (0-1 scale).

        Supports multiple employment type preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Employment type match score (0.0-1.0)
        """
        campaign_preference_str = (campaign.get("employment_type_preference") or "").upper()
        job_employment_type = (job.get("job_employment_type") or "").upper()
        job_employment_types = job.get("job_employment_types")  # JSONB array
        employment_types = job.get("employment_types")  # Comma-separated string

        if not campaign_preference_str:
            return 0.5  # Neutral if campaign has no preference

        if not job_employment_type and not job_employment_types and not employment_types:
            return 0.3  # Lower score if job has no employment type info

        # Parse comma-separated preferences
        campaign_preferences = [p.strip() for p in campaign_preference_str.split(",") if p.strip()]

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
        for campaign_preference in campaign_preferences:
            if campaign_preference in job_types_set:
                return 1.0  # Exact match

        # Partial match check (e.g., "Full-time" contains "FULLTIME")
        job_types_combined = " ".join(job_types_set).upper()
        for campaign_preference in campaign_preferences:
            if campaign_preference in job_types_combined:
                return 0.8  # Partial match

        return 0.2  # No match

    def _score_seniority_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score seniority level match between job and campaign (0-1 scale).

        Supports multiple seniority preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Seniority match score (0.0-1.0)
        """
        campaign_seniority_str = (campaign.get("seniority") or "").lower()
        job_seniority = (job.get("seniority_level") or "").lower()

        if not campaign_seniority_str:
            return 0.5  # Neutral if campaign has no seniority preference

        if not job_seniority:
            return 0.3  # Lower score if job has no seniority info

        # Parse comma-separated preferences
        campaign_seniorities = [s.strip() for s in campaign_seniority_str.split(",") if s.strip()]

        # Check for exact match with any preference
        if job_seniority in campaign_seniorities:
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
        for campaign_seniority in campaign_seniorities:
            campaign_level = seniority_levels.get(campaign_seniority, 0)
            if campaign_level == 0:
                continue

            # Score based on level difference
            level_diff = abs(campaign_level - job_level)
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

    def _score_remote_type_match(self, job: dict[str, Any], campaign: dict[str, Any]) -> float:
        """
        Score remote work type match between job and campaign (0-1 scale).

        Supports multiple remote preferences (comma-separated).
        Returns highest score if job matches any of the selected preferences.

        Args:
            job: Job dictionary
            campaign: Campaign dictionary

        Returns:
            Remote type match score (0.0-1.0)
        """
        campaign_remote_str = (campaign.get("remote_preference") or "").lower()
        job_remote_type = (job.get("remote_work_type") or "").lower()
        job_is_remote = job.get("job_is_remote", False)

        if not campaign_remote_str:
            return 0.5  # Neutral if campaign has no remote preference

        # If job has remote_work_type, use that; otherwise use job_is_remote
        if not job_remote_type:
            if job_is_remote:
                job_remote_type = "remote"
            else:
                job_remote_type = "onsite"

        # Parse comma-separated preferences
        campaign_remotes = [r.strip() for r in campaign_remote_str.split(",") if r.strip()]

        # Check for exact match with any preference
        if job_remote_type in campaign_remotes:
            return 1.0

        # Find best match among preferences
        best_score = 0.0
        for campaign_remote in campaign_remotes:
            # Partial matches
            if campaign_remote == "hybrid":
                # Hybrid matches both remote and onsite
                if job_remote_type in ("remote", "onsite"):
                    best_score = max(best_score, 0.7)
            elif campaign_remote == "remote":
                # Remote preference matches hybrid but not onsite
                if job_remote_type == "hybrid":
                    best_score = max(best_score, 0.7)
                elif job_remote_type == "onsite":
                    best_score = max(best_score, 0.2)
            elif campaign_remote == "onsite":
                # Onsite preference matches hybrid but not remote
                if job_remote_type == "hybrid":
                    best_score = max(best_score, 0.7)
                elif job_remote_type == "remote":
                    best_score = max(best_score, 0.2)

        return best_score if best_score > 0 else 0.3

    def rank_jobs_for_campaign(self, campaign: dict[str, Any]) -> int:
        """
        Process and save rankings for all jobs belonging to a campaign (workflow method).

        This method orchestrates the full ranking workflow:
        1. Retrieves all jobs extracted for this campaign
        2. Calculates match scores for each job using calculate_job_score()
        3. Writes all rankings to marts.dim_ranking_staging table (accessed via marts.dim_ranking view)

        This is the main entry point for ranking jobs - it handles the complete process
        from fetching jobs to persisting rankings in the database.

        Args:
            campaign: Campaign dictionary from job_campaigns

        Returns:
            Number of jobs ranked and saved to database
        """
        campaign_id = campaign["campaign_id"]
        campaign_name = campaign["campaign_name"]

        logger.info(
            f"Ranking jobs for campaign {campaign_id} ({campaign_name})",
            extra={"campaign_id": campaign_id, "campaign_name": campaign_name},
        )

        # Get jobs for this campaign
        jobs = self.get_jobs_for_campaign(campaign_id)

        if not jobs:
            logger.info(
                f"No jobs found for campaign {campaign_id}",
                extra={"campaign_id": campaign_id},
            )
            return 0

        # Calculate scores for each job
        rankings = []
        now = datetime.now()
        today = date.today()

        for job in jobs:
            score, explanation = self.calculate_job_score(job, campaign)
            rankings.append(
                {
                    "jsearch_job_id": job["jsearch_job_id"],
                    "campaign_id": campaign_id,
                    "rank_score": round(score, 2),
                    "rank_explain": json.dumps(explanation),
                    "ranked_at": now,
                    "ranked_date": today,
                    "dwh_load_timestamp": now,
                    "dwh_source_system": "ranker",
                }
            )

        # Write to database
        self._write_rankings(rankings)

        avg_score = sum(r["rank_score"] for r in rankings) / len(rankings) if rankings else 0.0
        logger.info(
            f"Ranked {len(rankings)} jobs for campaign {campaign_id} (avg score: {avg_score:.2f})",
            extra={
                "campaign_id": campaign_id,
                "jobs_ranked": len(rankings),
                "avg_score": round(avg_score, 2),
            },
        )

        return len(rankings)

    def _write_rankings(self, rankings: list[dict[str, Any]]):
        """
        Write rankings to marts.dim_ranking_staging table (accessed via marts.dim_ranking view).
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
                        ranking["campaign_id"],
                        ranking["rank_score"],
                        ranking["rank_explain"],
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
        Rank jobs for all active campaigns.

        Returns:
            Dictionary mapping campaign_id to number of jobs ranked
        """
        campaigns = self.get_active_campaigns()

        if not campaigns:
            logger.warning("No active campaigns found for ranking")
            return {}

        results = {}
        for campaign in campaigns:
            try:
                count = self.rank_jobs_for_campaign(campaign)
                results[campaign["campaign_id"]] = count
            except Exception as e:
                logger.error(
                    f"Failed to rank jobs for campaign {campaign['campaign_id']}: {e}",
                    exc_info=True,
                )
                results[campaign["campaign_id"]] = 0

        total_ranked = sum(results.values())
        logger.info(f"Ranking complete. Total jobs ranked: {total_ranked}")

        return results
