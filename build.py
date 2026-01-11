from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def _load_toml() -> object:
    try:
        import tomllib  # type: ignore[attr-defined]

        return tomllib
    except ModuleNotFoundError:
        import tomli  # type: ignore[import-not-found]

        return tomli


def read_project_version(pyproject_path: Path) -> str:
    toml = _load_toml()
    data = toml.loads(pyproject_path.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version", "")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("project.version is missing in pyproject.toml")
    return version.strip()


def release_log_has_entry(log_path: Path, version: str) -> bool:
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8")
    header_pattern = re.compile(rf"^##\s+{re.escape(version)}\s*$", re.MULTILINE)
    match = header_pattern.search(text)
    if not match:
        return False
    start = match.end()
    next_header = re.compile(r"^##\s+", re.MULTILINE).search(text, start)
    end = next_header.start() if next_header else len(text)
    body = text[start:end]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def release(pyproject_path: Path, log_path: Path) -> None:
    version = read_project_version(pyproject_path)
    if not release_log_has_entry(log_path, version):
        raise RuntimeError(
            f"Release log entry for version {version} is missing or empty in {log_path}."
        )
    token = os.environ.get("PYPI_TOKEN")
    if not token:
        raise RuntimeError("PYPI_TOKEN is not set.")
    run(["uv", "run", "--extra", "dev", "tox"])
    run(["uv", "build"])
    run(["uv", "publish", "--token", token])
    tag = f"v{version}"
    run(["git", "tag", "-f", "-a", tag, "-m", f"Release {tag}"])
    run(["git", "push", "-f", "origin", tag])


def main() -> int:
    parser = argparse.ArgumentParser(description="Release helper for pixoo-spotify.")
    parser.add_argument(
        "--release",
        action="store_true",
        help="Run tests, build, publish, and tag the current version.",
    )
    args = parser.parse_args()
    if args.release:
        release(Path("pyproject.toml"), Path("release-log.md"))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
