"""Changelog helpers for the Makefile release targets.

Usage:
  python3 scripts/release.py promote <version>  # move [Unreleased] under [<version>]
  python3 scripts/release.py check <version>    # fail unless CHANGELOG has [<version>]
  python3 scripts/release.py notes <version>    # print the section body
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
HEADING = re.compile(
    r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?$", re.MULTILINE
)


def _sections(text: str) -> list[tuple[str, int, int, int]]:
    """(version, heading_start, body_start, body_end) for each section."""
    headings = list(HEADING.finditer(text))
    out: list[tuple[str, int, int, int]] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        out.append((match.group("version"), match.start(), match.end(), end))
    return out


def section_notes(text: str, version: str) -> str:
    for name, _, body_start, body_end in _sections(text):
        if name == version:
            return text[body_start:body_end].strip()
    raise SystemExit(f"no CHANGELOG section for {version}")


def promote_unreleased(text: str, version: str, date: str) -> str:
    for name, heading_start, body_start, body_end in _sections(text):
        if name == "Unreleased":
            body = text[body_start:body_end].strip()
            if not body:
                raise SystemExit(
                    "the [Unreleased] section is empty; add entries before releasing"
                )
            replacement = f"## [Unreleased]\n\n## [{version}] - {date}\n\n{body}\n\n"
            return text[:heading_start] + replacement + text[body_end:]
    raise SystemExit("no [Unreleased] section in CHANGELOG.md")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    command, version = argv
    text = CHANGELOG.read_text(encoding="utf-8")
    if command == "promote":
        today = dt.date.today().isoformat()
        CHANGELOG.write_text(promote_unreleased(text, version, today), encoding="utf-8")
    elif command == "check":
        section_notes(text, version)
    elif command == "notes":
        print(section_notes(text, version))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
