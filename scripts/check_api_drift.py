"""API contract drift detector for Tandem Source integration.

Parses tandem_api.py and __init__.py for dict key accesses (.get() and []),
then cross-checks them against the known-good API response fixture.

Exit codes:
  0 — no drift detected
  1 — drift detected or fixture/source parse error

Usage:
  python scripts/check_api_drift.py
  python scripts/check_api_drift.py --verbose
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "known_good_api_response.json"

# Source files to scan for API field accesses
SOURCE_FILES = [
    REPO_ROOT / "custom_components" / "carelink" / "tandem_api.py",
    REPO_ROOT / "custom_components" / "carelink" / "__init__.py",
]

# Fixture sections → canonical field lists to check
FIXTURE_SECTIONS = {
    "pump_event_metadata": "_drift_check.pump_event_metadata_fields",
    "last_upload_settings": "_drift_check.last_upload_settings_fields",
    "jwt_claims": "_drift_check.jwt_claim_fields",
}

# Variable name patterns that indicate API response access
# (used to scope which .get() calls are relevant)
API_CONTEXT_PATTERNS = {
    "metadata",
    "pump_metadata",
    "pumper_info",
    "settings",
    "lastUpload",
    "last_upload",
    "claims",
    "login_json",
    "token_json",
}


def extract_string_keys_from_ast(source_path: Path) -> set[str]:
    """Extract all string literal keys from .get() calls and [] subscripts."""
    keys: set[str] = set()

    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        print(f"ERROR: Cannot parse {source_path}: {e}")
        sys.exit(1)

    for node in ast.walk(tree):
        # obj.get("key") or obj.get("key", default)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)

        # obj["key"]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)

    return keys


def load_fixture(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"ERROR: Cannot load fixture {path}: {e}")
        sys.exit(1)


def get_nested(data: dict, dotted_path: str):
    """Resolve a dotted path like '_drift_check.jwt_claim_fields' in a dict."""
    parts = dotted_path.split(".")
    for part in parts:
        data = data[part]
    return data


def check_drift(fixture: dict, code_keys: set[str], verbose: bool) -> list[str]:
    """Cross-check canonical fixture fields against keys found in source code."""
    findings: list[str] = []

    drift_config = fixture.get("_drift_check", {})

    for section_name, dotted_path in [
        ("pump_event_metadata", "pump_event_metadata_fields"),
        ("last_upload_settings", "last_upload_settings_fields"),
        ("jwt_claims", "jwt_claim_fields"),
    ]:
        canonical_fields: list[str] = drift_config.get(dotted_path, [])
        if not canonical_fields:
            findings.append(f"WARNING: No canonical fields defined for '{section_name}' in fixture._drift_check")
            continue

        for field in canonical_fields:
            if field not in code_keys:
                findings.append(
                    f"DRIFT [{section_name}]: field '{field}' is in fixture but NOT referenced in source code "
                    f"— may have been removed from code or renamed"
                )

        if verbose:
            print(f"  {section_name}: {len(canonical_fields)} canonical fields checked")

    return findings


def main() -> int:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("Tandem Source API drift detector")
    print(f"  Fixture: {FIXTURE_PATH.relative_to(REPO_ROOT)}")
    print(f"  Source files: {[str(f.relative_to(REPO_ROOT)) for f in SOURCE_FILES]}")
    print()

    # Load fixture
    fixture = load_fixture(FIXTURE_PATH)

    # Extract all string keys from source files
    all_code_keys: set[str] = set()
    for source_file in SOURCE_FILES:
        if not source_file.exists():
            print(f"WARNING: Source file not found: {source_file.relative_to(REPO_ROOT)}")
            continue
        file_keys = extract_string_keys_from_ast(source_file)
        if verbose:
            print(f"  {source_file.name}: {len(file_keys)} string keys found")
        all_code_keys.update(file_keys)

    if verbose:
        print(f"  Total unique keys across all files: {len(all_code_keys)}")
        print()

    # Run drift checks
    findings = check_drift(fixture, all_code_keys, verbose)

    if findings:
        print("DRIFT DETECTED:")
        for finding in findings:
            print(f"  {finding}")
        print()
        print("Action: Update the fixture at tests/fixtures/known_good_api_response.json")
        print("        to reflect the current API contract, then re-run this check.")
        return 1

    print("OK: No API contract drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
