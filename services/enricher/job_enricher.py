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
    Service for enriching job postings with extracted skills and seniority levels.

    Reads jobs from staging.jsearch_job_postings, extracts skills using spaCy NLP,
    extracts seniority from job titles, and updates the staging table.
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

        return {
            "extracted_skills": extracted_skills,
            "seniority_level": seniority_level,
            "remote_work_type": remote_work_type,
        }

    def update_job_enrichment(
        self,
        job_key: int,
        extracted_skills: list[str] | None,
        seniority_level: str | None,
        remote_work_type: str | None,
        enrichment_status_updates: str,
    ) -> None:
        """
        Update a job in staging.jsearch_job_postings with enrichment data.

        Args:
            job_key: jsearch_job_postings_key (primary key)
            extracted_skills: List of extracted skills or None (None if not processed)
            seniority_level: Seniority level string or None (None if not processed)
            remote_work_type: Remote work type string or None (None if not processed)
            enrichment_status_updates: JSONB string with flags to set to true
                Example: '{"skills_enriched": true, "seniority_enriched": true}'

        Note: enrichment_status_updates should only contain flags for fields that were
        actually processed. This prevents infinite loops by marking fields as processed.
        """
        # Convert skills list to JSON string for storage
        # If extracted_skills is None (not processed), pass None to preserve existing via COALESCE
        # If extracted_skills is a list (processed, even if empty), convert to JSON string
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
                    enrichment_status_updates,
                    job_key,
                ),
            )
            logger.debug(
                f"Updated enrichment for job_key={job_key}: "
                f"skills={'extracted' if extracted_skills is not None else 'preserved'}, "
                f"seniority={'extracted' if seniority_level is not None else 'preserved'}, "
                f"remote_type={'extracted' if remote_work_type is not None else 'preserved'}, "
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
                enrichment_status = job.get("enrichment_status") or {}
                if isinstance(enrichment_status, str):
                    enrichment_status = json.loads(enrichment_status)

                skills_enriched = enrichment_status.get("skills_enriched", False)
                seniority_enriched = enrichment_status.get("seniority_enriched", False)
                remote_type_enriched = enrichment_status.get("remote_type_enriched", False)

                # Only extract fields that haven't been processed yet
                extracted_skills = None
                seniority_level = None
                remote_work_type = None
                status_updates = {}

                job_title = job.get("job_title", "") or ""
                job_description = job.get("job_description", "") or ""

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

                # Build enrichment_status_updates JSONB string
                enrichment_status_updates = json.dumps(status_updates) if status_updates else "{}"

                # Update database (only updates fields that were extracted)
                self.update_job_enrichment(
                    job_key,
                    extracted_skills,
                    seniority_level,
                    remote_work_type,
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
