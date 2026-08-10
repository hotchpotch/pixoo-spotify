from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_toml() -> Any:
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib
    import tomli

    return tomli


def read_project_version(pyproject_path: Path) -> str:
    data = _load_toml().loads(pyproject_path.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version", "")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("project.version is missing in pyproject.toml")
    return version.strip()


def release_log_section(log_path: Path, version: str) -> str:
    if not log_path.exists():
        return ""
    text = log_path.read_text(encoding="utf-8")
    header_pattern = re.compile(rf"^##\s+{re.escape(version)}\s*$", re.MULTILINE)
    match = header_pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_header = re.compile(r"^##\s+", re.MULTILINE).search(text, start)
    end = next_header.start() if next_header else len(text)
    return text[start:end].strip()


def release_log_has_entry(log_path: Path, version: str) -> bool:
    return any(
        line.strip() and not line.lstrip().startswith("#")
        for line in release_log_section(log_path, version).splitlines()
    )


def validate_tag(version: str, tag: str | None) -> None:
    if tag is not None and tag != f"v{version}":
        raise RuntimeError(f"Tag {tag!r} does not match package version {version!r}.")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def clean_dist(dist_path: Path) -> None:
    if dist_path.exists():
        shutil.rmtree(dist_path)


def build_publish_files(dist_path: Path, version: str) -> list[Path]:
    return sorted(dist_path.glob(f"pixoo_spotify-{version}*"))


def ensure_clean_worktree(ignore_warnings: bool) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    changes = result.stdout.strip()
    if changes and not ignore_warnings:
        raise RuntimeError(
            "Uncommitted changes detected. Commit or stash them before building a release, "
            "or rerun with --ignore-git-warnings.\n\n"
            f"{changes}"
        )


def ensure_lock_up_to_date() -> None:
    result = subprocess.run(
        ["uv", "lock", "--check"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        output = result.stdout.strip()
        message = "uv.lock is out of date. Run `uv lock` and commit uv.lock before building."
        if output:
            message = f"{message}\n\n{output}"
        raise RuntimeError(message)


def build_release(
    pyproject_path: Path,
    log_path: Path,
    *,
    tag: str | None,
    ignore_git_warnings: bool,
) -> list[Path]:
    ensure_clean_worktree(ignore_git_warnings)
    ensure_lock_up_to_date()
    version = read_project_version(pyproject_path)
    validate_tag(version, tag)
    if not release_log_has_entry(log_path, version):
        raise RuntimeError(
            f"Release log entry for version {version} is missing or empty in {log_path}."
        )

    run(["uv", "run", "--extra", "dev", "tox"])
    dist_path = Path("dist")
    clean_dist(dist_path)
    run(["uv", "build", "--no-sources"])
    publish_files = build_publish_files(dist_path, version)
    if not publish_files:
        raise RuntimeError(f"No artifacts found for version {version} in {dist_path}.")
    run(["uv", "run", "--extra", "dev", "twine", "check", "--strict", *map(str, publish_files)])

    wheels = [path for path in publish_files if path.suffix == ".whl"]
    if len(wheels) != 1:
        raise RuntimeError(f"Expected exactly one wheel for {version}, found {len(wheels)}.")
    run(
        [
            "uv",
            "run",
            "--with",
            str(wheels[0]),
            "--no-project",
            "pixoo-spotify",
            "--version",
        ]
    )
    return publish_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and build pixoo-spotify release artifacts."
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run validation, build distributions, check metadata, and smoke test the wheel.",
    )
    parser.add_argument("--tag", help="Optional release tag to validate, for example v0.1.0.")
    parser.add_argument(
        "--print-version", action="store_true", help="Print project.version and exit."
    )
    parser.add_argument(
        "--ignore-git-warnings",
        action="store_true",
        help="Allow building with uncommitted changes (useful while developing the workflow).",
    )
    args = parser.parse_args()

    pyproject_path = Path("pyproject.toml")
    if args.print_version:
        print(read_project_version(pyproject_path))
        return 0
    if args.build:
        artifacts = build_release(
            pyproject_path,
            Path("release-log.md"),
            tag=args.tag,
            ignore_git_warnings=args.ignore_git_warnings,
        )
        print("Built and verified release artifacts:")
        for artifact in artifacts:
            print(f"  {artifact}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
