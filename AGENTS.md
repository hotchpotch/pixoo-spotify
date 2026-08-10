# AGENTS.md

This file gives coding agents and contributors the project-specific context needed to work on
pixoo-spotify. Keep it portable: do not add absolute paths, personal tool configuration, secrets,
or instructions that only apply to one contributor's machine.

## Project overview

pixoo-spotify is a Python CLI that renders the current Spotify track as a 64x64 GIF, serves it
from a lightweight local HTTP server, and instructs a Divoom Pixoo64 to fetch it. The host and the
Pixoo must have bidirectional network connectivity.

- Python 3.10 or newer
- Package and environment management: `uv`
- CLI: Typer and Rich
- Configuration and payload models: Pydantic
- Async network client: HTTPX
- Spotify authorization: Authorization Code with PKCE; no client secret
- GIF server: `http.server.ThreadingHTTPServer`

## Repository map

- `pixoo_spotify/`: application package
- `tests/`: unit, integration, CLI, workflow, and opt-in Spotify E2E tests
- `docs/`: detailed specifications and release documentation
- `.github/workflows/ci.yaml`: pull-request and `main` validation
- `.github/workflows/release.yml`: build, Trusted Publishing, tag, and GitHub Release automation
- `build.py`: local distribution and release validation
- `release-log.md`: user-visible release notes

## Development setup

```bash
uv sync --extra dev
uv run --extra dev tox
```

Use `uv add <package>` for runtime dependencies and `uv add --optional dev <package>` for
development tools. Commit `uv.lock` whenever it changes. Do not edit dependency lists without
updating the lock file.

## Implementation conventions

- Prefer async/await for network and other I/O work.
- Retain Pydantic models for configuration and external data payloads.
- Add CLI behavior through Typer. Foreground `run` mode should use the compact Rich UI in
  `pixoo_spotify/ui.py`; unattended usage must remain usable with plain text output.
- Keep the embedded HTTP server lightweight. It serves the generated GIF at `/spotify_gif`, and
  Pixoo URLs use a cache-busting query string.
- Keep server and headless operation first-class. Errors that require user action, especially an
  expired Spotify session, must be explicit, actionable, and result in a non-zero exit status.
- Preserve PKCE authentication and never require or store a Spotify client secret.
- Do not log tokens, authorization codes, Client IDs, or the contents of `.env` files.

### Configuration behavior

- The global `--config-path` option overrides the platform configuration directory.
- `auth` and `run` resolve the Spotify Client ID in this order: CLI option, TOML/JSON config,
  process environment, `.env` in the working directory, then the platform config cache.
- Read `.env` only as a configuration source; do not inject its values into the process environment.
- The default redirect URI is `http://127.0.0.1:8888/callback`.
- Headless authorization uses `--no-open-browser` and accepts the pasted redirect URL.
- Fonts and the default GIF output live below the platform configuration directory. The packaged
  Misaki Gothic font is the fallback when no user font is installed.
- Demo and manual GIF commands may continue to use the repository-local `output/` directory.

## Testing

Develop changes test-first when practical. Add regression coverage for bug fixes and cover both
success and actionable failure paths for CLI behavior.

Run the complete local suite before requesting review:

```bash
uv run --extra dev tox
```

Tox runs pytest, Ruff, and ty. Pull requests and pushes to `main` run the equivalent checks in
GitHub Actions. During development, focused tests are fine, for example:

```bash
uv run --extra dev pytest tests/test_cli.py -q
uv run --extra dev ruff check .
uv run --extra dev ty check
```

Live Spotify E2E tests are opt-in because they access a real account and API. Follow the README's
E2E instructions, use local credentials only, and never commit `.env`, token caches, or generated
authorization data. Tests must not contact a physical Pixoo unless they are explicitly marked and
documented as hardware-dependent.

## Documentation

- Update `README.md` when user-facing commands, configuration, prerequisites, or troubleshooting
  behavior changes.
- Update `docs/spec.md` when application behavior or architecture changes.
- Keep examples portable across macOS and Linux. If an OS-specific workaround is necessary, label
  it clearly and avoid presenting a contributor-specific path as universal.
- Keep `release-log.md` current. Add unreleased user-visible changes under `HEAD`.

## Releases

Read `docs/release.md` before changing or performing the release process.

- Bump versions with `uv version X.Y.Z` so `pyproject.toml` and `uv.lock` remain aligned.
- Move applicable `HEAD` notes in `release-log.md` into the versioned section.
- Validate artifacts with `python ./build.py --build`. The script rejects a dirty worktree, a stale
  lock file, and missing release notes.
- Normal publication uses `.github/workflows/release.yml` and PyPI Trusted Publishing. Do not add
  a long-lived PyPI token.
- Once a push to `main` passes CI, an unpublished project version is published and receives the
  corresponding `vX.Y.Z` tag and GitHub Release. Manual workflow dispatch validates the build but
  does not publish.
- Keep `docs/release.md`, `build.py`, the release workflow, and
  `tests/test_release_workflow.py` aligned when release behavior changes.

## Change hygiene

- Keep changes scoped and avoid modifying unrelated user work in a dirty worktree.
- Do not commit secrets, local caches, generated GIFs, build artifacts, or machine-specific files.
- Use clear commit messages and include tests and documentation in the same change when relevant.
- Do not weaken CI, type checking, or lint rules merely to make a change pass.
