"""Enricher service package.

This package contains services for enriching job postings with extracted
skills and seniority levels using NLP techniques and ChatGPT.
"""

from .chatgpt_enricher import ChatGPTEnricher
from .job_enricher import JobEnricher

__all__ = ["JobEnricher", "ChatGPTEnricher"]
