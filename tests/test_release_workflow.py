from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import build
import pytest


def test_package_version_matches_release_log() -> None:
    version = build.read_project_version(Path("pyproject.toml"))

    assert build.release_log_has_entry(Path("release-log.md"), version)


def test_validate_tag_accepts_matching_tag() -> None:
    build.validate_tag("1.2.3", "v1.2.3")


def test_validate_tag_rejects_mismatched_tag() -> None:
    with pytest.raises(RuntimeError, match="does not match"):
        build.validate_tag("1.2.3", "v1.2.2")


def test_release_notes_extracts_version_section(tmp_path: Path) -> None:
    log_path = tmp_path / "release-log.md"
    log_path.write_text(
        "# Release Log\n\n## HEAD\n\n- Draft\n\n## 1.2.3\n\n- Final note\n\n## 1.2.2\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/release-notes.py", "v1.2.3", str(log_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "- Final note\n"
