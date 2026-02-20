"""Enrichment Analysis Service.

Analyzes job postings to identify missing skills and seniority patterns
in the enrichment detection system.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from shared import Database

from .queries import (
    EXTRACT_WORDS_FROM_DESCRIPTIONS,
    EXTRACT_WORDS_FROM_TITLES,
    FIND_MISSING_SENIORITY,
    FIND_POTENTIAL_MISSING_SKILLS,
    GET_ENRICHMENT_STATISTICS,
    GET_JOBS_WITH_MISSING_SKILLS,
    GET_SENIORITY_PATTERNS,
)

logger = logging.getLogger(__name__)

# Common stop words to filter out
STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "been",
    "be",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "must",
    "can",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "when",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "now",
}


class EnrichmentAnalyzer:
    """
    Service for analyzing enrichment gaps in job postings.

    Identifies missing skills and seniority patterns by analyzing job descriptions
    and titles, comparing them with extracted enrichment data.
    """

    def __init__(self, database: Database):
        """
        Initialize the enrichment analyzer.

        Args:
            database: Database connection interface (implements Database protocol)

        Raises:
            ValueError: If database is None
        """
        if not database:
            raise ValueError("Database is required")

        self.db = database
        self._existing_patterns: set[str] | None = None

    def analyze_missing_seniority(self, limit: int = 100) -> dict[str, Any]:
        """
        Find jobs where seniority_level IS NULL but title/description contains seniority indicators.

        Args:
            limit: Maximum number of jobs to analyze (default: 100)

        Returns:
            Dictionary with:
            - jobs: List of jobs with missing seniority detection
            - patterns: Grouped patterns showing detected vs missing seniority
            - total_found: Total number of jobs found
        """
        logger.info(f"Analyzing missing seniority detection (limit: {limit})")

        # Get jobs with missing seniority
        with self.db.get_cursor() as cur:
            cur.execute(FIND_MISSING_SENIORITY, (limit,))
            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

        # Get patterns grouped by detected seniority
        with self.db.get_cursor() as cur:
            cur.execute(GET_SENIORITY_PATTERNS)
            columns = [desc[0] for desc in cur.description]
            patterns = []
            for row in cur.fetchall():
                pattern_dict = dict(zip(columns, row))
                # Limit sample_titles to 10 if it's an array
                if isinstance(pattern_dict.get("sample_titles"), list):
                    pattern_dict["sample_titles"] = pattern_dict["sample_titles"][:10]
                patterns.append(pattern_dict)

        logger.info(f"Found {len(jobs)} job(s) with missing seniority detection")
        logger.info(f"Identified {len(patterns)} seniority pattern(s)")

        return {
            "jobs": jobs,
            "patterns": patterns,
            "total_found": len(jobs),
        }

    def analyze_missing_skills(self, limit: int = 50) -> dict[str, Any]:
        """
        Analyze job descriptions for technical terms not in TECHNICAL_SKILLS.

        Finds frequently mentioned technologies that were not extracted as skills.

        Args:
            limit: Maximum number of potential missing skills to return (default: 50)

        Returns:
            Dictionary with:
            - missing_skills: List of potential missing skills with statistics
            - total_analyzed: Total number of jobs analyzed
        """
        logger.info(f"Analyzing missing skills (limit: {limit})")

        with self.db.get_cursor() as cur:
            cur.execute(FIND_POTENTIAL_MISSING_SKILLS, (limit,))
            columns = [desc[0] for desc in cur.description]
            missing_skills = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.info(f"Found {len(missing_skills)} potential missing skill(s)")

        return {
            "missing_skills": missing_skills,
            "total_analyzed": len(missing_skills),
        }

    def get_jobs_with_missing_skill(self, skill_term: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get specific jobs where a skill term is mentioned but not extracted.

        Args:
            skill_term: The skill term to search for (e.g., "snowflake", "databricks")
            limit: Maximum number of jobs to return (default: 20)

        Returns:
            List of job dictionaries with missing skill
        """
        logger.info(f"Finding jobs with missing skill: {skill_term}")

        with self.db.get_cursor() as cur:
            cur.execute(GET_JOBS_WITH_MISSING_SKILLS, (skill_term, skill_term, limit))
            columns = [desc[0] for desc in cur.description]
            jobs = [dict(zip(columns, row)) for row in cur.fetchall()]

        logger.info(f"Found {len(jobs)} job(s) with missing skill '{skill_term}'")

        return jobs

    def get_enrichment_statistics(self) -> dict[str, Any]:
        """
        Get overall statistics about enrichment coverage.

        Returns:
            Dictionary with enrichment statistics:
            - total_jobs: Total number of jobs with descriptions
            - jobs_with_skills: Number of jobs with extracted skills
            - jobs_with_seniority: Number of jobs with extracted seniority
            - fully_enriched: Number of jobs with both skills and seniority
            - avg_skills_per_job: Average number of skills per job
        """
        logger.info("Getting enrichment statistics")

        with self.db.get_cursor() as cur:
            cur.execute(GET_ENRICHMENT_STATISTICS)
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]

            if row:
                stats = dict(zip(columns, row))
            else:
                stats = {
                    "total_jobs": 0,
                    "jobs_with_skills": 0,
                    "jobs_with_seniority": 0,
                    "fully_enriched": 0,
                    "avg_skills_per_job": 0.0,
                }

        logger.info(
            f"Enrichment coverage: {stats.get('jobs_with_skills', 0)}/{stats.get('total_jobs', 0)} jobs with skills"
        )

        return stats

    def generate_report(
        self,
        seniority_limit: int = 100,
        skills_limit: int = 50,
        include_pattern_discovery: bool = True,
        discovery_min_frequency: int = 2,
        discovery_max_terms: int = 500,
    ) -> dict[str, Any]:
        """
        Generate a comprehensive enrichment analysis report.

        Args:
            seniority_limit: Maximum number of jobs to analyze for missing seniority
            skills_limit: Maximum number of potential missing skills to return
            include_pattern_discovery: Whether to include pattern discovery (default: True)
            discovery_min_frequency: Minimum frequency for discovered terms (default: 2)
            discovery_max_terms: Maximum number of discovered terms to return (default: 500)

        Returns:
            Dictionary with complete analysis report:
            - statistics: Overall enrichment statistics
            - missing_seniority: Analysis of missing seniority detection
            - missing_skills: Analysis of missing skills detection
            - discovered_patterns: Discovered terms not in existing dictionaries
            - recommendations: Recommendations for improving enrichment
        """
        logger.info("Generating enrichment analysis report")

        # Get statistics
        statistics = self.get_enrichment_statistics()

        # Analyze missing seniority
        missing_seniority = self.analyze_missing_seniority(limit=seniority_limit)

        # Analyze missing skills
        missing_skills = self.analyze_missing_skills(limit=skills_limit)

        # Discover new patterns
        discovered_patterns = None
        if include_pattern_discovery:
            discovered_patterns = self.discover_missing_patterns(
                min_frequency=discovery_min_frequency, max_terms=discovery_max_terms
            )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            statistics, missing_seniority, missing_skills, discovered_patterns
        )

        report = {
            "statistics": statistics,
            "missing_seniority": missing_seniority,
            "missing_skills": missing_skills,
            "discovered_patterns": discovered_patterns,
            "recommendations": recommendations,
        }

        logger.info("Enrichment analysis report generated successfully")

        return report

    def _generate_recommendations(
        self,
        statistics: dict[str, Any],
        missing_seniority: dict[str, Any],
        missing_skills: dict[str, Any],
        discovered_patterns: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate recommendations based on analysis results.

        Args:
            statistics: Enrichment statistics
            missing_seniority: Missing seniority analysis results
            missing_skills: Missing skills analysis results

        Returns:
            Dictionary with recommendations
        """
        recommendations = {
            "seniority_patterns": [],
            "skills_to_add": [],
            "discovered_terms": [],
            "general": [],
        }

        # Add discovered patterns recommendations
        if discovered_patterns and discovered_patterns.get("terms"):
            # Group by n-gram size
            single_words = [t for t in discovered_patterns["terms"] if t.get("ngram_size", 1) == 1][
                :50
            ]
            phrases = [t for t in discovered_patterns["terms"] if t.get("ngram_size", 1) > 1][:50]

            recommendations["discovered_terms"] = {
                "high_frequency_single_words": single_words[:20],
                "high_frequency_phrases": phrases[:20],
                "total_discovered": len(discovered_patterns["terms"]),
            }

        # Seniority recommendations
        if missing_seniority.get("patterns"):
            for pattern in missing_seniority["patterns"]:
                detected = pattern.get("detected_seniority", "unknown")
                count = pattern.get("job_count", 0)
                if detected != "unknown" and count > 0:
                    recommendations["seniority_patterns"].append(
                        {
                            "pattern": detected,
                            "job_count": count,
                            "sample_titles": pattern.get("sample_titles", []),
                            "recommendation": f"Consider adding patterns for '{detected}' level. Found {count} jobs with this pattern.",
                        }
                    )

        # Skills recommendations
        if missing_skills.get("missing_skills"):
            for skill in missing_skills["missing_skills"][:20]:  # Top 20
                term = skill.get("term", "")
                missing_count = skill.get("missing_count", 0)
                mention_count = skill.get("mention_count", 0)
                if missing_count > 0:
                    recommendations["skills_to_add"].append(
                        {
                            "skill": term,
                            "missing_count": missing_count,
                            "mention_count": mention_count,
                            "sample_titles": skill.get("sample_titles", []),
                            "recommendation": f"Consider adding '{term}' to TECHNICAL_SKILLS. Found in {mention_count} jobs, missing from {missing_count} extractions.",
                        }
                    )

        # General recommendations
        total_jobs = statistics.get("total_jobs", 0)
        jobs_with_skills = statistics.get("jobs_with_skills", 0)
        jobs_with_seniority = statistics.get("jobs_with_seniority", 0)

        if total_jobs > 0:
            skills_coverage = (jobs_with_skills / total_jobs) * 100
            seniority_coverage = (jobs_with_seniority / total_jobs) * 100

            if skills_coverage < 80:
                recommendations["general"].append(
                    f"Skills coverage is {skills_coverage:.1f}%. Consider improving skill extraction patterns."
                )

            if seniority_coverage < 80:
                recommendations["general"].append(
                    f"Seniority coverage is {seniority_coverage:.1f}%. Consider expanding seniority pattern matching."
                )

        return recommendations

    def export_report_to_json(self, report: dict[str, Any], filepath: str) -> None:
        """
        Export analysis report to JSON file.

        Args:
            report: Report dictionary from generate_report()
            filepath: Path to output JSON file
        """
        logger.info(f"Exporting report to {filepath}")

        # Convert any non-serializable types
        serializable_report = self._make_serializable(report)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable_report, f, indent=2, ensure_ascii=False)

        logger.info(f"Report exported successfully to {filepath}")

    def _make_serializable(self, obj: Any) -> Any:
        """
        Recursively convert objects to JSON-serializable format.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable object
        """
        if isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, str | int | float | bool | type(None)):
            return obj
        else:
            # Convert other types to string
            return str(obj)

    def _load_existing_patterns(self) -> set[str]:
        """
        Load existing patterns from TECHNICAL_SKILLS and SENIORITY_PATTERNS.

        Returns:
            Set of all existing patterns (lowercase, normalized)
        """
        if self._existing_patterns is not None:
            return self._existing_patterns

        try:
            from enricher.seniority_patterns import SENIORITY_PATTERNS
            from enricher.technical_skills import get_all_skills

            # Load technical skills (already flattened)
            existing = get_all_skills()

            # Flatten seniority patterns
            for patterns in SENIORITY_PATTERNS.values():
                existing.update(patterns)

            # Normalize to lowercase
            self._existing_patterns = {pattern.lower().strip() for pattern in existing}

            logger.info(f"Loaded {len(self._existing_patterns)} existing patterns")
            return self._existing_patterns

        except ImportError as e:
            logger.warning(f"Could not import dictionaries: {e}. Using empty set.")
            self._existing_patterns = set()
            return self._existing_patterns

    def _generate_ngrams(self, words: list[str], max_ngram: int = 3) -> list[tuple[str, int]]:
        """
        Generate n-grams from a list of words.

        Args:
            words: List of words
            max_ngram: Maximum n-gram size (default: 3)

        Returns:
            List of tuples (ngram, ngram_size)
        """
        ngrams = []
        for n in range(1, min(max_ngram + 1, len(words) + 1)):
            for i in range(len(words) - n + 1):
                ngram = " ".join(words[i : i + n])
                if ngram.strip():
                    ngrams.append((ngram.strip(), n))
        return ngrams

    def discover_terms_from_descriptions(
        self, min_frequency: int = 2, max_terms: int = 1000
    ) -> dict[str, Any]:
        """
        Extract all terms from job descriptions and count frequencies.

        Args:
            min_frequency: Minimum frequency to include a term (default: 2)
            max_terms: Maximum number of terms to return (default: 1000)

        Returns:
            Dictionary with discovered terms and statistics
        """
        logger.info("Discovering terms from job descriptions")

        # Get all words from descriptions
        with self.db.get_cursor() as cur:
            cur.execute(EXTRACT_WORDS_FROM_DESCRIPTIONS)
            rows = cur.fetchall()

        # Group words by job and generate n-grams
        job_words: dict[int, list[str]] = {}
        job_titles: dict[int, str] = {}

        for row in rows:
            job_key = row[0]
            job_title = row[1]
            word = row[2]

            if word and word not in STOP_WORDS and len(word) >= 2:
                if job_key not in job_words:
                    job_words[job_key] = []
                    job_titles[job_key] = job_title
                job_words[job_key].append(word)

        # Generate n-grams and count frequencies
        term_counter: Counter[tuple[str, int]] = Counter()
        term_jobs: dict[tuple[str, int], set[int]] = {}

        for job_key, words in job_words.items():
            ngrams = self._generate_ngrams(words, max_ngram=3)
            for ngram, ngram_size in ngrams:
                key = (ngram, ngram_size)
                term_counter[key] += 1
                if key not in term_jobs:
                    term_jobs[key] = set()
                term_jobs[key].add(job_key)

        # Convert to list format
        terms = []
        for (term, ngram_size), frequency in term_counter.most_common(max_terms):
            if frequency >= min_frequency:
                job_ids = list(term_jobs[(term, ngram_size)])
                sample_titles = [
                    job_titles.get(job_id, "") for job_id in job_ids[:10] if job_id in job_titles
                ]
                terms.append(
                    {
                        "term": term,
                        "frequency": frequency,
                        "ngram_size": ngram_size,
                        "sample_titles": [t for t in sample_titles if t],
                        "appears_in": "description",
                    }
                )

        logger.info(f"Discovered {len(terms)} unique terms from descriptions")

        return {
            "terms": terms,
            "total_jobs_analyzed": len(job_words),
            "total_unique_terms": len(term_counter),
        }

    def discover_terms_from_titles(
        self, min_frequency: int = 2, max_terms: int = 1000
    ) -> dict[str, Any]:
        """
        Extract all terms from job titles and count frequencies.

        Args:
            min_frequency: Minimum frequency to include a term (default: 2)
            max_terms: Maximum number of terms to return (default: 1000)

        Returns:
            Dictionary with discovered terms and statistics
        """
        logger.info("Discovering terms from job titles")

        # Get all words from titles
        with self.db.get_cursor() as cur:
            cur.execute(EXTRACT_WORDS_FROM_TITLES)
            rows = cur.fetchall()

        # Group words by job and generate n-grams
        job_words: dict[int, list[str]] = {}
        job_titles: dict[int, str] = {}

        for row in rows:
            job_key = row[0]
            job_title = row[1]
            word = row[2]

            if word and word not in STOP_WORDS and len(word) >= 2:
                if job_key not in job_words:
                    job_words[job_key] = []
                    job_titles[job_key] = job_title
                job_words[job_key].append(word)

        # Generate n-grams and count frequencies
        term_counter: Counter[tuple[str, int]] = Counter()
        term_jobs: dict[tuple[str, int], set[int]] = {}

        for job_key, words in job_words.items():
            ngrams = self._generate_ngrams(words, max_ngram=3)
            for ngram, ngram_size in ngrams:
                key = (ngram, ngram_size)
                term_counter[key] += 1
                if key not in term_jobs:
                    term_jobs[key] = set()
                term_jobs[key].add(job_key)

        # Convert to list format
        terms = []
        for (term, ngram_size), frequency in term_counter.most_common(max_terms):
            if frequency >= min_frequency:
                job_ids = list(term_jobs[(term, ngram_size)])
                sample_titles = [
                    job_titles.get(job_id, "") for job_id in job_ids[:10] if job_id in job_titles
                ]
                terms.append(
                    {
                        "term": term,
                        "frequency": frequency,
                        "ngram_size": ngram_size,
                        "sample_titles": [t for t in sample_titles if t],
                        "appears_in": "title",
                    }
                )

        logger.info(f"Discovered {len(terms)} unique terms from titles")

        return {
            "terms": terms,
            "total_jobs_analyzed": len(job_words),
            "total_unique_terms": len(term_counter),
        }

    def filter_against_dictionaries(self, terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter out terms that exist in TECHNICAL_SKILLS or SENIORITY_PATTERNS.

        Args:
            terms: List of term dictionaries from discovery methods

        Returns:
            Filtered list of terms not in existing dictionaries
        """
        existing_patterns = self._load_existing_patterns()
        filtered_terms = []

        for term_dict in terms:
            term = term_dict.get("term", "").lower().strip()
            if term and term not in existing_patterns:
                # Also check if any part of the term matches (for multi-word terms)
                term_parts = term.split()
                if not any(part in existing_patterns for part in term_parts if len(part) > 2):
                    filtered_terms.append(term_dict)

        logger.info(f"Filtered {len(terms)} terms to {len(filtered_terms)} new terms")

        return filtered_terms

    def discover_missing_patterns(
        self,
        min_frequency: int = 2,
        max_terms: int = 1000,
        include_descriptions: bool = True,
        include_titles: bool = True,
    ) -> dict[str, Any]:
        """
        Main method to discover missing patterns from descriptions and/or titles.

        Args:
            min_frequency: Minimum frequency to include a term (default: 2)
            max_terms: Maximum number of terms to return (default: 1000)
            include_descriptions: Whether to analyze descriptions (default: True)
            include_titles: Whether to analyze titles (default: True)

        Returns:
            Dictionary with discovered missing patterns
        """
        logger.info("Discovering missing patterns")

        all_terms = []
        total_jobs_analyzed = 0

        if include_descriptions:
            desc_results = self.discover_terms_from_descriptions(
                min_frequency=min_frequency,
                max_terms=max_terms * 2,  # Get more to account for filtering
            )
            all_terms.extend(desc_results["terms"])
            total_jobs_analyzed += desc_results.get("total_jobs_analyzed", 0)

        if include_titles:
            title_results = self.discover_terms_from_titles(
                min_frequency=min_frequency,
                max_terms=max_terms * 2,  # Get more to account for filtering
            )
            all_terms.extend(title_results["terms"])
            # Don't double count jobs if both are included

        # Combine terms from both sources
        term_combined: dict[str, dict[str, Any]] = {}
        for term_dict in all_terms:
            term = term_dict["term"]
            if term not in term_combined:
                term_combined[term] = {
                    "term": term,
                    "frequency": 0,
                    "ngram_size": term_dict["ngram_size"],
                    "sample_titles": [],
                    "appears_in": set(),
                }
            term_combined[term]["frequency"] += term_dict["frequency"]
            term_combined[term]["sample_titles"].extend(term_dict["sample_titles"])
            term_combined[term]["appears_in"].add(term_dict["appears_in"])

        # Convert appears_in set to string
        combined_terms = []
        for term_dict in term_combined.values():
            appears_in = list(term_dict["appears_in"])
            if len(appears_in) == 2:
                appears_in_str = "both"
            else:
                appears_in_str = appears_in[0] if appears_in else "unknown"
            term_dict["appears_in"] = appears_in_str
            # Deduplicate sample titles
            term_dict["sample_titles"] = list(dict.fromkeys(term_dict["sample_titles"]))[:10]
            combined_terms.append(term_dict)

        # Sort by frequency
        combined_terms.sort(key=lambda x: x["frequency"], reverse=True)

        # Filter against existing dictionaries
        filtered_terms = self.filter_against_dictionaries(combined_terms)

        return {
            "terms": filtered_terms[:max_terms],
            "total_jobs_analyzed": total_jobs_analyzed if include_descriptions else 0,
            "total_unique_terms": len(combined_terms),
            "terms_after_filtering": len(filtered_terms),
        }
