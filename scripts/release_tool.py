"""Release helpers used by the Pre-release workflow (.github/workflows/prerelease.yml).

Standard library only, so it runs on a bare Actions runner. Every command is a pure
function over text, unit-tested in tests/test_release_tool.py, so the release automation
is validated by CI rather than by hand.

Usage:
  git tag -l | python scripts/release_tool.py next-tag --version 2.3.0 --kind rc
  python scripts/release_tool.py bump --version 2.3.0
  python scripts/release_tool.py cut-changelog --tag-version 2.3.0-rc.2 --date 2026-09-27
  python scripts/release_tool.py notes --tag-version 2.3.0-rc.2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MANIFEST = Path("custom_components/tandem/manifest.json")
CHANGELOG = Path("CHANGELOG.md")
TAG_PREFIX = "v"
RC_SEPARATOR = "-rc."

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_UNRELEASED_RE = re.compile(r"^##\s*\[Unreleased\].*$", re.IGNORECASE)
_SECTION_RE = re.compile(r"^##\s")


class ReleaseError(Exception):
    """A release precondition failed; the message is shown to the user."""


def validate_version(version: str) -> str:
    """Return ``version`` if it is a plain X.Y.Z, else raise."""
    if not _VERSION_RE.match(version):
        raise ReleaseError(f"version must be X.Y.Z (got {version!r})")
    return version


def next_tag(version: str, existing_tags: list[str], kind: str) -> str:
    """Next tag for ``version``: vX.Y.Z-rc.<N+1> for an rc, vX.Y.Z for a final.

    Raises if the final tag already exists, or if an rc is requested for a version
    that has already had its final release.
    """
    validate_version(version)
    final = f"{TAG_PREFIX}{version}"
    tags = {t.strip() for t in existing_tags if t.strip()}
    if final in tags:
        raise ReleaseError(f"{final} is already released")
    if kind == "final":
        return final
    if kind != "rc":
        raise ReleaseError(f"kind must be rc or final (got {kind!r})")
    rc_re = re.compile(rf"^{re.escape(final + RC_SEPARATOR)}(\d+)$")
    numbers = [int(m.group(1)) for t in tags if (m := rc_re.match(t))]
    return f"{final}{RC_SEPARATOR}{max(numbers, default=0) + 1}"


def bump_manifest(text: str, version: str) -> str:
    """Return manifest JSON text with ``version`` set, changing nothing else in the file.

    Edits the value in place (the manifest keeps short lists on one line, which a JSON
    re-dump would reflow), then re-parses to prove the result is valid JSON.
    """
    validate_version(version)
    new, count = re.subn(r'("version"\s*:\s*)"[^"]*"', rf'\g<1>"{version}"', text, count=1)
    if count != 1 or json.loads(new).get("version") != version:
        raise ReleaseError('manifest has no top-level "version" string')
    return new


def cut_changelog(text: str, tag_version: str, date: str, *, allow_empty: bool = False) -> str:
    """Start a ``## [tag_version] - date`` section holding everything under [Unreleased].

    The [Unreleased] heading stays (empty) above the new section. Raises when there is
    no [Unreleased] heading, when a section for ``tag_version`` already exists, or when
    [Unreleased] is empty (nothing to release) unless ``allow_empty``.
    """
    lines = text.splitlines()
    idx = next((i for i, line in enumerate(lines) if _UNRELEASED_RE.match(line)), None)
    if idx is None:
        raise ReleaseError("CHANGELOG has no '## [Unreleased]' heading")
    if any(re.match(rf"^##\s*\[{re.escape(tag_version)}\]", line) for line in lines):
        raise ReleaseError(f"CHANGELOG already has a [{tag_version}] section")
    end = next((i for i in range(idx + 1, len(lines)) if _SECTION_RE.match(lines[i])), len(lines))
    body = "\n".join(lines[idx + 1 : end]).strip()
    if not body and not allow_empty:
        raise ReleaseError("CHANGELOG [Unreleased] is empty - nothing to release")
    suffix = " (pre-release)" if "-" in tag_version else ""
    new = [*lines[: idx + 1], "", f"## [{tag_version}] - {date}{suffix}", ""]
    if body:
        new += [body, ""]
    new += lines[end:]
    return "\n".join(new).rstrip("\n") + "\n"


def release_notes(text: str, tag_version: str) -> str:
    """Release notes for ``tag_version`` from the CHANGELOG.

    An rc gets its own section. A final release gets its own section followed by every
    ``[X.Y.Z-rc.N]`` section of the same version, so the notes cover the whole cycle.
    """
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    heading: str | None = None
    buf: list[str] = []
    for line in [*lines, "## [__end__]"]:
        if _SECTION_RE.match(line):
            if heading is not None:
                sections.append((heading, "\n".join(buf).strip()))
            m = re.match(r"^##\s*\[([^\]]+)\]", line)
            heading, buf = (m.group(1) if m else None), []
        elif heading is not None:
            buf.append(line)
    core = tag_version.split("-", 1)[0]
    if tag_version != core:  # release candidate
        wanted = [b for h, b in sections if h == tag_version]
    else:
        wanted = [b for h, b in sections if h == core]
        wanted += [f"### From {h}\n\n{b}" for h, b in sections if h.startswith(f"{core}-") and b]
    notes = "\n\n".join(b for b in wanted if b).strip()
    if not notes:
        raise ReleaseError(f"CHANGELOG has no notes for [{tag_version}]")
    return notes + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next-tag", help="next tag; existing tags are read from stdin")
    p.add_argument("--version", required=True)
    p.add_argument("--kind", choices=["rc", "final"], default="rc")
    p = sub.add_parser("bump", help="set the manifest version")
    p.add_argument("--version", required=True)
    p = sub.add_parser("cut-changelog", help="move [Unreleased] into a new release section")
    p.add_argument("--tag-version", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--allow-empty", action="store_true")
    p = sub.add_parser("notes", help="print release notes from the CHANGELOG")
    p.add_argument("--tag-version", required=True)
    args = parser.parse_args(argv)

    try:
        if args.cmd == "next-tag":
            print(next_tag(args.version, sys.stdin.read().splitlines(), args.kind))
        elif args.cmd == "bump":
            MANIFEST.write_text(bump_manifest(MANIFEST.read_text(encoding="utf-8"), args.version), encoding="utf-8")
        elif args.cmd == "cut-changelog":
            text = CHANGELOG.read_text(encoding="utf-8")
            new = cut_changelog(text, args.tag_version, args.date, allow_empty=args.allow_empty)
            CHANGELOG.write_text(new, encoding="utf-8")
        elif args.cmd == "notes":
            sys.stdout.write(release_notes(CHANGELOG.read_text(encoding="utf-8"), args.tag_version))
    except ReleaseError as err:
        print(f"::error::{err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
