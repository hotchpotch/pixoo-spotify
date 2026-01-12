# Release Log

## HEAD

- (unreleased)
- Continue running if Pixoo GIF delivery fails (e.g., connection timeouts), logging the error instead of crashing.
- Rediscover Pixoo and refresh the local base URL after Pixoo connection errors when using auto-detected endpoints.
- Attempt Pixoo rediscovery on track changes when the device is missing or a previous Pixoo request failed, with informative logs.
- Add a Rich UI status panel showing Pixoo connectivity and the local server URL.

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
