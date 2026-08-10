# pixoo-spotify

Show the artwork, title, and artist for the currently playing Spotify track on a
[Divoom Pixoo64](https://divoom.com/en-jp/products/pixoo-64) pixel display.

<div style="display:inline-block; background:#0b0b0b; border:3px solid #000; padding:6px;">
  <div style="background:#1a1a1a; padding:3px;">
    <img src="assets/images/example.gif" alt="Spotify artwork and scrolling track information displayed as a 64×64 pixel GIF" style="display:block; border:1px solid #000; image-rendering:pixelated;">
  </div>
</div>

The app polls Spotify, renders a pixel-art GIF, serves it over HTTP, and tells the Pixoo to
display that URL:

```text
Spotify Web API → GIF renderer → local HTTP server ← Pixoo64
```

## Features

- Spotify Authorization Code flow with PKCE; no client secret required
- Album artwork with scrolling title and artist text
- 64, 32, and 16-pixel output modes
- Pixel-art image filter chains and palette controls
- Automatic Pixoo discovery and recovery after device connection errors
- Rich foreground UI or plain text logs for server operation
- English/Japanese fallback font plus optional Latin, CJK, and Korean fonts
- Display power, brightness, and settings commands
- Live opt-in Spotify E2E tests

## Less network setup by design

The networking defaults are designed so a normal home-LAN setup usually needs no IP address or
port configuration:

| Under the hood | What it means for you |
| --- | --- |
| Pixoo discovery | You normally do not need to look up or enter the display's IP address. |
| Route-aware host IP selection | The app asks the operating system which local address reaches the Pixoo, avoiding the wrong Wi-Fi, Ethernet, or VPN address. |
| Automatic port selection | When no port is configured, the first available port from `18080` through `18099` is used. |
| Rediscovery after connection errors | If DHCP changes the Pixoo's address, the app can find it again and update the GIF URL. |
| Cache-busting GIF URLs | Each track update gets a fresh URL so the Pixoo does not keep showing a cached image. |

Every automatic choice can still be overridden for Docker, VPN, multi-interface, and fixed-IP
deployments.

## Local network requirement

**The machine running pixoo-spotify and the Pixoo64 must be on the same local network and able to
connect to each other.** The app sends commands directly to the Pixoo, and the Pixoo connects back
to the app's HTTP server to download the generated GIF.

Using the same internet connection is not always sufficient: guest Wi-Fi, wireless client
isolation, host firewalls, and some VPN or container configurations can block device-to-device
traffic. A routed LAN is fine; the two devices do not have to use Wi-Fi or be on the exact same
subnet as long as traffic can pass in both directions.

## Requirements

- A Pixoo64 reachable on the same local network as the machine running this app
- A Spotify account and a [Spotify Developer](https://developer.spotify.com/dashboard) app
- A Spotify Premium account when required by Spotify's current Development Mode policy
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for the `uvx` command

## Quick start

### 1. Create a Spotify app

Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an app,
and add this exact Redirect URI:

```text
http://127.0.0.1:8888/callback
```

Copy the app's Client ID. A client secret is not needed.

### 2. Authenticate

```bash
uvx pixoo-spotify auth --client-id "YOUR_CLIENT_ID"
```

The Client ID and token are stored in the platform config directory, so the Client ID does not
need to be passed to later `run` commands.

### 3. Run

```bash
uvx pixoo-spotify run
```

By default, the app discovers a Pixoo on the local network, starts an HTTP server on an available
port, polls Spotify, and updates the display when the track changes.

Use `Ctrl+C` to stop it. See every available option with:

```bash
uvx pixoo-spotify run --help
```

## Update pixoo-spotify

`uvx` runs the package in a cached, isolated environment rather than installing it permanently.
Refresh that environment and upgrade pixoo-spotify and its compatible dependencies with:

```bash
uvx --upgrade pixoo-spotify --version
```

You can then use the normal `uvx pixoo-spotify ...` commands. To explicitly run the newest release
in a single command, use `pixoo-spotify@latest`:

```bash
uvx pixoo-spotify@latest --version
```

If you chose a persistent tool installation instead, upgrade it with:

```bash
uv tool upgrade pixoo-spotify
```

These commands upgrade pixoo-spotify, not `uv` itself. See the official
[uv tools guide](https://docs.astral.sh/uv/guides/tools/) for details.

## Server and SSH operation

Use text output when running under systemd, Docker, tmux, or another non-interactive environment:

```bash
uvx pixoo-spotify run \
  --ui text \
  --log-format basic \
  --device-ip 192.168.1.50 \
  --no-discover \
  --server-port 18080 \
  --public-base-url http://192.168.1.20:18080
```

- `--device-ip` is the Pixoo address.
- `--public-base-url` is the URL the Pixoo uses to fetch the generated GIF.
- The Pixoo must be able to reach the server port through the host firewall.
- An explicit base URL is useful on hosts with multiple interfaces, VPNs, or containers.

### Authenticate from a headless server

```bash
uvx pixoo-spotify auth --client-id "YOUR_CLIENT_ID" --no-open-browser
```

Open the printed URL in a browser, approve access, then paste the full redirected URL back into
the terminal. The browser may show that `127.0.0.1` cannot be reached when it is running on a
different machine; the complete URL in its address bar is still the value to paste.

### Refresh token expiration

Spotify refresh tokens expire six months after authorization. If the token expires while the app
is running—or is already expired at startup—the app:

1. stops without waiting for interactive input;
2. discards a token rejected with `invalid_grant`;
3. prints interactive and headless re-authentication commands; and
4. exits with a non-zero status so the failure is visible to a service manager.

Re-authenticate and restart the service or process:

```bash
uvx pixoo-spotify auth --client-id "YOUR_CLIENT_ID" --reauth --no-open-browser
```

See [Spotify's refresh token expiration announcement](https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration)
for the policy details.

## Artwork and text customization

The default artwork filter pipeline reduces noise and colors to produce a clearer pixel-art image.
Use a custom chain with `|` separators:

```bash
uvx pixoo-spotify run \
  --image-filters "blur:0.6|median:3|posterize:4|quantize:32"
```

Disable the filter chain and use legacy resize-only behavior:

```bash
uvx pixoo-spotify run --no-image-filters
```

Other useful options include:

```bash
# Artwork without text
uvx pixoo-spotify run --artwork-only

# Bounce text and pause at each edge
uvx pixoo-spotify run --scroll-mode bounce --scroll-pause-frames 15

# Change text content and position
uvx pixoo-spotify run \
  --text-format "{artist}\n{title}" \
  --text-position bottom-right
```

See [docs/image_filters.md](docs/image_filters.md) for every filter and its arguments.

## Fonts

The packaged Misaki Gothic font provides an 8-pixel English/Japanese fallback. To install the
recommended Fusion Pixel Font for broader Latin, CJK, and Korean coverage, use the same `uvx`
command as the rest of this guide:

```bash
uvx pixoo-spotify font-install
```

The command shows the font license and asks for confirmation before downloading. A custom font can
also be assigned to a language code:

```bash
uvx pixoo-spotify font-install --lang ja --font-path ./font.ttf
```

## Device commands

```bash
# Find Pixoo devices on the LAN
uvx pixoo-spotify devices

# Turn the display on or off
uvx pixoo-spotify display on --device-ip 192.168.1.50
uvx pixoo-spotify display off --device-ip 192.168.1.50

# Set or read brightness
uvx pixoo-spotify brightness set --value 40 --device-ip 192.168.1.50
uvx pixoo-spotify brightness get --device-ip 192.168.1.50

# Print all settings returned by the device
uvx pixoo-spotify settings all --device-ip 192.168.1.50
```

Each device command uses discovery when `--device-ip` is omitted.

## Configuration file

`run` accepts TOML or JSON. If `config.toml` exists in the current directory, it is loaded
automatically; use `--config` to select another file.

```toml
poll_interval = 5
idle_poll_interval = 20

[pixoo]
device_ip = "192.168.1.50"
discover = false
auto_screen_off = true

[server]
host = "0.0.0.0"
port = 18080
public_base_url = "http://192.168.1.20:18080"

[gif]
size = 64
image_filters = ["default"]
scroll_mode = "loop"
text_format = "{title}\n{artist}"

[ui]
mode = "text"
log_format = "basic"
```

```bash
uvx pixoo-spotify run --config ./config.toml
```

CLI options override values from the configuration file.

## Local data

Authentication data, fonts, and the latest generated GIF are kept outside the repository.

| Data | macOS | Linux |
| --- | --- | --- |
| Client ID and Spotify token | `~/Library/Application Support/pixoo-spotify/` | `~/.config/pixoo-spotify/` |
| Installed fonts | `<config directory>/fonts/` | `<config directory>/fonts/` |
| Latest GIF | `<config directory>/output/latest.gif` | `<config directory>/output/latest.gif` |

Use the global `--config-path` option before the command to relocate authentication files and
fonts:

```bash
uvx pixoo-spotify --config-path /srv/pixoo-spotify auth --client-id "YOUR_CLIENT_ID"
uvx pixoo-spotify --config-path /srv/pixoo-spotify run
```

Use `run --gif-output PATH` to explicitly relocate the generated GIF.

## Generate a GIF without a Pixoo

Create a demo using bundled sample data:

```bash
uvx pixoo-spotify demo --output output/demo.gif
```

Or provide track metadata manually:

```bash
uvx pixoo-spotify gif \
  --artist "Artist" \
  --title "Track" \
  --album "Album" \
  --artwork-url "https://example.com/artwork.jpg" \
  --output output/manual.gif
```

## Troubleshooting

| Problem | What to check |
| --- | --- |
| No Pixoo is found | Run `uvx pixoo-spotify devices`, confirm both devices are on the same local network, and check for guest Wi-Fi or client isolation; otherwise pass `--device-ip`. |
| The Pixoo does not load the GIF | Allow the selected server port through the firewall and set a reachable `--public-base-url`. |
| Spotify authorization is missing or expired | Run the re-authentication command printed by `uvx pixoo-spotify run`, then restart it. |
| Spotify rejects the callback | Register `http://127.0.0.1:8888/callback` exactly in the Spotify Dashboard. Do not use `localhost`. |
| Text has missing glyphs | Run `uvx pixoo-spotify font-install` or install a language-specific font. |
| More diagnostics are needed | Add the global `--verbose` option before the command. |

## Development

```bash
git clone https://github.com/hotchpotch/pixoo-spotify.git
cd pixoo-spotify
uv sync --extra dev
uv run --extra dev tox
```

Tox runs pytest, Ruff, and ty.

### Live Spotify E2E tests

The live tests use a dedicated token cache and never use the normal application token. Copy the
sample environment file and set your Client ID:

```bash
cp .env.sample .env
```

Create the dedicated token once:

```bash
set -a
source .env
set +a
uv run pixoo-spotify auth \
  --client-id "$SPOTIFY_CLIENT_ID" \
  --cache-path "$SPOTIFY_E2E_TOKEN_CACHE" \
  --reauth \
  --no-open-browser
```

Keep `RUN_SPOTIFY_E2E=0` in `.env` so normal test runs stay offline. Enable live access for one
command only:

```bash
RUN_SPOTIFY_E2E=1 uv run --extra dev pytest -m spotify_e2e
```

The E2E suite calls Spotify's real token endpoint, verifies `invalid_grant` handling, refreshes the
dedicated token, and calls the current playback API.

## License

MIT

## Author

[Yuichi Tateno](https://github.com/hotchpotch) (`@hotchpotch`)
