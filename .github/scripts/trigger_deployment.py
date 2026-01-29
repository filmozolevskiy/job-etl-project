#!/usr/bin/env python3
"""Trigger the deployment workflow manually."""

import os
import sys

import requests


def trigger_deployment():
    """Trigger the deployment workflow via GitHub API."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    owner = "filmozolevskiy"
    repo = "job-etl-project"
    workflow_file = "deploy-production.yml"

    url = (
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    payload = {"ref": "main"}

    print(f"Triggering deployment workflow: {workflow_file}")
    print(f"Repository: {owner}/{repo}")
    print("Branch: main")

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 204:
            print("[SUCCESS] Deployment workflow triggered successfully!")
            print(
                f"Monitor at: https://github.com/{owner}/{repo}/actions/workflows/{workflow_file}"
            )
            return 0
        else:
            print(f"[ERROR] Failed to trigger workflow: {response.status_code}", file=sys.stderr)
            print(f"Response: {response.text}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"[ERROR] Error triggering workflow: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(trigger_deployment())
