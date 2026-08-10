# AGENTS.md for /Users/hotchpotch/src/github.com/hotchpotch/pixoo-spotify

<INSTRUCTIONS>
## Project conventions
- Use `uv add` for all dependencies. Keep runtime deps in `[project.dependencies]`.
- Dev tools must live in the `dev` extra. Update via `uv add --optional dev <pkgs>` (tox runs with `uv run --extra dev tox`).
- If `uv.lock` changes, include it in the same commit.
- Prefer async/await for IO. Keep Pydantic models for config and data payloads.
- CLI uses Typer. Non-background mode should show a small Rich UI panel (see `pixoo_spotify/ui.py`).
- HTTP server uses `http.server` (ThreadingHTTPServer) to keep it lightweight.
- Spotify auth uses PKCE (no client secret required). Default redirect is `http://127.0.0.1:8888/callback`.
- `auth` requires `--client-id`; the value is cached under the platform config directory.
- Config directory can be overridden with `--config-path` (global option).
- For headless auth, set `--no-open-browser` and copy/paste the redirect URL.
- Fonts live under the config directory (same location as auth files) in `fonts/`.
- Use `pixoo-spotify font-install` to install the recommended Fusion Pixel Font.
- If no fonts are installed, the packaged Misaki Gothic fallback is used.
- Default GIF output lives under the platform config directory (`output/latest.gif` under the same base as auth/cache). Demo/manual commands still use `output/`.
- HTTP server serves `/spotify_gif` (Pixoo URL includes a cache-busting `?{epoch}`).
- Keep `release-log.md` updated. Use the `HEAD` section for unreleased changes, and move those notes into a versioned section during each release.
- Validate release artifacts locally with `python ./build.py --build`; it fails if the git worktree
  is dirty, `uv.lock` is stale, or the versioned release-log entry is missing.
- Before release, bump `pyproject.toml` with `uv version X.Y.Z` so `uv.lock` stays aligned and PyPI
  does not reject a duplicate version.
- Releases publish through `.github/workflows/release.yml` using PyPI Trusted Publishing. Do not
  add or use a long-lived PyPI token for the normal release path.
- After a push to `main` passes CI, the release workflow builds and checks distributions. If
  `[project].version` is not on PyPI, it publishes through Trusted Publishing and creates the
  matching `vX.Y.Z` tag and GitHub Release. Already-published versions are built but not republished.
- Manual release-workflow dispatch exercises the build job without publishing.
- Keep `docs/release.md`, the release workflow, `build.py`, and `tests/test_release_workflow.py`
  aligned when changing release behavior.

## Testing & linting
- Run: `uv run --extra dev tox` after implementation changes and before release.
- Tox runs pytest, ruff, and ty.
- PRs and pushes to `main` must pass the same command through `.github/workflows/ci.yaml`.

## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.
### Available skills
- skill-creator: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/hotchpotch/syncthing/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: /Users/hotchpotch/syncthing/.codex/skills/.system/skill-installer/SKILL.md)
### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  3) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  4) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.
</INSTRUCTIONS>
