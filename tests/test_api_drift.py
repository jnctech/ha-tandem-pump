"""API contract drift detection test.

Runs check_api_drift.py as a pytest test so drift is caught in CI.
No network calls — operates entirely on source code and fixture files.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_api_drift.py"


def test_no_api_contract_drift():
    """Fixture fields must be referenced in source code — detects API drift."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "API contract drift detected.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        "Update tests/fixtures/known_good_api_response.json to match current API contract."
    )
