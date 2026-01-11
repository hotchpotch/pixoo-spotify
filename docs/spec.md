# pixoo-spotify Specification Notes

## 1. Initial spec (summary)
- A CLI app that generates GIFs for Pixoo (64x64/32x32/16x16) and serves them via an HTTP server.
- Fetches Spotify "now playing" info and renders artwork + text (artist/title).
- GIF requirements:
  - Use artwork as a 64x64 background (or gray when missing).
  - Scroll `{artist}\n{title}` line by line.
- Bitmap font (fixed 8px). Default is Misaki Gothic.
  - Max 40 characters.
- Bottom-left alignment by default, position selectable.
  - FPS is 8.
- Fonts are stored under the config directory `fonts/`.
- Per-line language detection (langdetect). Use a font matching the language code if available, otherwise fallback.
- HTTP server uses lightweight `http.server`.
- CLI is Typer, types are enforced with Pydantic and type hints.
- Pixoo device discovery endpoint: `https://app.divoom-gz.com/Device/ReturnSameLANDevice`
- Pixoo playback command: `Device/PlayTFGif`

## 2. Current implementation (as of 2026-01-09)
### Structure and core modules
- `pixoo_spotify/cli.py`
  - Typer CLI: `run` / `auth` / `devices` / `demo` / `gif`
- `pixoo_spotify/app.py`
  - Main loop: Spotify -> GIF generation -> HTTP serving -> Pixoo playback
- `pixoo_spotify/gif.py`
  - GIF generation logic (artwork + per-line scrolling)
- `pixoo_spotify/fonts.py`
  - Font installation (Fusion Pixel Font / manual)
- `pixoo_spotify/spotify.py`
  - Spotipy OAuth + now playing track retrieval
- `pixoo_spotify/pixoo.py`
  - Pixoo device discovery / PlayTFGif calls
- `pixoo_spotify/server.py`
  - Serves `/spotify_gif` via `http.server` (Pixoo is sent with `?{epoch}`)
- `pixoo_spotify/config.py`
  - Pydantic settings, config.toml/json support
- `pixoo_spotify/ui.py`
  - Rich UI output (foreground mode)
- `pixoo_spotify/dummy.py`
  - Dummy track + artwork
- `tests/`
  - Tests for GIF generation and config merging
- `release-log.md`
  - Unreleased notes in HEAD, move to version section on release
- `build.py`
  - Release helper (test/build/publish/tag, fails on dirty tree or missing release log)

### Dependencies
- Runtime: `typer`, `pydantic`, `spotipy`, `httpx`, `pillow`, `langdetect`, `rich`
- Dev: `pytest`, `ruff`, `ty`, `tox`, `tox-uv`
- Dev extra registered: `uv run --extra dev tox`

### Spotify auth (PKCE)
- Uses PKCE, no `client_secret` required (only `client_id`).
- Default `redirect_uri` is `http://127.0.0.1:8888/callback`.
- If a GUI browser is available, auth completes automatically via local redirect.
- Without GUI, open the URL on another device and copy the redirect URL back.
- Always pass `client_id` with `auth --client-id`. The value is cached and reused.
- Auth data is stored under the platform config directory.
  - Linux: `~/.config/pixoo-spotify/`
  - macOS: `~/Library/Application Support/pixoo-spotify/`
  - `auth_spotify_client.json` and `spotify_token.json` are created.
- If auth files already exist, `auth --reauth` is required.

### CLI examples
- Auth: `uv run pixoo-spotify auth`
- Run: `uv run pixoo-spotify run --public-base-url http://<host>:8000 --device-ip <pixoo-ip>`
- Demo GIF: `uv run pixoo-spotify demo`
- Install fonts: `uv run pixoo-spotify font-install`
- Version: `uv run pixoo-spotify --version`

## 3. Open questions / needs verification
- Headless Spotify OAuth (`open_browser=True`) may fail depending on environment.
- PKCE redirect URLs not using `127.0.0.1` require HTTPS (be careful in production).
- Whether Pixoo `Device/PlayTFGif` plays correctly on real hardware is unverified.
- Whether Pixoo displays GIF scrolling as intended is unverified.
- Whether Pixoo can fetch 32/16 size images (not only 64px) needs confirmation.
- Network reachability of Pixoo to the server when `public_base_url` is not set.
- Behavior when network fails during `font-install`.
- Visual overflow issues at max length (40 chars) need verification.

## 4. Notes for the next developer
- First priority: verify playback on real Pixoo hardware.
- Spotify auth is manual input flow; for production, add a redirect handler suitable for operations.
- There is no `config.toml` sample yet; consider adding a template for ops.
- Scroll speed, margins, and position are configurable in `GifConfig`.
- Language detection is per line; use `<lang>.ttf` when available, otherwise `fallback.ttf`.
- 64/32/16 sizes are configurable via `GifConfig.size`, but visual legibility needs testing.
- Tests are light; add integration tests if you automate Pixoo hardware tests.
