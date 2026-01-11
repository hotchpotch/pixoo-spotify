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

1) Update the version in `pyproject.toml`.
2) Add an entry for the version in `release-log.md`.
3) Run tests and type checks:

```
uv run --extra dev tox
```

4) Build distribution artifacts:

```
uv build
```

5) Publish to PyPI:

```
uv publish --token "$PYPI_TOKEN"
```

6) Tag the release in git:

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
