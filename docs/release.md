# PyPI Release Guide

This project uses a Python release helper script.

## Prerequisites

- A PyPI account
- A PyPI API token
- The token stored in an environment variable:

```
export PYPI_TOKEN="pypi-..."
```

## Release steps

1) Keep `release-log.md` updated. Use the `HEAD` section for unreleased changes.
2) When preparing a release, move the `HEAD` notes into a versioned section.
3) Update the version in `pyproject.toml`.
4) Add an entry for the version in `release-log.md`.
5) Run tests and type checks:

```
uv run --extra dev tox
```

6) Build distribution artifacts:

```
uv build
```

7) Publish to PyPI:

```
uv publish --token "$PYPI_TOKEN"
```

8) Tag the release in git:

```
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push --tags
```

## One-command release

If you already set `PYPI_TOKEN`, you can run:

```
python ./build.py --release
```

This will run tests, build, publish, and tag the current version as `vX.Y.Z`. If the tag already exists, it will be updated and force-pushed. It will also error if the release log entry is missing.
The script also fails if the git worktree is dirty, unless you pass `--ignore-git-warnings`.
