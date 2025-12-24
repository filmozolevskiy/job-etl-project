"""Job Enricher Service.

Enriches job postings with extracted skills and seniority levels using NLP.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

try:
    import spacy
except ImportError:
    spacy = None  # type: ignore[assignment]

from shared import Database

from .queries import GET_ALL_JOBS_TO_ENRICH, GET_JOBS_TO_ENRICH, UPDATE_JOB_ENRICHMENT
from .remote_patterns import REMOTE_PATTERNS
from .seniority_patterns import SENIORITY_PATTERNS
from .technical_skills import TECHNICAL_SKILLS

logger = logging.getLogger(__name__)


class JobEnricher:
    """
    Service for enriching job postings with extracted skills, seniority, remote type,
    and salary information.

    Reads jobs from staging.jsearch_job_postings, extracts skills using spaCy NLP,
    extracts seniority from job titles, classifies remote work type, infers salary
    ranges/periods from text when missing, and updates the staging table.
    """

    def __init__(self, database: Database, batch_size: int = 100):
        """
        Initialize the job enricher.

        Args:
            database: Database connection interface (implements Database protocol)
            batch_size: Number of jobs to process in each batch

        Raises:
            ValueError: If database is None or batch_size is invalid
        """
        if not database:
            raise ValueError("Database is required")
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(f"batch_size must be a positive integer, got: {batch_size}")

        self.db = database
        self.batch_size = batch_size
        self.nlp = None
        self._load_nlp_model()

    def _load_nlp_model(self) -> None:
        """
        Load spaCy NLP model for skills extraction.

        Tries to load 'en_core_web_sm' model. If not available, falls back to
        a basic model or creates a simple tokenizer.
        """
        if spacy is None:
            logger.warning("spaCy is not installed. Install with: pip install spacy>=3.6.0,<3.7.0")
            logger.warning("Skills extraction will use basic pattern matching only.")
            self.nlp = None
            return

        try:
            # Try to load the small English model
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy model: en_core_web_sm")
        except OSError:
            # If model not found, try to load a basic model
            try:
                self.nlp = spacy.load("en_core_web_lg")
                logger.info("Loaded spaCy model: en_core_web_lg")
            except OSError:
                # Fallback: create a basic model (tokenizer only)
                logger.warning(
                    "spaCy model not found. Install with: python -m spacy download en_core_web_sm"
                )
                logger.warning("Falling back to basic tokenizer. Skills extraction may be limited.")
                try:
                    self.nlp = spacy.blank("en")
                except Exception as e:
                    logger.error(f"Failed to create basic spaCy model: {e}")
                    self.nlp = None

    def get_jobs_to_enrich(self, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Get jobs that need enrichment from staging.jsearch_job_postings.

        Args:
            limit: Optional limit on number of jobs to return. If None, uses batch_size.

        Returns:
            List of job dictionaries with jsearch_job_postings_key, jsearch_job_id,
            job_title, and job_description
        """
        query_limit = limit if limit is not None else self.batch_size
        query = GET_JOBS_TO_ENRICH if limit is not None else GET_ALL_JOBS_TO_ENRICH

        with self.db.get_cursor() as cur:
            if limit is not None:
                cur.execute(query, (query_limit,))
            else:
                cur.execute(query)

            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

            logger.info(f"Found {len(jobs)} job(s) needing enrichment")
            return jobs

    def extract_skills(self, job_description: str, job_title: str = "") -> list[str]:
        """
        Extract technical skills from job description and title.

        Uses two complementary methods:
        1. Regex pattern matching: Iterates through TECHNICAL_SKILLS categories
           and uses word-boundary regex to find exact matches in the text.
           This is the primary method and matches the approach used in
           extract_seniority() for consistency.

        2. spaCy NLP: Uses named entity recognition and noun phrase extraction
           to identify potential technologies, then validates against the
           skills dictionary. This helps catch variations and context-based
           mentions that regex might miss.

        Performance characteristics:
        - Method 1: O(n*m) where n = number of skills, m = text length
        - Method 2: O(k) for NLP processing + O(k*p) for validation where
          k = number of chunks/entities, p = skills to check
        - Overall: Efficient for typical job descriptions (< 10KB text)

        Args:
            job_description: Full job description text
            job_title: Optional job title for additional context

        Returns:
            List of extracted skills (normalized, lowercase, unique, sorted)
        """
        if not job_description:
            return []

        # Combine title and description for analysis
        text = f"{job_title} {job_description}".lower()

        extracted_skills = set()

        # Method 1: Check against predefined skills dictionary
        # Iterate through categories and patterns (similar to seniority extraction)
        for _, skills_list in TECHNICAL_SKILLS.items():
            for skill in skills_list:
                # Use word boundaries to avoid partial matches
                pattern = r"\b" + re.escape(skill.lower()) + r"\b"
                if re.search(pattern, text, re.IGNORECASE):
                    extracted_skills.add(skill.lower())

        # Method 2: Use spaCy for named entity recognition and noun phrases
        # Build flattened sets for efficient membership checks
        all_skills_set = set()
        long_skills_set = set()  # Skills > 3 chars for substring matching
        for skills_list in TECHNICAL_SKILLS.values():
            all_skills_set.update(skills_list)
            # Pre-build set of longer skills for efficient substring checking
            long_skills_set.update(s for s in skills_list if len(s) > 3)

        if self.nlp:
            try:
                doc = self.nlp(text)
                # Extract noun phrases that might be technologies
                for chunk in doc.noun_chunks:
                    chunk_text = chunk.text.lower().strip()
                    # Check if it matches any known skill (exact match)
                    if chunk_text in all_skills_set:
                        extracted_skills.add(chunk_text)
                    # Check for multi-word skills (e.g., "machine learning")
                    # Use pre-built set for O(1) lookup instead of nested loop
                    for skill in long_skills_set:
                        if skill in chunk_text:
                            extracted_skills.add(skill)

                # Extract named entities that might be technologies
                for ent in doc.ents:
                    ent_text = ent.text.lower().strip()
                    if ent_text in all_skills_set:
                        extracted_skills.add(ent_text)
            except Exception as e:
                logger.warning(f"Error in spaCy processing: {e}")

        # Sort and return as list
        return sorted(extracted_skills)

    def extract_seniority(self, job_title: str, job_description: str = "") -> str | None:
        """
        Extract seniority level from job title and description.

        Uses pattern matching to identify seniority indicators in job titles
        and descriptions.

        Args:
            job_title: Job title text
            job_description: Optional job description for additional context

        Returns:
            Seniority level string: "intern", "junior", "mid", "senior", or "executive"
            Returns None if no clear seniority level is detected
        """
        if not job_title:
            return None

        # Combine title and description for analysis
        text = f"{job_title} {job_description}".lower()

        # Check patterns in order of specificity (most specific first)
        # Check for executive level first (most specific)
        for level, patterns in SENIORITY_PATTERNS.items():
            for pattern in patterns:
                # Use word boundaries to avoid partial matches
                regex_pattern = r"\b" + re.escape(pattern) + r"\b"
                if re.search(regex_pattern, text, re.IGNORECASE):
                    return level

        # If no pattern matches, return None
        return None

    def extract_remote_type(self, job_title: str, job_description: str = "") -> str | None:
        """
        Extract remote work type from job title and description.

        Uses pattern matching to identify remote work indicators in job titles
        and descriptions.

        Args:
            job_title: Job title text
            job_description: Optional job description for additional context

        Returns:
            Remote work type string: "remote", "hybrid", or "onsite"
            Returns None if no clear remote work type is detected
        """
        if not job_title and not job_description:
            return None

        # Combine title and description for analysis
        text = f"{job_title} {job_description}".lower()

        # Check patterns in order of specificity (most specific first)
        # IMPORTANT: Order in REMOTE_PATTERNS matters - hybrid must be checked before remote
        # to catch cases like "hybrid working environment, allowing for both remote and on-site"
        for work_type, patterns in REMOTE_PATTERNS.items():
            for pattern in patterns:
                # Use word boundaries to avoid partial matches
                regex_pattern = r"\b" + re.escape(pattern.lower()) + r"\b"
                if re.search(regex_pattern, text, re.IGNORECASE):
                    return work_type

        # If no pattern matches, return None
        return None

    def extract_salary(
        self, job_title: str, job_description: str = "", job_country: str | None = None
    ) -> tuple[float | None, float | None, str | None, str | None]:
        """
        Extract salary range, period, and currency from job title/description.

        This uses simple pattern matching for common salary formats, for example:
        - "$120k-$150k", "120,000 - 150,000 USD", "80-100k CAD"
        - "$90,000 per year", "£500 per day", "€60/hour"

        Args:
            job_title: Job title text
            job_description: Job description text
            job_country: Country code (e.g., "US", "CA", "GB", "FR") for default currency detection

        Returns:
            Tuple of (min_salary, max_salary, salary_period, currency) where:
            - period is one of "year", "month", "week", "day", "hour", or None
            - currency is one of "USD", "CAD", "EUR", "GBP", or None if not detected
        """
        text = f"{job_title or ''} {job_description or ''}"
        text_lower = text.lower()
        if not text_lower.strip():
            return None, None, None, None

        # Require some explicit salary / compensation context to reduce false positives.
        context_markers = [
            "salary",
            "compensation",
            "pay",
            "rate",
            "per year",
            "per month",
            "per week",
            "per day",
            "per hour",
            "/year",
            "/month",
            "/week",
            "/day",
            "/hour",
            "$",
            "c$",  # Canadian dollar prefix
            "£",
            "€",
        ]
        if not any(marker in text_lower for marker in context_markers):
            return None, None, None, None

        # Financial exclusions will be checked after pattern matching
        # to only apply them in the context window around the matched salary

        def _detect_currency(
            context_text: str, currency_symbol: str | None = None, job_country: str | None = None
        ) -> str | None:
            """
            Detect currency code from context around salary, currency symbol, or job country.
            Returns: "USD", "CAD", "EUR", "GBP", or None
            """
            # Map currency symbols to currency codes
            symbol_to_currency = {
                "$": None,  # $ is ambiguous - need to check country or context
                "£": "GBP",
                "€": "EUR",
            }

            # Map country codes to default currencies
            country_to_currency = {
                # North America
                "US": "USD",
                "USA": "USD",
                "UNITED STATES": "USD",
                "CA": "CAD",
                "CAN": "CAD",
                "CANADA": "CAD",
                "MX": "USD",  # Mexico often uses USD in tech job postings, but could be MXN
                # Europe
                "GB": "GBP",
                "GBR": "GBP",
                "UK": "GBP",
                "UNITED KINGDOM": "GBP",
                # European Union countries - default to EUR
                "AT": "EUR",  # Austria
                "BE": "EUR",  # Belgium
                "BG": "EUR",  # Bulgaria
                "HR": "EUR",  # Croatia
                "CY": "EUR",  # Cyprus
                "CZ": "EUR",  # Czech Republic
                "DK": "EUR",  # Denmark (actually uses DKK, but EUR common in tech)
                "EE": "EUR",  # Estonia
                "FI": "EUR",  # Finland
                "FR": "EUR",  # France
                "DE": "EUR",  # Germany
                "GR": "EUR",  # Greece
                "HU": "EUR",  # Hungary
                "IE": "EUR",  # Ireland
                "IT": "EUR",  # Italy
                "LV": "EUR",  # Latvia
                "LT": "EUR",  # Lithuania
                "LU": "EUR",  # Luxembourg
                "MT": "EUR",  # Malta
                "NL": "EUR",  # Netherlands
                "PL": "EUR",  # Poland
                "PT": "EUR",  # Portugal
                "RO": "EUR",  # Romania
                "SK": "EUR",  # Slovakia
                "SI": "EUR",  # Slovenia
                "ES": "EUR",  # Spain
                "SE": "EUR",  # Sweden (actually uses SEK, but EUR common in tech)
                # Other common countries
                "AU": "USD",  # Australia (AUD, but USD common in remote tech jobs)
                "NZ": "USD",  # New Zealand (NZD, but USD common in remote tech jobs)
                "IN": "USD",  # India (INR, but USD common in tech jobs)
            }

            # Look for explicit currency codes in the context (case-insensitive)
            # Check for "USD", "CAD", "EUR", "GBP" near the salary mention
            currency_patterns = {
                r"\b(?:usd|us\s+dollars?)\b": "USD",
                r"\b(?:cad|canadian\s+dollars?)\b": "CAD",
                r"\b(?:eur|euros?|euro)\b": "EUR",
                r"\b(?:gbp|pounds?|british\s+pounds?)\b": "GBP",
            }

            for pattern, code in currency_patterns.items():
                if re.search(pattern, context_text, re.IGNORECASE):
                    return code

            # If we have a currency symbol, use it as default but check for context hints
            if currency_symbol:
                # For $ symbol, check context and country
                if currency_symbol == "$":
                    # If text mentions "CAD" or "Canadian" elsewhere, likely CAD
                    if re.search(r"\bcad\b|\bcanadian\b", context_text, re.IGNORECASE):
                        return "CAD"
                    # Default $ based on country
                    if job_country:
                        country_upper = job_country.upper().strip()
                        return country_to_currency.get(country_upper, "USD")
                    # Default to USD if no country info
                    return "USD"
                else:
                    # For £ and €, use symbol-based default
                    return symbol_to_currency.get(currency_symbol)

            # If no symbol but we have country, use country-based default
            if job_country:
                country_upper = job_country.upper().strip()
                return country_to_currency.get(country_upper)

            # No currency detected
            return None

        def _parse_number(num_str: str, has_k: bool) -> float:
            value = float(num_str.replace(",", ""))
            if has_k:
                value *= 1000.0
            return value

        # First, try to find a range like "80k-100k" or "$52.06 to $92.45 per hour".
        # We later enforce that at least one side has a currency symbol or 'k'
        # to avoid capturing generic ranges like "3-5" years.
        # Note: \d[\d,]*(?:\.\d+)? matches integers or decimals (e.g., "52.06", "80,000")
        # The pattern allows for optional periods like "/hr" or "/hour" after numbers
        # Also handles "C$" prefix for Canadian dollars
        # Handles double dash "--" as separator
        range_pattern = re.compile(
            r"(?P<cur_prefix>[Cc]\$)?\s*(?P<cur>[$£€])?\s*"
            r"(?P<min>\d[\d,]*(?:\.\d+)?)\s*(?P<mink>[kK])?(?:/hr|/hour)?\s*"
            r"(?:-{1,2}|–|—|to)\s*"  # Matches: regular dash, en dash (–), em dash (—), or "to"
            r"(?P<cur_prefix2>[Cc]\$)?\s*(?P<cur2>[$£€])?\s*"
            r"(?P<max>\d[\d,]*(?:\.\d+)?)\s*(?P<maxk>[kK])?(?:/hr|/hour)?",
            re.IGNORECASE,
        )
        # Search through all matches to find one that is likely a salary range:
        #  - has an explicit currency symbol (e.g., $)
        #  - OR uses a "k" suffix
        #  - OR has an explicit currency code text (USD, CAD, EUR, GBP) in the local context
        # This avoids false positives like "5-8 years" while still capturing ranges like
        # "Salary USD 155,500 - 315,000" that don't repeat the currency symbol.
        m = None
        for match in range_pattern.finditer(text):
            has_currency = bool(
                match.group("cur")
                or match.group("cur2")
                or match.group("cur_prefix")
                or match.group("cur_prefix2")
            )
            has_k = bool(match.group("mink") or match.group("maxk"))
            # Look at a small window around this match to detect currency codes like "USD" / "CAD"
            local_start = max(0, match.start() - 80)
            local_end = min(len(text), match.end() + 80)
            local_context_lower = text[local_start:local_end].lower()
            has_text_currency = bool(
                re.search(
                    r"\b(?:usd|us\s+dollars?|cad|canadian\s+dollars?|eur|euro?s?|gbp|pounds?)\b",
                    local_context_lower,
                    re.IGNORECASE,
                )
            )

            # If this match has currency, 'k', or an explicit text currency code, it's likely a salary range
            if has_currency or has_k or has_text_currency:
                m = match
                break

        if m:
            min_val = _parse_number(m.group("min"), bool(m.group("mink")))
            max_val = _parse_number(m.group("max"), bool(m.group("maxk")))

            # Detect currency and salary period from context around the matched salary range
            # Look in a window around the match to avoid false positives from unrelated text
            match_start = max(
                0, m.start() - 200
            )  # 200 chars before (increased to catch bonus mentions)
            match_end = min(len(text), m.end() + 200)  # 200 chars after
            salary_context = text[match_start:match_end]
            salary_context_lower = salary_context.lower()

            # Exclude financial/market contexts that often mention large dollar amounts
            # but aren't about salary (e.g., "$15T in capital", "assets under management")
            # Only check in the context window around the matched salary to avoid false positives
            financial_context_exclusions = [
                "in capital",
                "capital and",
                "assets under",
                "under management",
                "funds manage",
                "market cap",
                # Don't exclude general mentions of revenue/turnover - only exclude if near salary amount
                # "revenue", "turnover", "gross profit", "net profit", "ebitda", "valuation",
            ]
            if any(exclusion in salary_context_lower for exclusion in financial_context_exclusions):
                return None, None, None, None

            # Exclude bonus-related amounts (sign-on bonus, retention bonus, etc.)
            # Only exclude if bonus phrase appears directly before the salary amount
            # (e.g., "sign-on bonus up to $30,000") to avoid false positives
            # when bonus is mentioned separately from salary range
            bonus_exclusions = [
                "sign-on bonus",
                "sign on bonus",
                "signing bonus",
                "retention bonus",
                "bonus up to",
                "bonus of",
                "bonus:",
                "bonus;",
            ]
            # Check if any bonus exclusion appears within 50 characters before the matched salary
            match_start_in_context = m.start() - match_start  # Position of match in context window
            context_before_match = salary_context_lower[
                max(0, match_start_in_context - 50) : match_start_in_context
            ]
            if any(exclusion in context_before_match for exclusion in bonus_exclusions):
                return None, None, None, None

            # Detect currency from symbol, context, and country
            # Check for "C$" prefix first (Canadian dollar indicator)
            currency_symbol = None
            if m.group("cur_prefix") or m.group("cur_prefix2"):
                currency_symbol = "$"  # Treat C$ as $ for symbol matching
                # Force CAD currency when C$ is present
                currency = "CAD"
            else:
                currency_symbol = m.group("cur") or m.group("cur2")
                currency = _detect_currency(salary_context, currency_symbol, job_country)

            period: str | None = None
            # Check for period indicators in the context around the salary
            if any(
                p in salary_context_lower for p in ["per hour", "/hour", "/hr", "hourly", "an hour"]
            ):
                period = "hour"
            elif any(p in salary_context_lower for p in ["per day", "/day", "daily"]):
                period = "day"
            elif any(p in salary_context_lower for p in ["per week", "/week", "weekly"]):
                # For large amounts (>= $50k), "per week" is likely incorrect
                # Default to "year" for large ranges unless explicitly stated
                if min_val >= 50000:
                    period = "year"
                else:
                    period = "week"
            elif any(p in salary_context_lower for p in ["per month", "/month", "monthly"]):
                # For large amounts (>= $100k), "per month" is likely incorrect
                if min_val >= 100000:
                    period = "year"
                else:
                    period = "month"
            elif any(
                p in salary_context_lower
                for p in [
                    "per year",
                    "/year",
                    "per annum",
                    "annual",
                    "annually",
                    "a year",
                    "yr",
                    "/annum",
                ]
            ):
                period = "year"
            else:
                # Default to "year" for large salary ranges (common for full-time positions)
                if min_val >= 30000:
                    period = "year"
                # For smaller amounts without explicit period, leave as None

            return min_val, max_val, period, currency

        # Fallback: single value like "120k", "$90.50 per hour", "C$170,000"
        # Note: \d[\d,]*(?:\.\d+)? matches integers or decimals
        # Exclude "T", "M", "B" suffixes (trillion, million, billion) which indicate
        # financial/market data, not salary. Use negative lookahead to avoid matching
        # patterns like "$15T" or "$500M". We check for T/M/B immediately after the number
        # (with optional whitespace) to exclude these cases.
        # Also handles "C$" prefix for Canadian dollars
        single_pattern = re.compile(
            r"(?P<cur_prefix>[Cc]\$)?\s*(?P<cur>[$£€])?\s*(?P<val>\d[\d,]*(?:\.\d+)?)\s*(?P<k>[kK])?(?![mMbBtT])"
        )
        m_single = single_pattern.search(text)
        if m_single and (
            m_single.group("cur") or m_single.group("k") or m_single.group("cur_prefix")
        ):
            # Double-check: if match ends right before T/M/B, exclude it
            match_end_pos = m_single.end()
            if match_end_pos < len(text):
                next_char = text[match_end_pos]
                if next_char.upper() in ["T", "M", "B"]:
                    return None, None, None, None

            # Only extract if there's currency or 'k' to avoid false positives
            val = _parse_number(m_single.group("val"), bool(m_single.group("k")))

            # Detect currency and salary period from context around the matched salary
            match_start = max(
                0, m_single.start() - 200
            )  # 200 chars before (increased to catch bonus mentions)
            match_end = min(len(text), m_single.end() + 200)  # 200 chars after
            salary_context = text[match_start:match_end]
            salary_context_lower = salary_context.lower()

            # Exclude financial/market contexts that often mention large dollar amounts
            # but aren't about salary (e.g., "$15T in capital", "assets under management")
            financial_context_exclusions = [
                "in capital",
                "capital and",
                "assets under",
                "under management",
                "funds manage",
                "market cap",
            ]
            if any(exclusion in salary_context_lower for exclusion in financial_context_exclusions):
                return None, None, None, None

            # Exclude bonus-related amounts (sign-on bonus, retention bonus, etc.)
            bonus_exclusions = [
                "sign-on bonus",
                "sign on bonus",
                "signing bonus",
                "retention bonus",
                "performance bonus",
                "annual bonus",
                "bonus up to",
                "bonus of",
                "bonus:",
                "bonus;",
            ]
            if any(exclusion in salary_context_lower for exclusion in bonus_exclusions):
                return None, None, None, None

            # Detect currency from symbol, context, and country
            # Check for "C$" prefix first (Canadian dollar indicator)
            if m_single.group("cur_prefix"):
                currency_symbol = "$"  # Treat C$ as $ for symbol matching
                currency = "CAD"  # Force CAD currency when C$ is present
            else:
                currency_symbol = m_single.group("cur")
                currency = _detect_currency(salary_context, currency_symbol, job_country)

            period: str | None = None
            if any(
                p in salary_context_lower for p in ["per hour", "/hour", "/hr", "hourly", "an hour"]
            ):
                period = "hour"
            elif any(p in salary_context_lower for p in ["per day", "/day", "daily"]):
                period = "day"
            elif any(p in salary_context_lower for p in ["per week", "/week", "weekly"]):
                if val >= 50000:
                    period = "year"  # Large amounts are likely yearly
                else:
                    period = "week"
            elif any(p in salary_context_lower for p in ["per month", "/month", "monthly"]):
                if val >= 100000:
                    period = "year"  # Very large amounts are likely yearly
                else:
                    period = "month"
            elif any(
                p in salary_context_lower
                for p in [
                    "per year",
                    "/year",
                    "per annum",
                    "annual",
                    "annually",
                    "a year",
                    "yr",
                    "/annum",
                ]
            ):
                period = "year"
            else:
                # Default to "year" for large amounts
                if val >= 30000:
                    period = "year"

            return val, val, period, currency

        return None, None, None, None

    def enrich_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a single job with extracted skills, seniority, and remote work type.

        Args:
            job: Job dictionary with jsearch_job_postings_key, job_title, job_description

        Returns:
            Dictionary with extracted_skills (list), seniority_level (str or None),
            and remote_work_type (str or None)
        """
        job_title = job.get("job_title", "") or ""
        job_description = job.get("job_description", "") or ""

        extracted_skills = self.extract_skills(job_description, job_title)
        seniority_level = self.extract_seniority(job_title, job_description)
        remote_work_type = self.extract_remote_type(job_title, job_description)
        job_country = job.get("job_country")
        min_salary, max_salary, salary_period, salary_currency = self.extract_salary(
            job_title, job_description, job_country
        )

        return {
            "extracted_skills": extracted_skills,
            "seniority_level": seniority_level,
            "remote_work_type": remote_work_type,
            "job_min_salary": min_salary,
            "job_max_salary": max_salary,
            "job_salary_period": salary_period,
            "job_salary_currency": salary_currency,
        }

    def update_job_enrichment(
        self,
        job_key: int,
        extracted_skills: list[str] | None,
        seniority_level: str | None,
        remote_work_type: str | None,
        job_min_salary: float | None,
        job_max_salary: float | None,
        job_salary_period: str | None,
        job_salary_currency: str | None,
        enrichment_status_updates: str,
    ) -> None:
        """
        Update a job in staging.jsearch_job_postings with enrichment data.

        Args:
            job_key: jsearch_job_postings_key (primary key)
            extracted_skills: List of extracted skills or None (None if not processed)
            seniority_level: Seniority level string or None (None if not processed)
            remote_work_type: Remote work type string or None (None if not processed)
            job_min_salary: Minimum salary value or None
            job_max_salary: Maximum salary value or None
            job_salary_period: Salary period (year/month/week/day/hour) or None
            job_salary_currency: Currency code (USD/CAD/EUR/GBP) or None
            enrichment_status_updates: JSONB string with flags to set to true
                Example: '{"skills_enriched": true, "seniority_enriched": true}'

        Note: enrichment_status_updates should only contain flags for fields that were
        actually processed. This prevents infinite loops by marking fields as processed.
        """
        # Convert skills list to JSON string for storage.
        # If extracted_skills is None (not processed), pass None to preserve existing via COALESCE.
        # If extracted_skills is a list (processed, even if empty), convert to JSON string.
        if extracted_skills is not None:
            skills_json = json.dumps(extracted_skills)
        else:
            skills_json = None

        with self.db.get_cursor() as cur:
            cur.execute(
                UPDATE_JOB_ENRICHMENT,
                (
                    skills_json,
                    seniority_level,
                    remote_work_type,
                    job_min_salary,
                    job_max_salary,
                    job_salary_period,
                    job_salary_currency,
                    enrichment_status_updates,
                    job_key,
                ),
            )
            logger.debug(
                f"Updated enrichment for job_key={job_key}: "
                f"skills={'extracted' if extracted_skills is not None else 'preserved'}, "
                f"seniority={'extracted' if seniority_level is not None else 'preserved'}, "
                f"remote_type={'extracted' if remote_work_type is not None else 'preserved'}, "
                f"salary_min={job_min_salary}, salary_max={job_max_salary}, "
                f"salary_period={job_salary_period}, salary_currency={job_salary_currency}, "
                f"status_updates={enrichment_status_updates}"
            )

    def enrich_jobs(self, jobs: list[dict[str, Any]] | None = None) -> dict[str, int]:
        """
        Enrich a batch of jobs.

        Args:
            jobs: Optional list of jobs to enrich. If None, fetches jobs from database.

        Returns:
            Dictionary with statistics: {"processed": int, "enriched": int, "errors": int}
        """
        if jobs is None:
            jobs = self.get_jobs_to_enrich()

        stats = {"processed": 0, "enriched": 0, "errors": 0}

        for job in jobs:
            try:
                stats["processed"] += 1
                job_key = job["jsearch_job_postings_key"]

                # Get current enrichment status to determine what needs processing
                enrichment_status = job.get("enrichment_status")
                if enrichment_status is None:
                    enrichment_status = {}
                elif isinstance(enrichment_status, str):
                    enrichment_status = json.loads(enrichment_status)
                elif not isinstance(enrichment_status, dict):
                    # If it's not a dict, str, or None, default to empty dict
                    enrichment_status = {}

                skills_enriched = enrichment_status.get("skills_enriched", False)
                seniority_enriched = enrichment_status.get("seniority_enriched", False)
                remote_type_enriched = enrichment_status.get("remote_type_enriched", False)
                salary_enriched = enrichment_status.get("salary_enriched", False)

                # Only extract fields that haven't been processed yet
                extracted_skills = None
                seniority_level = None
                remote_work_type = None
                job_min_salary: float | None = None
                job_max_salary: float | None = None
                job_salary_period: str | None = None
                job_salary_currency: str | None = None
                status_updates = {}

                job_title = job.get("job_title", "") or ""
                job_description = job.get("job_description", "") or ""
                job_country = job.get("job_country")
                existing_min_salary = job.get("job_min_salary")
                existing_max_salary = job.get("job_max_salary")
                existing_salary_period = job.get("job_salary_period")
                existing_salary_currency = job.get("job_salary_currency")

                if not skills_enriched:
                    extracted_skills = self.extract_skills(job_description, job_title)
                    # Always mark as processed, even if extraction returns empty list
                    status_updates["skills_enriched"] = True

                if not seniority_enriched:
                    seniority_level = self.extract_seniority(job_title, job_description)
                    # Always mark as processed, even if extraction returns None
                    status_updates["seniority_enriched"] = True

                if not remote_type_enriched:
                    remote_work_type = self.extract_remote_type(job_title, job_description)
                    # Always mark as processed, even if extraction returns None
                    status_updates["remote_type_enriched"] = True

                if not salary_enriched:
                    # Only attempt to infer salary when all salary fields are currently NULL.
                    # However, we always mark salary_enriched=true so rows with existing salary
                    # don't get reprocessed on every run and cause an infinite loop.
                    if (
                        existing_min_salary is None
                        and existing_max_salary is None
                        and existing_salary_period is None
                        and existing_salary_currency is None
                    ):
                        min_salary, max_salary, salary_period, salary_currency = (
                            self.extract_salary(job_title, job_description, job_country)
                        )
                        job_min_salary = min_salary
                        job_max_salary = max_salary
                        job_salary_period = salary_period
                        job_salary_currency = salary_currency
                    status_updates["salary_enriched"] = True

                # Build enrichment_status_updates JSONB string
                enrichment_status_updates = json.dumps(status_updates) if status_updates else "{}"

                # Update database (only updates fields that were extracted)
                self.update_job_enrichment(
                    job_key,
                    extracted_skills,
                    seniority_level,
                    remote_work_type,
                    job_min_salary,
                    job_max_salary,
                    job_salary_period,
                    job_salary_currency,
                    enrichment_status_updates,
                )
                stats["enriched"] += 1

                logger.debug(
                    f"Enriched job {job_key}: "
                    f"skills={'extracted' if extracted_skills is not None else 'preserved'}, "
                    f"seniority={'extracted' if seniority_level is not None else 'preserved'}, "
                    f"remote_type={'extracted' if remote_work_type is not None else 'preserved'}, "
                    f"status_updates={status_updates}"
                )

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Error enriching job {job.get('jsearch_job_postings_key')}: {e}")

        logger.info(
            f"Enrichment batch complete: processed={stats['processed']}, "
            f"enriched={stats['enriched']}, errors={stats['errors']}"
        )

        return stats

    def enrich_all_pending_jobs(self) -> dict[str, int]:
        """
        Enrich all pending jobs in batches.

        Processes jobs in batches of batch_size until all jobs are enriched.

        Returns:
            Dictionary with total statistics: {"processed": int, "enriched": int, "errors": int}
        """
        total_stats = {"processed": 0, "enriched": 0, "errors": 0}

        while True:
            # Get next batch
            jobs = self.get_jobs_to_enrich(limit=self.batch_size)

            if not jobs:
                break

            # Process batch
            batch_stats = self.enrich_jobs(jobs)
            total_stats["processed"] += batch_stats["processed"]
            total_stats["enriched"] += batch_stats["enriched"]
            total_stats["errors"] += batch_stats["errors"]

        logger.info(
            f"All jobs enriched: processed={total_stats['processed']}, "
            f"enriched={total_stats['enriched']}, errors={total_stats['errors']}"
        )

        return total_stats
