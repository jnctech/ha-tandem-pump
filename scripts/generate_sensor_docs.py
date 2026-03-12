"""Generate sensor documentation table from const.py definitions.

Parses TANDEM_SENSORS from custom_components/carelink/const.py via AST
and outputs a markdown table grouped by category.

Usage:
  python scripts/generate_sensor_docs.py           # print to stdout
  python scripts/generate_sensor_docs.py --check   # compare against README, exit 1 if stale
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONST_PATH = REPO_ROOT / "custom_components" / "carelink" / "const.py"
README_PATH = REPO_ROOT / "README.md"

TABLE_START_MARKER = "<!-- SENSOR_TABLE_START -->"
TABLE_END_MARKER = "<!-- SENSOR_TABLE_END -->"


def extract_string_constants(tree: ast.Module) -> dict[str, str]:
    """Extract all top-level NAME = 'string' assignments from an AST."""
    constants: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.targets[0].id] = node.value.value
    return constants


def extract_sensor_descriptions(const_path: Path) -> list[dict]:
    """Parse TANDEM_SENSORS tuple from const.py using AST."""
    source = const_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_constants = extract_string_constants(tree)

    sensors: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "TANDEM_SENSORS":
                if isinstance(node.value, ast.Tuple):
                    for elt in node.value.elts:
                        sensor = _parse_sensor_description(elt, string_constants)
                        if sensor:
                            sensors.append(sensor)
    return sensors


def _parse_sensor_description(node: ast.expr, constants: dict[str, str]) -> dict | None:
    if not isinstance(node, ast.Call):
        return None
    sensor: dict = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        value = _eval_value(keyword.value, constants)
        sensor[keyword.arg] = value
    return sensor if "key" in sensor else None


def _eval_value(node: ast.expr, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant):
        return str(node.value) if node.value is not None else None
    if isinstance(node, ast.Name):
        if node.id in constants:
            return constants[node.id]
        if node.id in ("None", "UNAVAILABLE"):
            return None
        return None
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _category_from_key(key: str) -> str:
    if not key:
        return "Other"
    k = key.lower()
    if "glucose" in k or "_sg_" in k or "cgm" in k or "gmi" in k:
        return "Glucose / CGM"
    if "bolus" in k or "insulin" in k or "iob" in k or "basal" in k:
        return "Insulin Delivery"
    if "carb" in k:
        return "Nutrition"
    if "time_in" in k or "time_below" in k or "time_above" in k or "cgm_usage" in k:
        return "Statistics"
    if "control_iq" in k or "activity_mode" in k or "suspended" in k or "suspend_reason" in k:
        return "Pump Control"
    if "cartridge" in k or "site" in k or "tubing" in k:
        return "Consumables"
    if "upload" in k or "update" in k or "software" in k or "serial" in k or "model" in k:
        return "Device Info"
    if (
        "profile" in k
        or "weight" in k
        or "tdi" in k
        or "max_bolus" in k
        or "alert" in k
        or "threshold" in k
        or "limit" in k
    ):
        return "Settings"
    return "Other"


def generate_table(sensors: list[dict]) -> str:
    category_order = [
        "Glucose / CGM",
        "Insulin Delivery",
        "Nutrition",
        "Statistics",
        "Pump Control",
        "Consumables",
        "Device Info",
        "Settings",
        "Other",
    ]

    groups: dict[str, list[dict]] = {}
    for sensor in sensors:
        cat = _category_from_key(sensor.get("key", ""))
        groups.setdefault(cat, []).append(sensor)

    lines: list[str] = []
    lines.append("| Entity ID | Name | Unit | Device Class | State Class | Icon |")
    lines.append("|-----------|------|------|--------------|-------------|------|")

    for category in category_order:
        if category not in groups:
            continue
        lines.append(f"| **{category}** | | | | | |")
        for s in groups[category]:
            key = s.get("key") or ""
            name = s.get("name") or ""
            unit = s.get("native_unit_of_measurement") or "-"
            device_class = s.get("device_class") or "-"
            state_class = s.get("state_class") or "-"
            icon = s.get("icon") or "-"
            entity_id = f"`sensor.{key}`" if key else ""
            lines.append(f"| {entity_id} | {name} | {unit} | {device_class} | {state_class} | {icon} |")

    return "\n".join(lines)


def check_readme(generated_table: str) -> bool:
    if not README_PATH.exists():
        print("WARNING: README.md not found -- skipping check")
        return True
    readme = README_PATH.read_text(encoding="utf-8")
    if TABLE_START_MARKER not in readme or TABLE_END_MARKER not in readme:
        print(
            f"WARNING: README.md does not contain sensor table markers "
            f"({TABLE_START_MARKER} / {TABLE_END_MARKER})\n"
            "Add the markers to README.md to enable automated sensor table checking."
        )
        return True
    pattern = re.compile(
        re.escape(TABLE_START_MARKER) + r"(.*?)" + re.escape(TABLE_END_MARKER),
        re.DOTALL,
    )
    match = pattern.search(readme)
    if not match:
        return False
    existing = match.group(1).strip()
    return existing == generated_table.strip()


def main() -> int:
    check_mode = "--check" in sys.argv

    if not CONST_PATH.exists():
        print(f"ERROR: {CONST_PATH} not found")
        return 1

    sensors = extract_sensor_descriptions(CONST_PATH)
    if not sensors:
        print("ERROR: No sensors extracted from TANDEM_SENSORS -- check const.py")
        return 1

    table = generate_table(sensors)

    if check_mode:
        if check_readme(table):
            print(f"OK: README.md sensor table is up-to-date ({len(sensors)} sensors).")
            return 0
        else:
            print("STALE: README.md sensor table is out of date.")
            print("Run: python scripts/generate_sensor_docs.py > sensor_table.md")
            print("Then update the section between the markers in README.md.")
            return 1
    else:
        print(table)
        print(f"\n# {len(sensors)} Tandem sensors extracted from const.py", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
