"""
Company Extractor Service

Extracts company data from Glassdoor API and writes to raw.glassdoor_companies table.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any

from rapidfuzz import fuzz
from shared import Database

from .glassdoor_client import GlassdoorClient
from .queries import (
    CHECK_GLASSDOOR_TABLE_EXISTS,
    GET_COMPANIES_TO_ENRICH_WITH_TABLE,
    GET_COMPANIES_TO_ENRICH_WITHOUT_TABLE,
    INSERT_COMPANY,
    MARK_COMPANY_ERROR,
    MARK_COMPANY_QUEUED,
    UPDATE_ENRICHMENT_STATUS,
)

logger = logging.getLogger(__name__)


class CompanyExtractor:
    """
    Service for extracting company data from Glassdoor API.

    Scans staging.jsearch_job_postings for employer names, identifies companies
    not yet enriched, and calls Glassdoor API to fetch company data.
    """

    def __init__(self, database: Database, glassdoor_client: GlassdoorClient):
        """
        Initialize the company extractor.

        Args:
            database: Database connection interface (implements Database protocol)
            glassdoor_client: Glassdoor API client instance

        Raises:
            ValueError: If database or glassdoor_client is None
        """
        if not database:
            raise ValueError("Database is required")
        if not glassdoor_client:
            raise ValueError("GlassdoorClient is required")

        self.db = database
        self.client = glassdoor_client

    def get_companies_to_enrich(self, limit: int | None = None) -> list[str]:
        """
        Get list of company lookup keys that need enrichment.

        Scans staging.jsearch_job_postings for unique employer names that are
        not yet in staging.glassdoor_companies or in the enrichment queue with success/not_found status.

        Args:
            limit: Maximum number of companies to return (None for all)

        Returns:
            List of company lookup keys (normalized company names)
        """
        # Validate limit if provided
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError(f"Limit must be a positive integer, got: {limit}")

        with self.db.get_cursor() as cur:
            # Check if staging.glassdoor_companies table exists
            cur.execute(CHECK_GLASSDOOR_TABLE_EXISTS)
            glassdoor_table_exists = cur.fetchone()[0]

            # Get unique employer names from staging that aren't already enriched
            # Check both staging.glassdoor_companies (if it exists) and company_enrichment_queue
            if glassdoor_table_exists:
                query = GET_COMPANIES_TO_ENRICH_WITH_TABLE
            else:
                # If staging.glassdoor_companies doesn't exist yet (first run), only check queue
                logger.info(
                    "staging.glassdoor_companies table does not exist yet, skipping that check"
                )
                query = GET_COMPANIES_TO_ENRICH_WITHOUT_TABLE

            if limit:
                query += " LIMIT %s"
                cur.execute(query, (limit,))
            else:
                cur.execute(query)
            companies = [row[0] for row in cur.fetchall()]

            logger.info(f"Found {len(companies)} companies needing enrichment")
            return companies

    def mark_company_queued(self, company_lookup_key: str):
        """
        Mark a company as queued in the enrichment queue.

        Args:
            company_lookup_key: Normalized company name/domain
        """
        with self.db.get_cursor() as cur:
            cur.execute(MARK_COMPANY_QUEUED, (company_lookup_key,))

    def extract_company(self, company_lookup_key: str) -> dict[str, Any] | None:
        """
        Extract company data from Glassdoor API for a single company.

        Uses fuzzy matching to select the best match when multiple results are returned.

        Args:
            company_lookup_key: Normalized company name/domain to search for

        Returns:
            Company data dictionary if found, None otherwise
        """
        logger.info(f"Searching Glassdoor for company: {company_lookup_key}")

        try:
            # Mark as queued
            self.mark_company_queued(company_lookup_key)

            # Call Glassdoor API
            response = self.client.search_company(
                query=company_lookup_key,
                limit=10,  # Get multiple results for fuzzy matching
            )

            # Check response
            logger.debug(
                f"API response for {company_lookup_key}: status={response.get('status')}, keys={list(response.keys()) if isinstance(response, dict) else 'not a dict'}"
            )

            # Check if response has error status
            if response.get("status") and response.get("status") != "OK":
                logger.warning(
                    f"API returned non-OK status for {company_lookup_key}: {response.get('status')}"
                )
                error_msg = response.get("error", {}).get("message", "Unknown error")
                logger.warning(f"Error message: {error_msg}")
                self._mark_company_error(
                    company_lookup_key, f"API status: {response.get('status')} - {error_msg}"
                )
                return None

            # Get companies data - try different possible response structures
            companies_data = response.get("data", [])

            # Log what we got
            if companies_data:
                logger.debug(
                    f"Found {len(companies_data)} results in 'data' key for {company_lookup_key}"
                )
                logger.debug(
                    f"First result sample: {companies_data[0] if companies_data else 'N/A'}"
                )
            else:
                # Try alternative response structure
                companies_data = response.get("companies", [])
                if companies_data:
                    logger.debug(
                        f"Found {len(companies_data)} results in 'companies' key for {company_lookup_key}"
                    )
                else:
                    # Try if response itself is a list
                    if isinstance(response, list):
                        companies_data = response
                        logger.debug(f"Response is a list with {len(companies_data)} items")

            # Check if data is empty or None
            if not companies_data or (
                isinstance(companies_data, list) and len(companies_data) == 0
            ):
                # Log at INFO level with more details
                data_value = response.get("data")
                status_value = response.get("status", "unknown")
                logger.info(
                    f"No company found for: {company_lookup_key} "
                    f"(status: {status_value}, data type: {type(data_value).__name__}, "
                    f"data length: {len(data_value) if isinstance(data_value, list) else 'N/A'})"
                )
                self._mark_company_not_found(company_lookup_key)
                return None

            # Use fuzzy matching to select best match
            company_data = self._select_best_match(companies_data, company_lookup_key)

            if company_data:
                logger.info(
                    f"Found company: {company_data.get('name', 'Unknown')} (ID: {company_data.get('company_id')})"
                )
                return company_data
            else:
                logger.info(
                    f"No company found with sufficient similarity for: {company_lookup_key}"
                )
                self._mark_company_not_found(company_lookup_key)
                return None

        except Exception as e:
            logger.error(f"Error extracting company {company_lookup_key}: {e}", exc_info=True)
            self._mark_company_error(company_lookup_key, str(e))
            return None

    def _select_best_match(
        self,
        companies_data: list[dict[str, Any]],
        company_lookup_key: str,
        similarity_threshold: float = 0.85,
    ) -> dict[str, Any] | None:
        """
        Select the best matching company from API results using fuzzy matching.

        Args:
            companies_data: List of company dictionaries from API
            company_lookup_key: Original normalized company name to match against
            similarity_threshold: Minimum similarity ratio (0.0-1.0) to accept a match. Default 0.85 (85%)

        Returns:
            Best matching company dictionary if similarity >= threshold, None otherwise
        """
        if not companies_data:
            return None

        if len(companies_data) == 1:
            # Only one result, return it if similarity is acceptable
            company_name = companies_data[0].get("name", "")
            similarity = fuzz.ratio(company_lookup_key.lower(), company_name.lower()) / 100.0
            if similarity >= similarity_threshold:
                return companies_data[0]
            else:
                logger.warning(
                    f"Single result similarity ({similarity:.2%}) below threshold "
                    f"({similarity_threshold:.2%}) for {company_lookup_key}"
                )
                return None

        # Multiple results - find best match
        best_match = None
        best_similarity = 0.0

        for company in companies_data:
            company_name = company.get("name", "")
            if not company_name:
                continue

            # Calculate similarity ratio (0-100, convert to 0-1)
            similarity = fuzz.ratio(company_lookup_key.lower(), company_name.lower()) / 100.0

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = company

        # Check if best match meets threshold
        if best_match and best_similarity >= similarity_threshold:
            logger.info(
                f"Selected best match: '{best_match.get('name')}' "
                f"(similarity: {best_similarity:.2%}) for '{company_lookup_key}'"
            )
            return best_match
        else:
            logger.warning(
                f"Best match similarity ({best_similarity:.2%}) below threshold "
                f"({similarity_threshold:.2%}) for {company_lookup_key}"
            )
            logger.debug(
                f"Available matches: {[c.get('name', 'Unknown') for c in companies_data[:3]]}"
            )
            return None

    def _write_company_to_db(self, company_data: dict[str, Any], company_lookup_key: str):
        """
        Write company data to raw.glassdoor_companies table.

        Args:
            company_data: Company dictionary from API
            company_lookup_key: Lookup key used to find the company
        """
        with self.db.get_cursor() as cur:
            now = datetime.now()
            today = date.today()

            # Generate surrogate key
            company_id = company_data.get("company_id", "")
            key_string = f"{company_id}|{company_lookup_key}"
            glassdoor_companies_key = int(hashlib.md5(key_string.encode()).hexdigest()[:15], 16)

            # Note: Duplicates will be handled by staging layer deduplication
            cur.execute(
                INSERT_COMPANY,
                (
                    glassdoor_companies_key,
                    json.dumps(company_data),
                    company_lookup_key,
                    today,
                    now,
                    "glassdoor",
                ),
            )

            # Mark as successful in enrichment queue
            self._mark_company_success(company_lookup_key)

    def _mark_company_success(self, company_lookup_key: str):
        """Mark company as successfully enriched."""
        self._update_enrichment_status(company_lookup_key, "success")

    def _mark_company_not_found(self, company_lookup_key: str):
        """Mark company as not found."""
        self._update_enrichment_status(company_lookup_key, "not_found")

    def _mark_company_error(self, company_lookup_key: str, error_message: str):
        """Mark company enrichment as error."""
        with self.db.get_cursor() as cur:
            cur.execute(MARK_COMPANY_ERROR, (error_message[:500], company_lookup_key))

    def _update_enrichment_status(self, company_lookup_key: str, status: str):
        """Update enrichment status in queue."""
        with self.db.get_cursor() as cur:
            cur.execute(UPDATE_ENRICHMENT_STATUS, (status, status, company_lookup_key))

    def extract_all_companies(self, limit: int | None = None) -> dict[str, str]:
        """
        Extract company data for all companies needing enrichment.

        Args:
            limit: Maximum number of companies to process (None for all)

        Returns:
            Dictionary mapping company_lookup_key to status (success/not_found/error)
        """
        companies = self.get_companies_to_enrich(limit=limit)

        if not companies:
            logger.info("No companies need enrichment")
            return {}

        results = {}
        for company_lookup_key in companies:
            try:
                company_data = self.extract_company(company_lookup_key)
                if company_data:
                    self._write_company_to_db(company_data, company_lookup_key)
                    results[company_lookup_key] = "success"
                else:
                    results[company_lookup_key] = "not_found"
            except Exception as e:
                logger.error(f"Failed to extract company {company_lookup_key}: {e}")
                results[company_lookup_key] = "error"

        # Print summary
        success_count = sum(1 for v in results.values() if v == "success")
        not_found_count = sum(1 for v in results.values() if v == "not_found")
        error_count = sum(1 for v in results.values() if v == "error")

        logger.info(
            f"Extraction complete. Success: {success_count}, Not Found: {not_found_count}, Errors: {error_count}"
        )

        return results
