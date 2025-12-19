#!/usr/bin/env python3
"""
Script to query CI status and errors.

This script allows agents to check CI status and extract error details
"""

import argparse
import json
import sys
from typing import Any

import requests
from github import Auth, Github


class CIStatusQuery:
    """Query CI status and errors from GitHub workflow runs."""

    def __init__(self, token: str, repo: str):
        """Initialize the status query."""
        self.token = token
        auth = Auth.Token(token)
        self.github = Github(auth=auth)
        self.repo = self.github.get_repo(repo)

    def get_workflow_run(self, run_id: int) -> dict[str, Any] | None:
        """Get workflow run details by ID."""
        url = f"https://api.github.com/repos/{self.repo.full_name}/actions/runs/{run_id}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            run_data = response.json()
            return {
                "id": run_data["id"],
                "name": run_data["name"],
                "status": run_data["status"],
                "conclusion": run_data["conclusion"],
                "head_branch": run_data["head_branch"],
                "head_sha": run_data["head_sha"],
                "html_url": run_data["html_url"],
                "created_at": run_data["created_at"],
                "updated_at": run_data["updated_at"],
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching workflow run: {e}", file=sys.stderr)
            return None

    def get_latest_workflow_run(self, branch: str = None) -> dict[str, Any] | None:
        """Get the latest workflow run, optionally filtered by branch."""
        workflow_runs = self.repo.get_workflow_runs()

        if branch:
            # Filter by branch
            for run in workflow_runs:
                if run.head_branch == branch:
                    return {
                        "id": run.id,
                        "name": run.name,
                        "status": run.status,
                        "conclusion": run.conclusion,
                        "head_branch": run.head_branch,
                        "head_sha": run.head_sha,
                        "html_url": run.html_url,
                        "created_at": run.created_at.isoformat() if run.created_at else None,
                        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
                    }
        else:
            # Get the most recent run
            latest_run = workflow_runs[0] if workflow_runs.totalCount > 0 else None
            if latest_run:
                return {
                    "id": latest_run.id,
                    "name": latest_run.name,
                    "status": latest_run.status,
                    "conclusion": latest_run.conclusion,
                    "head_branch": latest_run.head_branch,
                    "head_sha": latest_run.head_sha,
                    "html_url": latest_run.html_url,
                    "created_at": latest_run.created_at.isoformat()
                    if latest_run.created_at
                    else None,
                    "updated_at": latest_run.updated_at.isoformat()
                    if latest_run.updated_at
                    else None,
                }

        return None

    def get_workflow_run_jobs(self, run_id: int) -> list[dict[str, Any]]:
        """Get jobs for a workflow run."""
        url = f"https://api.github.com/repos/{self.repo.full_name}/actions/runs/{run_id}/jobs"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            jobs_data = response.json()
            return [
                {
                    "id": job["id"],
                    "name": job["name"],
                    "status": job["status"],
                    "conclusion": job["conclusion"],
                    "html_url": job["html_url"],
                    "started_at": job.get("started_at"),
                    "completed_at": job.get("completed_at"),
                }
                for job in jobs_data.get("jobs", [])
            ]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching jobs: {e}", file=sys.stderr)
            return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Query CI status and errors directly from GitHub")
    parser.add_argument("--repo", required=True, help="Repository in format owner/repo")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--branch", help="Branch name to filter by")
    parser.add_argument("--run-id", type=int, help="Specific workflow run ID")
    parser.add_argument("--latest", action="store_true", help="Get latest workflow run status")
    parser.add_argument("--jobs", action="store_true", help="Include job details")
    parser.add_argument("--output-json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    query = CIStatusQuery(args.token, args.repo)
    result = {}

    if args.run_id:
        run = query.get_workflow_run(args.run_id)
        if run:
            result["workflow_run"] = run
            if args.jobs:
                result["jobs"] = query.get_workflow_run_jobs(args.run_id)
        else:
            print("Workflow run not found", file=sys.stderr)
            sys.exit(1)
    elif args.latest:
        run = query.get_latest_workflow_run(args.branch)
        if run:
            result["workflow_run"] = run
            if args.jobs:
                result["jobs"] = query.get_workflow_run_jobs(run["id"])
        else:
            print("No workflow runs found", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        run = result["workflow_run"]
        print(f"Workflow Run: {run['name']} #{run['id']}")
        print(f"Status: {run['status']}")
        print(f"Conclusion: {run['conclusion']}")
        print(f"Branch: {run['head_branch']}")
        print(f"SHA: {run['head_sha']}")
        print(f"URL: {run['html_url']}")

        if args.jobs and "jobs" in result:
            print(f"\nJobs ({len(result['jobs'])}):")
            for job in result["jobs"]:
                print(f"  - {job['name']}: {job['status']} ({job['conclusion']})")


if __name__ == "__main__":
    main()
