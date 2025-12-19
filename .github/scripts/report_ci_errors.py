#!/usr/bin/env python3
"""
Script to extract CI errors from workflow runs.

This script extracts error details from failed CI jobs and outputs them
in JSON format for programmatic access by agents.
"""

import argparse
import json
import re
import sys
from typing import Any

import requests
from github import Auth, Github


class CIErrorExtractor:
    """Extract CI errors from workflow runs."""

    def __init__(self, token: str, repo: str, workflow_run_id: int):
        """Initialize the error extractor."""
        self.token = token
        auth = Auth.Token(token)
        self.github = Github(auth=auth)
        self.repo = self.github.get_repo(repo)
        self.workflow_run_id = workflow_run_id

    def _workflow_run_to_dict(self, run) -> dict[str, Any]:
        """Convert a workflow run object to a dictionary."""
        return {
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "conclusion": run.conclusion,
            "head_branch": run.head_branch,
            "head_sha": run.head_sha,
            "html_url": run.html_url,
        }

    def fetch_job_logs(self, job_id: int) -> str:
        """Fetch logs for a specific job."""
        url = f"https://api.github.com/repos/{self.repo.full_name}/actions/jobs/{job_id}/logs"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+raw",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text

    def parse_linting_errors(self, log_content: str) -> list[dict[str, Any]]:
        """Parse ruff linting and formatting errors from logs."""
        errors = []

        # Parse format check failures: "Would reformat: filepath"
        format_pattern = r"Would reformat:\s+(.+?)(?=\n|$)"
        format_matches = re.finditer(format_pattern, log_content, re.MULTILINE)

        for match in format_matches:
            file_path = match.group(1).strip()
            errors.append(
                {
                    "type": "formatting",
                    "file": file_path,
                    "message": "File needs reformatting",
                }
            )

        # Parse GitHub Actions format: ::error file=path,line=1,col=1::code::message
        github_pattern = r"::error\s+file=([^,]+)(?:,line=(\d+),col=(\d+))?::([^:]+)::(.+?)(?=\n|$)"
        github_matches = re.finditer(github_pattern, log_content, re.MULTILINE)

        for match in github_matches:
            groups = match.groups()
            file_path = groups[0]
            line = int(groups[1]) if groups[1] else 0
            col = int(groups[2]) if groups[2] else 0
            code = groups[3].strip()
            message = groups[4].strip()

            errors.append(
                {
                    "type": "linting",
                    "file": file_path,
                    "line": line,
                    "column": col,
                    "code": code,
                    "message": message,
                }
            )

        # Also try standard ruff format: filepath:line:column: code message
        if not errors:
            standard_pattern = r"([^\s:]+):(\d+):(\d+):\s+([A-Z]\d{3})\s+(.+?)(?=\n|$)"
            standard_matches = re.finditer(standard_pattern, log_content, re.MULTILINE)

            for match in standard_matches:
                file_path, line, col, code, message = match.groups()
                errors.append(
                    {
                        "type": "linting",
                        "file": file_path,
                        "line": int(line),
                        "column": int(col),
                        "code": code,
                        "message": message.strip(),
                    }
                )

        return errors

    def parse_test_errors(self, log_content: str) -> list[dict[str, Any]]:
        """Parse pytest test failures from logs."""
        errors = []
        # Look for FAILED test markers
        failed_pattern = r"FAILED\s+(.+?)(?:\n|$)"
        failed_matches = re.finditer(failed_pattern, log_content, re.MULTILINE)

        for match in failed_matches:
            test_name = match.group(1).strip()
            error_section = self._extract_test_error_section(log_content, test_name)
            errors.append(
                {
                    "type": "test",
                    "test_name": test_name,
                    "error_details": error_section[:500],  # Limit length
                }
            )

        # Also look for assertion errors
        assertion_pattern = r"AssertionError:(.+?)(?=\n\s*\n|\nFAILED|\nPASSED|$)"
        assertion_matches = re.finditer(assertion_pattern, log_content, re.DOTALL)

        for match in assertion_matches:
            error_msg = match.group(1).strip()
            errors.append(
                {
                    "type": "test",
                    "test_name": "Assertion Error",
                    "error_details": error_msg[:500],
                }
            )

        return errors

    def parse_dbt_errors(self, log_content: str) -> list[dict[str, Any]]:
        """Parse dbt test failures from logs."""
        errors = []
        # Look for dbt test failure patterns
        failure_pattern = r"Failure in test\s+(.+?)\s*\((.+?)\)\s*\n(.+?)(?=\n\s*compiled code|$)"
        failure_matches = re.finditer(failure_pattern, log_content, re.DOTALL)

        for match in failure_matches:
            test_name = match.group(1).strip()
            test_location = match.group(2).strip()
            error_details = match.group(3).strip()

            errors.append(
                {
                    "type": "dbt",
                    "test_name": test_name,
                    "test_location": test_location,
                    "error_details": error_details[:500],
                }
            )

        # Also look for database errors in dbt
        db_error_pattern = (
            r"Database Error in test\s+(.+?)\s*\((.+?)\)\s*\n(.+?)(?=\n\s*compiled code|$)"
        )
        db_error_matches = re.finditer(db_error_pattern, log_content, re.DOTALL)

        for match in db_error_matches:
            test_name = match.group(1).strip()
            test_location = match.group(2).strip()
            error_details = match.group(3).strip()

            errors.append(
                {
                    "type": "dbt",
                    "test_name": test_name,
                    "test_location": test_location,
                    "error_details": error_details[:500],
                    "error_type": "database_error",
                }
            )

        return errors

    def _extract_test_error_section(self, log_content: str, test_name: str) -> str:
        """Extract error details section for a specific test."""
        test_index = log_content.find(test_name)
        if test_index == -1:
            return ""

        next_test = re.search(
            r"\n(FAILED|PASSED|ERROR|===)", log_content[test_index + len(test_name) :]
        )
        if next_test:
            section = log_content[test_index : test_index + len(test_name) + next_test.start()]
        else:
            section = log_content[test_index : test_index + 1000]

        return section.strip()

    def _parse_generic_errors(self, log_content: str, job_name: str) -> list[dict[str, Any]]:
        """Parse generic error messages when specific parsing fails."""
        errors = []

        # Look for error lines that might contain useful information
        # Common patterns: "Error:", "Failed:", exit codes, etc.
        error_patterns = [
            r"Error:\s*(.+?)(?=\n|$)",
            r"failed\s+(.+?)(?=\n|$)",
            r"Process completed with exit code (\d+)",
        ]

        for pattern in error_patterns:
            matches = re.finditer(pattern, log_content, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                error_msg = match.group(1) if match.lastindex else match.group(0)
                errors.append(
                    {
                        "type": "generic",
                        "job": job_name,
                        "error_details": error_msg.strip()[:200],
                    }
                )

        return errors[:10]  # Limit to first 10 generic errors

    def extract_errors_from_job(self, job_id: int, job_name: str) -> list[dict[str, Any]]:
        """Extract errors from a failed job."""
        if not job_id:
            return []

        try:
            logs = self.fetch_job_logs(job_id)
        except Exception as e:
            print(f"Error fetching logs for job {job_name}: {e}", file=sys.stderr)
            return []

        errors = []

        # Determine job type and parse accordingly
        if "lint" in job_name.lower() or "format" in job_name.lower():
            errors.extend(self.parse_linting_errors(logs))
            # If no errors found, try generic parsing
            if not errors:
                errors.extend(self._parse_generic_errors(logs, job_name))
        elif "test" in job_name.lower() and "dbt" not in job_name.lower():
            errors.extend(self.parse_test_errors(logs))
            if not errors:
                errors.extend(self._parse_generic_errors(logs, job_name))
        elif "dbt" in job_name.lower():
            errors.extend(self.parse_dbt_errors(logs))
            if not errors:
                errors.extend(self._parse_generic_errors(logs, job_name))
        else:
            # For unknown job types, try generic parsing
            errors.extend(self._parse_generic_errors(logs, job_name))

        return errors

    def extract_errors(self) -> dict[str, Any]:
        """Extract all errors from the workflow run."""
        workflow_run = self.repo.get_workflow_run(self.workflow_run_id)
        workflow_run_dict = self._workflow_run_to_dict(workflow_run)

        all_errors = {}
        failed_jobs = []

        # Use PyGithub's jobs property instead of manual API call
        for job in workflow_run.jobs():
            if job.conclusion == "failure":
                job_name = job.name
                failed_jobs.append(job_name)
                errors = self.extract_errors_from_job(job.id, job.name)
                if errors:
                    all_errors[job_name] = errors

        return {
            "workflow_run_id": self.workflow_run_id,
            "workflow_run_url": workflow_run_dict["html_url"],
            "status": workflow_run_dict["status"],
            "conclusion": workflow_run_dict["conclusion"],
            "head_branch": workflow_run_dict["head_branch"],
            "head_sha": workflow_run_dict["head_sha"],
            "failed_jobs": failed_jobs,
            "errors": all_errors,
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Extract CI errors from workflow runs")
    parser.add_argument("--workflow-run-id", type=int, required=True, help="GitHub workflow run ID")
    parser.add_argument("--repo", required=True, help="Repository in format owner/repo")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--output-json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    extractor = CIErrorExtractor(args.token, args.repo, args.workflow_run_id)
    errors_data = extractor.extract_errors()

    if args.output_json:
        print(json.dumps(errors_data, indent=2))
    else:
        # Human-readable output
        print(f"Workflow Run: {errors_data['workflow_run_url']}")
        print(f"Status: {errors_data['status']} ({errors_data['conclusion']})")
        print(f"Branch: {errors_data['head_branch']}")
        print(f"SHA: {errors_data['head_sha']}")
        if errors_data["failed_jobs"]:
            print(f"\nFailed jobs: {', '.join(errors_data['failed_jobs'])}")
            for job_name, errors in errors_data["errors"].items():
                print(f"\n{job_name}: {len(errors)} error(s)")
        else:
            print("\nNo failed jobs found")


if __name__ == "__main__":
    main()
