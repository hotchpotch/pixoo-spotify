# pixoo_spotify

pixoo_spotify shows the currently playing Spotify artwork and track info on a [Divoom Pixoo64](https://divoom.com/en-jp/products/pixoo-64) 64x64 Pixel Art LED Display.
Because the artwork is rendered at 64x64, it keeps the pixel art vibe crisp and charming.

<div style="display:inline-block; background:#0b0b0b; border:3px solid #000; padding:6px;">
  <div style="background:#1a1a1a; padding:3px;">
    <img src="assets/images/example.gif" alt="pixoo_spotify example" style="display:block; border:1px solid #000; image-rendering:pixelated;">
  </div>
</div>

Divoom’s official app supports Spotify playback, but it does not show the artwork, so this project fills that gap.

## Install

Install uv first. This gives you the uvx command.
https://docs.astral.sh/uv/getting-started/installation/

## Spotify setup (client ID)

- Register at https://developer.spotify.com/
- Create an app at https://developer.spotify.com/dashboard
  - Copy the Client ID
  - Set the Redirect URI to http://127.0.0.1:8888/callback

Then authenticate once with your Client ID:

```
uvx pixoo-spotify auth --client-id "CLIENT ID"
```

Spotify refresh tokens expire 6 months after authorization. When this happens,
`pixoo-spotify run` exits with re-authentication instructions instead of waiting for
interactive input. Re-authenticate on the server and then restart the service or process:

```
uvx pixoo-spotify auth --client-id "CLIENT ID" --reauth
```

For an SSH or other headless session, use the manual redirect flow:

```
uvx pixoo-spotify auth --client-id "CLIENT ID" --reauth --no-open-browser
```

See Spotify's [refresh token expiration announcement](https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration)
for the current policy.

### Live Spotify E2E tests

The live tests are opt-in and use a dedicated token cache so they do not modify the normal
`pixoo-spotify` authorization. Copy `.env.sample` to `.env`, set `SPOTIFY_CLIENT_ID`, and obtain
the dedicated token once:

```
set -a
source .env
set +a
uv run pixoo-spotify auth \
  --client-id "$SPOTIFY_CLIENT_ID" \
  --cache-path "$SPOTIFY_E2E_TOKEN_CACHE" \
  --reauth \
  --no-open-browser
```

Keep `RUN_SPOTIFY_E2E=0` in `.env` so normal test runs stay offline. Enable the live tests for
one command only:

```
RUN_SPOTIFY_E2E=1 uv run --extra dev pytest -m spotify_e2e
```

This calls Spotify's real token endpoint to verify `invalid_grant`, refreshes the dedicated token,
and calls the current playback API. Normal pytest and tox runs skip these network tests.

## Fonts (optional)

By default, a bundled 8‑pixel font that supports English and Japanese [Misaki font](https://littlelimit.net/misaki.htm) is used.

If you want Latin/CJK/Korean coverage, install additional fonts:

```
uv run pixoo-spotify font-install
```

This downloads pixel fonts from:
https://github.com/TakWolf/fusion-pixel-font

## Run

```
uvx pixoo-spotify run
```

For detailed command-line options:

```
uvx pixoo-spotify run --help
```

If you run with no options, the app will try to infer the Spotify language from your environment and discover the Pixoo device on your local network. You can also provide all values manually.

## Image filters

You can post-process album artwork with an image filter chain:

```
uvx pixoo-spotify run --image-filters "default"
```

See `docs/image_filters.md` for available filters and examples.
To disable filters and use legacy resizing only:

```
uvx pixoo-spotify run --no-image-filters
```

## Troubleshooting

When the Pixoo device accesses the server, it needs permission to reach port 18080 on the machine running pixoo_spotify. If the OS firewall blocks this port, allow or open it.

## License

- Source code: MIT

## Author

- Yuichi Tateno (@hotchpotch)
