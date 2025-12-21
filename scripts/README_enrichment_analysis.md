# Enrichment Analysis Guide

This guide explains how to analyze and improve the enrichment detection system for job postings.

## Overview

The enrichment analysis process helps identify gaps in skill and seniority detection by:
1. Creating diverse test profiles to gather varied job posting data
2. Running DAGs to collect job postings for these profiles
3. Analyzing the collected data to find missing skills and seniority patterns
4. Using the findings to improve the enrichment dictionaries

## Prerequisites

- PostgreSQL database with job postings data
- Python 3.11+ with required dependencies
- Access to the services directory structure
- Environment variables set for database connection (or defaults will be used)

## Step 1: Create Test Profiles

Create diverse test profiles to gather job posting data across different roles, seniorities, and skill combinations.

### Using the Script

```bash
python scripts/create_test_profiles.py
```

This script creates 12 test profiles covering:
- **Roles**: Data Engineer, Software Engineer, Data Scientist, Product Manager, DevOps Engineer
- **Seniority Levels**: Junior, Mid, Senior
- **Skill Focuses**: Python-heavy, Java-heavy, Cloud-focused, ML-focused

The script will:
- Create profiles using `ProfileService`
- Mark all profiles as active for DAG processing
- Output the created profile IDs

### Manual Profile Creation

You can also create profiles manually using the Profile Management UI or by directly inserting into `marts.profile_preferences`.

## Step 2: Run DAG for Data Collection

Run the `jobs_etl_daily` DAG manually via the Airflow UI to collect job postings for all active profiles.

1. Navigate to Airflow UI (typically http://localhost:8080)
2. Find the `jobs_etl_daily` DAG
3. Click "Trigger DAG" to run it manually
4. Wait for the DAG to complete (this may take several minutes)

The DAG will:
- Extract job postings from JSearch API for all active profiles
- Normalize jobs to staging layer
- Run the enricher service to extract skills and seniority
- Build marts and rank jobs

## Step 3: Run Enrichment Analysis

Use the `EnrichmentAnalyzer` service to analyze the collected data.

### Basic Usage

```python
import os
import sys
from pathlib import Path

# Add services to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from enrichment_analysis import EnrichmentAnalyzer
from shared import PostgreSQLDatabase

# Build database connection
db_conn_str = "postgresql://user:password@host:port/dbname"
database = PostgreSQLDatabase(connection_string=db_conn_str)

# Initialize analyzer
analyzer = EnrichmentAnalyzer(database=database)

# Generate full report
report = analyzer.generate_report(seniority_limit=100, skills_limit=50)

# Export to JSON
analyzer.export_report_to_json(report, "enrichment_analysis_report.json")
```

### Individual Analysis Methods

```python
# Analyze missing seniority
missing_seniority = analyzer.analyze_missing_seniority(limit=100)

# Analyze missing skills
missing_skills = analyzer.analyze_missing_skills(limit=50)

# Get specific jobs with a missing skill
jobs = analyzer.get_jobs_with_missing_skill("snowflake", limit=20)

# Get overall statistics
stats = analyzer.get_enrichment_statistics()
```

### Example Script

Create a script `scripts/run_enrichment_analysis.py`:

```python
#!/usr/bin/env python3
"""Run enrichment analysis and generate report."""

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
    """Run enrichment analysis."""
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    analyzer = EnrichmentAnalyzer(database=database)

    print("Generating enrichment analysis report...")
    report = analyzer.generate_report(seniority_limit=100, skills_limit=50)

    # Print summary
    stats = report["statistics"]
    print(f"\n=== Enrichment Statistics ===")
    print(f"Total jobs: {stats['total_jobs']}")
    print(f"Jobs with skills: {stats['jobs_with_skills']} ({stats['jobs_with_skills']/stats['total_jobs']*100:.1f}%)")
    print(f"Jobs with seniority: {stats['jobs_with_seniority']} ({stats['jobs_with_seniority']/stats['total_jobs']*100:.1f}%)")
    print(f"Fully enriched: {stats['fully_enriched']} ({stats['fully_enriched']/stats['total_jobs']*100:.1f}%)")
    print(f"Avg skills per job: {stats['avg_skills_per_job']}")

    # Print missing seniority
    missing_sr = report["missing_seniority"]
    print(f"\n=== Missing Seniority ===")
    print(f"Jobs with missing seniority: {missing_sr['total_found']}")
    for pattern in missing_sr["patterns"][:5]:
        print(f"  - {pattern['detected_seniority']}: {pattern['job_count']} jobs")

    # Print missing skills
    missing_skills = report["missing_skills"]
    print(f"\n=== Missing Skills (Top 10) ===")
    for skill in missing_skills["missing_skills"][:10]:
        print(f"  - {skill['term']}: missing from {skill['missing_count']} jobs (mentioned in {skill['mention_count']} jobs)")

    # Print recommendations
    recs = report["recommendations"]
    print(f"\n=== Recommendations ===")
    if recs["skills_to_add"]:
        print("Skills to consider adding:")
        for skill_rec in recs["skills_to_add"][:10]:
            print(f"  - {skill_rec['skill']}: {skill_rec['recommendation']}")

    if recs["general"]:
        print("\nGeneral recommendations:")
        for rec in recs["general"]:
            print(f"  - {rec}")

    # Export report
    output_file = "enrichment_analysis_report.json"
    analyzer.export_report_to_json(report, output_file)
    print(f"\n✓ Full report exported to: {output_file}")

if __name__ == "__main__":
    main()
```

## Step 4: Interpret Results

### Understanding the Report

The analysis report contains:

1. **Statistics**: Overall enrichment coverage metrics
2. **Missing Seniority**: Jobs where seniority patterns were detected but not extracted
3. **Missing Skills**: Technical terms found in job descriptions but not in `TECHNICAL_SKILLS`
4. **Recommendations**: Actionable suggestions for improvement

### Key Metrics

- **Skills Coverage**: Percentage of jobs with extracted skills
- **Seniority Coverage**: Percentage of jobs with extracted seniority
- **Missing Count**: Number of jobs where a skill/seniority was mentioned but not extracted

### Identifying Patterns

Look for:
- **High missing_count**: Skills/seniority patterns that appear frequently but aren't being detected
- **Sample titles**: Review actual job titles to understand context
- **Coverage gaps**: Areas where enrichment is below 80%

## Step 5: Update Enrichment Dictionaries

Based on the analysis results, update the enrichment dictionaries:

### Update Technical Skills

Edit `services/enricher/technical_skills.py`:

```python
TECHNICAL_SKILLS = {
    # ... existing skills ...
    # Add new skills from analysis
    "snowflake",
    "databricks",
    "redshift",
    # ... etc
}
```

### Update Seniority Patterns

Edit `services/enricher/seniority_patterns.py`:

```python
SENIORITY_PATTERNS = {
    # ... existing patterns ...
    "junior": [
        # ... existing patterns ...
        "new_pattern",  # Add new patterns
    ],
    # ... etc
}
```

## Step 6: Re-run Enrichment

After updating the dictionaries:

1. Re-run the enrichment task in the DAG (or run it standalone)
2. Re-run the analysis to validate improvements
3. Compare coverage metrics before and after

### Re-running Enrichment Only

You can trigger just the enrichment task:

```python
from enricher import JobEnricher
from shared import PostgreSQLDatabase

db_conn_str = "postgresql://user:password@host:port/dbname"
database = PostgreSQLDatabase(connection_string=db_conn_str)

enricher = JobEnricher(database=database, batch_size=100)
stats = enricher.enrich_all_pending_jobs()
print(f"Processed: {stats['processed']}, Enriched: {stats['enriched']}, Errors: {stats['errors']}")
```

## Step 7: Validate Improvements

After updating dictionaries and re-running enrichment:

1. Run the analysis again
2. Compare statistics:
   - Skills coverage should increase
   - Seniority coverage should increase
   - Missing counts should decrease
3. Review sample jobs to ensure quality hasn't degraded

## Troubleshooting

### No Jobs Found

- Ensure DAG has run successfully
- Check that profiles are active
- Verify jobs exist in `staging.jsearch_job_postings`

### Database Connection Issues

- Verify environment variables are set correctly
- Check database is accessible
- Ensure connection string format is correct

### Analysis Takes Too Long

- Reduce limits in analysis methods
- Use specific skill searches instead of full analysis
- Consider analyzing a sample of recent jobs only

## Best Practices

1. **Regular Analysis**: Run analysis periodically (e.g., weekly) to catch new patterns
2. **Incremental Updates**: Add skills/patterns gradually and validate each change
3. **Quality Over Quantity**: Focus on high-impact missing skills first
4. **Review Samples**: Always review sample job titles before adding patterns
5. **Test Changes**: Re-run enrichment and analysis after each update

## Files Reference

- **Profile Creation**: `scripts/create_test_profiles.py`
- **Analysis Service**: `services/enrichment_analysis/enrichment_analyzer.py`
- **Analysis Queries**: `services/enrichment_analysis/queries.py`
- **Technical Skills**: `services/enricher/technical_skills.py`
- **Seniority Patterns**: `services/enricher/seniority_patterns.py`

## Next Steps

After completing the analysis cycle:
1. Document findings and decisions
2. Update enrichment dictionaries based on recommendations
3. Re-run enrichment and validate improvements
4. Consider automating regular analysis runs

