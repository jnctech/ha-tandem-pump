"""Tests for scripts/release_tool.py (the logic behind the Pre-release workflow)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "release_tool", Path(__file__).resolve().parent.parent / "scripts" / "release_tool.py"
)
assert _spec and _spec.loader
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)

CHANGELOG = """# Changelog

## [Unreleased] - develop

### Added
- New thing

## [2.3.0-rc.1] - 2026-09-26 (pre-release)

### Added
- First rc thing

## [2.2.1] - 2026-09-09

### Fixed
- Old fix
"""


class TestNextTag:
    def test_first_rc(self):
        assert rt.next_tag("2.4.0", ["v2.3.0", "v2.3.0-rc.1"], "rc") == "v2.4.0-rc.1"

    def test_increments_highest_rc_numerically(self):
        tags = ["v2.3.0-rc.1", "v2.3.0-rc.10", "v2.3.0-rc.2", "v2.3.0-rc1", "v0.2.0-rc1"]
        assert rt.next_tag("2.3.0", tags, "rc") == "v2.3.0-rc.11"

    def test_final(self):
        assert rt.next_tag("2.3.0", ["v2.3.0-rc.3"], "final") == "v2.3.0"

    def test_already_released(self):
        with pytest.raises(rt.ReleaseError, match="already released"):
            rt.next_tag("2.3.0", ["v2.3.0"], "rc")

    @pytest.mark.parametrize("bad", ["2.3", "v2.3.0", "2.3.0-rc.1", "2.3.0 "])
    def test_bad_version(self, bad):
        with pytest.raises(rt.ReleaseError, match="X.Y.Z"):
            rt.next_tag(bad, [], "rc")

    def test_bad_kind(self):
        with pytest.raises(rt.ReleaseError, match="kind"):
            rt.next_tag("2.3.0", [], "beta")


class TestBumpManifest:
    def test_sets_version_keeps_order(self):
        text = json.dumps({"domain": "tandem", "version": "2.2.1", "zeroconf": []}, indent=2) + "\n"
        out = rt.bump_manifest(text, "2.3.0")
        assert json.loads(out)["version"] == "2.3.0"
        assert list(json.loads(out)) == ["domain", "version", "zeroconf"]
        assert out.endswith("}\n")

    def test_no_version_key(self):
        with pytest.raises(rt.ReleaseError, match="version"):
            rt.bump_manifest('{"domain": "tandem"}\n', "2.3.0")

    def test_real_manifest_round_trips(self):
        path = Path(__file__).resolve().parent.parent / "custom_components" / "tandem" / "manifest.json"
        text = path.read_text(encoding="utf-8")
        version = json.loads(text)["version"]
        assert rt.bump_manifest(text, version) == text  # no-op bump leaves the file byte-identical
        bumped = rt.bump_manifest(text, "9.8.7")
        assert [a for a, b in zip(text.splitlines(), bumped.splitlines()) if a != b] == [
            line for line in text.splitlines() if '"version"' in line
        ]


class TestCutChangelog:
    def test_moves_unreleased_into_new_section(self):
        out = rt.cut_changelog(CHANGELOG, "2.3.0-rc.2", "2026-09-27")
        assert (
            "## [Unreleased] - develop\n\n## [2.3.0-rc.2] - 2026-09-27 (pre-release)\n\n### Added\n- New thing" in out
        )
        assert out.count("New thing") == 1
        assert "## [2.3.0-rc.1]" in out and "## [2.2.1]" in out

    def test_final_has_no_prerelease_suffix(self):
        out = rt.cut_changelog(CHANGELOG, "2.3.0", "2026-10-01")
        assert "## [2.3.0] - 2026-10-01\n" in out

    def test_empty_unreleased_refused(self):
        empty = CHANGELOG.replace("### Added\n- New thing\n\n", "", 1)
        with pytest.raises(rt.ReleaseError, match="empty"):
            rt.cut_changelog(empty, "2.3.0-rc.2", "2026-09-27")
        assert "## [2.3.0] - 2026-10-01" in rt.cut_changelog(empty, "2.3.0", "2026-10-01", allow_empty=True)

    def test_duplicate_section_refused(self):
        with pytest.raises(rt.ReleaseError, match="already has"):
            rt.cut_changelog(CHANGELOG, "2.3.0-rc.1", "2026-09-27")

    def test_no_unreleased_heading(self):
        with pytest.raises(rt.ReleaseError, match="Unreleased"):
            rt.cut_changelog("# Changelog\n\n## [1.0.0]\n- x\n", "1.1.0", "2026-09-27")


class TestReleaseNotes:
    def test_rc_notes_are_its_own_section(self):
        assert rt.release_notes(CHANGELOG, "2.3.0-rc.1") == "### Added\n- First rc thing\n"

    def test_final_notes_include_rc_sections(self):
        text = rt.cut_changelog(CHANGELOG, "2.3.0", "2026-10-01")
        notes = rt.release_notes(text, "2.3.0")
        assert notes.startswith("### Added\n- New thing")
        assert "### From 2.3.0-rc.1" in notes and "First rc thing" in notes
        assert "Old fix" not in notes

    def test_missing_section(self):
        with pytest.raises(rt.ReleaseError, match="no notes"):
            rt.release_notes(CHANGELOG, "9.9.9-rc.1")

    def test_repo_changelog_latest_release_has_notes(self):
        """The real CHANGELOG parses, and its newest released section yields notes."""
        import re

        text = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        latest = next(m.group(1) for m in re.finditer(r"^## \[(\d[^\]]*)\]", text, re.MULTILINE))
        assert rt.release_notes(text, latest).strip()


class TestCli:
    def test_next_tag_reads_stdin(self, monkeypatch, capsys):
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO("v2.3.0-rc.1\nv2.2.1\n"))
        assert rt.main(["next-tag", "--version", "2.3.0"]) == 0
        assert capsys.readouterr().out.strip() == "v2.3.0-rc.2"

    def test_error_is_annotation_and_exit_1(self, monkeypatch, capsys):
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO("v2.3.0\n"))
        assert rt.main(["next-tag", "--version", "2.3.0"]) == 1
        assert capsys.readouterr().err.startswith("::error::")
