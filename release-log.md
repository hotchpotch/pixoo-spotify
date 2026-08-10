# Release Log

## HEAD

- (unreleased)

## 0.1.0

- Add matching local and GitHub Actions validation, verified package builds, PyPI Trusted
  Publishing, and automated GitHub Release creation.
- Modernize package license metadata to the SPDX form expected by current build tools.
- Rewrite the README around the current quick-start and demo media, automatic LAN setup, server
  operation, package updates, customization, device controls, configuration, troubleshooting, and
  live E2E workflows.
- Detect expired or missing Spotify authorization during server operation, discard refresh tokens
  rejected with `invalid_grant`, and show interactive and headless re-authentication instructions.
- Add opt-in live Spotify E2E coverage for refresh, playback, and `invalid_grant` handling.
- Update Spotipy to 2.26.0, Ruff to 0.16.2, ty to 0.0.69, tox to 4.58.0, and
  tox-uv to 1.36.0.
- Reject excess image filter arguments instead of silently ignoring them.
- Add artwork image filter chains with a default pixel-art pipeline and a `--no-image-filters` escape hatch.
- Continue running if Pixoo GIF delivery fails (e.g., connection timeouts), logging the error instead of crashing.
- Rediscover Pixoo and refresh the local base URL after Pixoo connection errors when using auto-detected endpoints.
- Attempt Pixoo rediscovery on track changes when the device is missing or a previous Pixoo request failed, with informative logs.
- Add a Rich UI status panel showing Pixoo connectivity and the local server URL.
- Add Pixoo CLI commands for display on/off, brightness set/get, and full settings fetch.

## 0.0.4

- Add a 16px blank gap after scrolling text completes before restarting the line from offscreen.
- Refresh README with an example GIF, framed styling, links, and run help usage.
- Translate docs/spec.md to English.
- Add a release-time check to ensure `uv.lock` is up to date.

## 0.0.3

- Add CLI version flag.
- Add release helper script and release log checks.

## 0.0.2

- Ensure the bundled fallback font is included in the package.

## 0.0.1

- Initial release.
