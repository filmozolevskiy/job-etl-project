#!/usr/bin/env python3
"""Run pattern discovery on collected job data."""

import os
import sys
from pathlib import Path

# Add services to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from enrichment_analysis import EnrichmentAnalyzer
from shared import PostgreSQLDatabase


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def main():
    """Run pattern discovery."""
    print("=" * 70)
    print("Pattern Discovery - Finding Missing Skills & Seniority Patterns")
    print("=" * 70)

    # Connect to database
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    analyzer = EnrichmentAnalyzer(database=database)

    # Step 1: Get statistics first
    print("\n[STATS] Getting enrichment statistics...")
    stats = analyzer.get_enrichment_statistics()
    print(f"   Total jobs: {stats['total_jobs']}")
    print(
        f"   Jobs with skills: {stats['jobs_with_skills']} ({stats['jobs_with_skills'] / max(stats['total_jobs'], 1) * 100:.1f}%)"
    )
    print(
        f"   Jobs with seniority: {stats['jobs_with_seniority']} ({stats['jobs_with_seniority'] / max(stats['total_jobs'], 1) * 100:.1f}%)"
    )

    if stats["total_jobs"] == 0:
        print(
            "\n[WARNING] No jobs found in database. Please run the DAG first to collect job data."
        )
        return

    # Step 2: Discover missing patterns
    print("\n[DISCOVERY] Discovering missing patterns from job descriptions and titles...")
    print("   (This may take a minute for large datasets)")

    missing_patterns = analyzer.discover_missing_patterns(
        min_frequency=3,  # Only show terms that appear at least 3 times
        max_terms=200,  # Get top 200 terms
        include_descriptions=True,
        include_titles=True,
    )

    print("\n[SUCCESS] Analysis complete!")
    print(f"   Total unique terms discovered: {missing_patterns['total_unique_terms']}")
    print(f"   New terms (not in dictionaries): {missing_patterns['terms_after_filtering']}")

    # Step 3: Display results
    terms = missing_patterns["terms"]

    if not terms:
        print(
            "\n[WARNING] No missing patterns found. All discovered terms are already in dictionaries."
        )
        print("   Try lowering min_frequency or check if you have enough job data.")
        return

    # Group by n-gram size
    single_words = [t for t in terms if t["ngram_size"] == 1]
    two_words = [t for t in terms if t["ngram_size"] == 2]
    three_words = [t for t in terms if t["ngram_size"] == 3]

    print("\n" + "=" * 70)
    print("DISCOVERED PATTERNS (Not in Current Dictionaries)")
    print("=" * 70)

    # Show single words (likely skills)
    if single_words:
        print("\n[1-GRAM] Single Words (Top 30):")
        print("-" * 70)
        for i, term in enumerate(single_words[:30], 1):
            print(
                f"  {i:2d}. {term['term']:30s} | Freq: {term['frequency']:4d} | "
                f"In: {term['appears_in']:12s}"
            )
            if term.get("sample_titles") and i <= 5:
                print(f"      Example: {term['sample_titles'][0]}")

    # Show two-word phrases
    if two_words:
        print("\n[2-GRAM] Two-Word Phrases (Top 20):")
        print("-" * 70)
        for i, term in enumerate(two_words[:20], 1):
            print(
                f"  {i:2d}. {term['term']:40s} | Freq: {term['frequency']:4d} | "
                f"In: {term['appears_in']:12s}"
            )
            if term.get("sample_titles") and i <= 3:
                print(f"      Example: {term['sample_titles'][0]}")

    # Show three-word phrases
    if three_words:
        print("\n[3-GRAM] Three-Word Phrases (Top 10):")
        print("-" * 70)
        for i, term in enumerate(three_words[:10], 1):
            print(f"  {i:2d}. {term['term']:50s} | Freq: {term['frequency']:4d}")
            if term.get("sample_titles") and i <= 2:
                print(f"      Example: {term['sample_titles'][0]}")

    # Step 4: Export discovered patterns to JSON
    print("\n" + "=" * 70)
    print("[EXPORT] Exporting discovered patterns to JSON...")

    output_data = {
        "statistics": stats,
        "discovered_patterns": missing_patterns,
        "summary": {
            "total_jobs": stats["total_jobs"],
            "total_unique_terms": missing_patterns["total_unique_terms"],
            "new_terms_found": missing_patterns["terms_after_filtering"],
            "single_words_count": len(single_words),
            "two_word_phrases_count": len(two_words),
            "three_word_phrases_count": len(three_words),
        },
    }

    import json
    from decimal import Decimal

    def make_json_serializable(obj):
        """Convert non-serializable types to JSON-compatible types."""
        if isinstance(obj, dict):
            return {key: make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [make_json_serializable(item) for item in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    output_file = "enrichment_analysis_report.json"
    serializable_data = make_json_serializable(output_data)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable_data, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Report exported to: {output_file}")

    # Show summary
    print("\n[SUMMARY]")
    print(f"   - {len(single_words)} high-frequency single words discovered")
    print(f"   - {len(two_words)} high-frequency two-word phrases discovered")
    print(f"   - {len(three_words)} high-frequency three-word phrases discovered")

    print("\n" + "=" * 70)
    print("[SUCCESS] Pattern Discovery Complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review the discovered patterns above")
    print("  2. Check the JSON report for detailed analysis")
    print("  3. Add relevant terms to TECHNICAL_SKILLS or SENIORITY_PATTERNS")
    print("  4. Re-run enrichment to validate improvements")


if __name__ == "__main__":
    main()
