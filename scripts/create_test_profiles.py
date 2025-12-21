"""Script to create diverse test profiles for enrichment analysis.

This script creates multiple test profiles with varied roles, seniorities,
and skill combinations to gather diverse job posting data for analysis.
"""

import os
import sys
from pathlib import Path

# Add services directory to path
services_path = Path(__file__).parent.parent / "services"
sys.path.insert(0, str(services_path))

from profile_management import ProfileService
from shared import PostgreSQLDatabase


def build_db_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "job_search_db")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def create_test_profiles() -> list[int]:
    """Create diverse test profiles for enrichment analysis.

    Returns:
        List of created profile IDs
    """
    db_conn_str = build_db_connection_string()
    database = PostgreSQLDatabase(connection_string=db_conn_str)
    profile_service = ProfileService(database=database)

    profiles_to_create = [
        # Data Engineer profiles
        {
            "profile_name": "Data Engineer - Python",
            "query": "Data Engineer Python",
            "country": "us",
            "location": "United States",
            "skills": "Python;SQL;Spark;Airflow;AWS",
            "seniority": "mid",
        },
        {
            "profile_name": "Senior Data Engineer",
            "query": "Senior Data Engineer",
            "country": "us",
            "location": "United States",
            "skills": "Python;Scala;Spark;Kafka;GCP",
            "seniority": "senior",
        },
        {
            "profile_name": "Junior Data Engineer",
            "query": "Junior Data Engineer",
            "country": "us",
            "location": "United States",
            "skills": "Python;SQL;PostgreSQL",
            "seniority": "junior",
        },
        # Software Engineer profiles
        {
            "profile_name": "Software Engineer - Java",
            "query": "Software Engineer Java",
            "country": "us",
            "location": "United States",
            "skills": "Java;Spring;MySQL;Docker",
            "seniority": "mid",
        },
        {
            "profile_name": "Software Engineer - JavaScript",
            "query": "Software Engineer JavaScript React",
            "country": "us",
            "location": "United States",
            "skills": "JavaScript;TypeScript;React;Node.js",
            "seniority": "mid",
        },
        {
            "profile_name": "Senior Software Engineer",
            "query": "Senior Software Engineer",
            "country": "us",
            "location": "United States",
            "skills": "Python;Java;Kubernetes;AWS;Microservices",
            "seniority": "senior",
        },
        # Data Scientist profiles
        {
            "profile_name": "Data Scientist - ML",
            "query": "Data Scientist Machine Learning",
            "country": "us",
            "location": "United States",
            "skills": "Python;TensorFlow;PyTorch;Scikit-learn;Pandas",
            "seniority": "mid",
        },
        {
            "profile_name": "Senior Data Scientist",
            "query": "Senior Data Scientist",
            "country": "us",
            "location": "United States",
            "skills": "Python;ML;Deep Learning;NLP;AWS",
            "seniority": "senior",
        },
        # Product Manager profiles
        {
            "profile_name": "Product Manager - Tech",
            "query": "Product Manager Technology",
            "country": "us",
            "location": "United States",
            "skills": "Agile;Scrum;Jira;SQL;Analytics",
            "seniority": "mid",
        },
        {
            "profile_name": "Senior Product Manager",
            "query": "Senior Product Manager",
            "country": "us",
            "location": "United States",
            "skills": "Product Management;Agile;Data Analysis;Strategy",
            "seniority": "senior",
        },
        # DevOps Engineer profiles
        {
            "profile_name": "DevOps Engineer - Cloud",
            "query": "DevOps Engineer AWS",
            "country": "us",
            "location": "United States",
            "skills": "AWS;Docker;Kubernetes;Terraform;CI/CD",
            "seniority": "mid",
        },
        {
            "profile_name": "Senior DevOps Engineer",
            "query": "Senior DevOps Engineer",
            "country": "us",
            "location": "United States",
            "skills": "AWS;Azure;Kubernetes;Terraform;Ansible;Jenkins",
            "seniority": "senior",
        },
    ]

    created_profile_ids = []

    print("Creating test profiles for enrichment analysis...")
    print(f"Total profiles to create: {len(profiles_to_create)}\n")

    for profile_config in profiles_to_create:
        try:
            profile_id = profile_service.create_profile(
                profile_name=profile_config["profile_name"],
                query=profile_config["query"],
                country=profile_config["country"],
                location=profile_config.get("location"),
                skills=profile_config.get("skills"),
                seniority=profile_config.get("seniority"),
                is_active=True,
            )
            created_profile_ids.append(profile_id)
            print(f"✓ Created profile {profile_id}: {profile_config['profile_name']}")
        except Exception as e:
            print(f"✗ Failed to create profile '{profile_config['profile_name']}': {e}")

    print(f"\n✓ Successfully created {len(created_profile_ids)} profile(s)")
    print(f"Profile IDs: {created_profile_ids}")

    return created_profile_ids


if __name__ == "__main__":
    try:
        profile_ids = create_test_profiles()
        sys.exit(0)
    except Exception as e:
        print(f"Error creating test profiles: {e}", file=sys.stderr)
        sys.exit(1)

