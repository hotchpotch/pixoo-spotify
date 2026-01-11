# PyPI Release Guide

This project uses uv for building and publishing.

## Prerequisites

- A PyPI account
- A PyPI API token
- The token stored in an environment variable:

```
export PYPI_TOKEN="pypi-..."
```

## Release steps

1) Update the version in `pyproject.toml`.
2) Run tests and type checks:

```
uv run --extra dev tox
```

3) Build distribution artifacts:

```
uv build
```

4) Publish to PyPI:

```
uv publish --token "$PYPI_TOKEN"
```

5) Tag the release in git:

```
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push --tags
```

## One-command release

If you already set `PYPI_TOKEN`, you can run:

```
make release
```
