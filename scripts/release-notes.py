#!/usr/bin/env python3
"""Print GitHub Release notes for a version in release-log.md."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def release_notes(tag: str, log_path: Path) -> str:
    version = tag.removeprefix("v")
    if not log_path.exists():
        return f"Release {tag}"

    text = log_path.read_text(encoding="utf-8")
    match = re.search(rf"^##\s+{re.escape(version)}\s*$", text, re.MULTILINE)
    if not match:
        return f"Release {tag}"
    start = match.end()
    next_header = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_header.start() if next_header else len(text)
    notes = text[start:end].strip()
    return notes or f"Release {tag}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print release notes from release-log.md.")
    parser.add_argument("tag", help="Release tag, for example v0.1.0")
    parser.add_argument(
        "log_path",
        nargs="?",
        default=Path("release-log.md"),
        type=Path,
        help="Path to the release log.",
    )
    args = parser.parse_args()
    print(release_notes(args.tag, args.log_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
