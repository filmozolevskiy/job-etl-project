"""
Root pytest configuration and shared fixtures.

This file contains configuration and fixtures shared across all test types.
Directory-specific conftest.py files can override or extend these fixtures.
"""

import sys
from pathlib import Path

# Add services directory to Python path for tests
# This allows imports like "from shared import Database" to work in tests
services_path = Path(__file__).parent.parent / "services"
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))
