"""
Helper functions for integration tests.
"""

import os
import shutil
import subprocess
from pathlib import Path


def check_dbt_available() -> bool:
    """Check if dbt is available in PATH or as Python module."""
    # Check if dbt is in PATH
    if shutil.which("dbt") is not None:
        return True

    # Check if dbt can be imported (installed but not in PATH)
    try:
        # Also check if dbt CLI is accessible
        import dbt.cli.main  # noqa: F401

        return True
    except ImportError:
        return False


def run_dbt_command(
    dbt_project_dir: Path,
    command: list[str],
    env: dict | None = None,
    connection_string: str | None = None,
) -> subprocess.CompletedProcess | None:
    """
    Run a dbt command safely.

    Args:
        dbt_project_dir: Path to dbt project directory
        command: dbt command as list (e.g., ["run", "--select", "staging.jsearch_job_postings"])
        env: Optional environment variables dict
        connection_string: Optional PostgreSQL connection string to extract DB connection info from

    Returns:
        CompletedProcess if successful, None if dbt is not available
    """
    if not check_dbt_available():
        return None

    if env is None:
        env = {}
    else:
        env = {**os.environ, **env}

    # If connection_string is provided, extract DB info and set env vars for dbt
    if connection_string:
        # Parse connection string: postgresql://user:password@host:port/dbname
        import urllib.parse

        parsed = urllib.parse.urlparse(connection_string)
        env["POSTGRES_HOST"] = parsed.hostname or "localhost"
        env["POSTGRES_PORT"] = str(parsed.port or 5432)
        env["POSTGRES_USER"] = parsed.username or "postgres"
        env["POSTGRES_PASSWORD"] = parsed.password or "postgres"
        env["POSTGRES_DB"] = parsed.path.lstrip("/") or "job_search_test"

    # Try to use dbt from PATH first
    dbt_cmd_path = shutil.which("dbt")
    if dbt_cmd_path is None:
        # If not in PATH, try to find it in Python Scripts directory
        import sysconfig

        scripts_dir = sysconfig.get_path("scripts")
        dbt_exe = os.path.join(scripts_dir, "dbt.exe")
        if os.path.exists(dbt_exe):
            dbt_cmd_path = dbt_exe
        else:
            # Last resort: try to use python -m dbt (may not work, but worth trying)
            import sys

            dbt_cmd_path = [sys.executable, "-m", "dbt"]
            full_command = [*dbt_cmd_path, *command, "--profiles-dir", str(dbt_project_dir)]
            try:
                result = subprocess.run(
                    full_command,
                    cwd=dbt_project_dir,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                return result
            except Exception:
                return None

    # Use the found dbt command
    # Ensure dbt_cmd_path is a string (not list) for single command
    if isinstance(dbt_cmd_path, list):
        full_command = [*dbt_cmd_path, *command, "--profiles-dir", str(dbt_project_dir)]
    else:
        full_command = [dbt_cmd_path, *command, "--profiles-dir", str(dbt_project_dir)]

    result = subprocess.run(
        full_command,
        cwd=str(dbt_project_dir),  # Ensure it's a string path for subprocess
        capture_output=True,
        text=True,
        env=env,
    )

    return result
