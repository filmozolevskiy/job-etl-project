"""Script to create diverse test campaigns for enrichment analysis.

This script creates multiple test campaigns with varied roles, seniorities,
and skill combinations to gather diverse job posting data for analysis.
"""

import os
import sys
from pathlib import Path

# Add services directory to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from campaign_management import CampaignService
from shared import PostgreSQLDatabase


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def create_test_campaigns() -> list[int]:
    """Create diverse test campaigns for enrichment analysis.

    Returns:
        List of created campaign IDs
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    campaign_service = CampaignService(database=database)

    campaigns_to_create = [
        # Data Engineer campaigns
        {
            "campaign_name": "Data Engineer - Python",
            "query": "Data Engineer Python",
            "country": "us",
            "location": "United States",
            "skills": "Python;SQL;Spark;Airflow;AWS",
            "seniority": "mid",
        },
        {
            "campaign_name": "Senior Data Engineer",
            "query": "Senior Data Engineer",
            "country": "us",
            "location": "United States",
            "skills": "Python;Scala;Spark;Kafka;GCP",
            "seniority": "senior",
        },
        {
            "campaign_name": "Junior Data Engineer",
            "query": "Junior Data Engineer",
            "country": "us",
            "location": "United States",
            "skills": "Python;SQL;PostgreSQL",
            "seniority": "junior",
        },
        # Software Engineer campaigns
        {
            "campaign_name": "Software Engineer - Java",
            "query": "Software Engineer Java",
            "country": "us",
            "location": "United States",
            "skills": "Java;Spring;MySQL;Docker",
            "seniority": "mid",
        },
        {
            "campaign_name": "Software Engineer - JavaScript",
            "query": "Software Engineer JavaScript React",
            "country": "us",
            "location": "United States",
            "skills": "JavaScript;TypeScript;React;Node.js",
            "seniority": "mid",
        },
        {
            "campaign_name": "Senior Software Engineer",
            "query": "Senior Software Engineer",
            "country": "us",
            "location": "United States",
            "skills": "Python;Java;Kubernetes;AWS;Microservices",
            "seniority": "senior",
        },
        # Data Scientist campaigns
        {
            "campaign_name": "Data Scientist - ML",
            "query": "Data Scientist Machine Learning",
            "country": "us",
            "location": "United States",
            "skills": "Python;TensorFlow;PyTorch;Scikit-learn;Pandas",
            "seniority": "mid",
        },
        {
            "campaign_name": "Senior Data Scientist",
            "query": "Senior Data Scientist",
            "country": "us",
            "location": "United States",
            "skills": "Python;ML;Deep Learning;NLP;AWS",
            "seniority": "senior",
        },
        # Product Manager campaigns
        {
            "campaign_name": "Product Manager - Tech",
            "query": "Product Manager Technology",
            "country": "us",
            "location": "United States",
            "skills": "Agile;Scrum;Jira;SQL;Analytics",
            "seniority": "mid",
        },
        {
            "campaign_name": "Senior Product Manager",
            "query": "Senior Product Manager",
            "country": "us",
            "location": "United States",
            "skills": "Product Management;Agile;Data Analysis;Strategy",
            "seniority": "senior",
        },
        # DevOps Engineer campaigns
        {
            "campaign_name": "DevOps Engineer - Cloud",
            "query": "DevOps Engineer AWS",
            "country": "us",
            "location": "United States",
            "skills": "AWS;Docker;Kubernetes;Terraform;CI/CD",
            "seniority": "mid",
        },
        {
            "campaign_name": "Senior DevOps Engineer",
            "query": "Senior DevOps Engineer",
            "country": "us",
            "location": "United States",
            "skills": "AWS;Azure;Kubernetes;Terraform;Ansible;Jenkins",
            "seniority": "senior",
        },
    ]

    created_campaign_ids = []

    print("Creating test campaigns for enrichment analysis...")
    print(f"Total campaigns to create: {len(campaigns_to_create)}\n")

    for campaign_config in campaigns_to_create:
        try:
            campaign_id = campaign_service.create_campaign(
                campaign_name=campaign_config["campaign_name"],
                query=campaign_config["query"],
                country=campaign_config["country"],
                location=campaign_config.get("location"),
                skills=campaign_config.get("skills"),
                seniority=campaign_config.get("seniority"),
                is_active=True,
            )
            created_campaign_ids.append(campaign_id)
            print(f"✓ Created campaign {campaign_id}: {campaign_config['campaign_name']}")
        except Exception as e:
            print(f"✗ Failed to create campaign '{campaign_config['campaign_name']}': {e}")

    print(f"\n✓ Successfully created {len(created_campaign_ids)} campaign(s)")
    print(f"Campaign IDs: {created_campaign_ids}")

    return created_campaign_ids


if __name__ == "__main__":
    try:
        campaign_ids = create_test_campaigns()
        sys.exit(0)
    except Exception as e:
        print(f"Error creating test campaigns: {e}", file=sys.stderr)
        sys.exit(1)
