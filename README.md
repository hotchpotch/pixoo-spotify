<div align="center">

# pixoo-spotify

**Your currently playing Spotify track — album art, title, and artist — live on a [Divoom Pixoo64](https://divoom.com/en-jp/products/pixoo-64).**

[![PyPI](https://img.shields.io/pypi/v/pixoo-spotify.svg)](https://pypi.org/project/pixoo-spotify/)
[![Python](https://img.shields.io/pypi/pyversions/pixoo-spotify.svg)](https://pypi.org/project/pixoo-spotify/)
[![CI](https://github.com/hotchpotch/pixoo-spotify/actions/workflows/ci.yaml/badge.svg)](https://github.com/hotchpotch/pixoo-spotify/actions/workflows/ci.yaml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<img src="assets/images/example.gif" width="64" alt="Album artwork with scrolling track title and artist, rendered as a 64x64 pixel-art GIF">

</div>

▶️ **See it running on a real Pixoo64:**

https://github.com/user-attachments/assets/b0999523-6a8b-48c7-a5b9-88008be070a0

---

## ✨ Why pixoo-spotify

- **Two CLI commands to a working display.** Authenticate once, then `run`. A typical setup needs no IP address, port forwarding, or broker.
- **No client secret.** Spotify Authorization Code with PKCE — you only paste a Client ID.
- **Finds your Pixoo for you.** Device discovery, route-aware host-IP selection, and port selection happen automatically; rediscovery can recover after a network hiccup.
- **Built for unattended operation.** Rich terminal UI when you're watching, plain logs when systemd is. Headless SSH login. Non-zero exit and a copy-pasteable fix when your Spotify session expires.
- **Real pixel art, not a downscale.** A tuned filter pipeline (blur → median → posterize → quantize) keeps 64×64 artwork readable instead of muddy.
- **Rendering stays on your machine.** Artwork is processed locally and served by a small local HTTP server — no third-party rendering service in the loop.

### How it works

```text
Spotify Web API  →  GIF renderer  →  local HTTP server  ←  Pixoo64
```

pixoo-spotify polls Spotify for the current track, renders a pixel-art GIF, serves it at
`/spotify_gif` from a lightweight local server, and tells the Pixoo to fetch that URL. Each
update uses a cache-busting URL so the display never gets stuck on a stale frame.

> [!IMPORTANT]
> **The Pixoo64 and the machine running pixoo-spotify must be able to reach each other over your
> local network.** pixoo-spotify sends commands *to* the Pixoo, and the Pixoo connects *back* to
> download the GIF — so traffic has to flow in both directions.
>
> Sharing an internet connection is not enough. Guest Wi-Fi, wireless client isolation, host
> firewalls, and some VPN or container setups block device-to-device traffic. A routed LAN is
> fine — the two do not have to sit on the exact same subnet, as long as both directions are
> routable.

---

## 📋 Requirements

| What | You need |
| --- | --- |
| **Hardware** | A Divoom Pixoo64 on your local network |
| **Spotify** | A Spotify Premium account and an app registered in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |
| **Runtime** | [uv](https://docs.astral.sh/uv/getting-started/installation/) (provides `uvx`); Python 3.10+ is fetched by uv automatically |

> [!NOTE]
> Spotify's Development Mode requires the app owner to have an active Premium subscription. Each
> listening account must also be added to the app's allowlist (up to five users). See Spotify's
> current [quota-mode documentation](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
> if authorization succeeds but playback data stays empty.

---

## 🚀 Quick start

### 1. Register a Spotify app

In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an app and
add this **exact** Redirect URI:

```text
http://127.0.0.1:8888/callback
```

Copy the **Client ID**. You do not need a client secret.

### 2. Save the Client ID and authenticate

Create a `.env` file in the directory where you will run pixoo-spotify:

```dotenv
SPOTIFY_CLIENT_ID=YOUR_CLIENT_ID
```

Then authenticate without repeating the Client ID on the command line:

```bash
uvx pixoo-spotify auth
```

A browser opens for approval. The Client ID and token are stored in your user config directory,
so later commands don't need `--client-id`.

Alternatively, skip `.env` and pass it directly with
`uvx pixoo-spotify auth --client-id "YOUR_CLIENT_ID"`.

> [!TIP]
> If the browser redirect doesn't complete, the command also accepts the full redirected URL
> pasted straight into the terminal — no need to restart.

### 3. Run

```bash
uvx pixoo-spotify run
```

That's it. pixoo-spotify discovers your Pixoo, starts a local server on a free port, polls
Spotify, and updates the display on every track change. Press `Ctrl+C` to stop.

```bash
uvx pixoo-spotify run --help   # every available option
```

---

## 🖥️ Servers, Raspberry Pi, and SSH

### Authenticate without a local browser

```bash
uvx pixoo-spotify auth --client-id "YOUR_CLIENT_ID" --no-open-browser
```

Open the printed URL in a browser on any machine, approve access, then paste the **full redirected
URL** back into the terminal. That browser will show "`127.0.0.1` can't be reached" — expected, and
irrelevant. The URL in its address bar is still what you paste.

> [!TIP]
> Already authenticated? `auth` refuses to overwrite existing credentials. Add `--reauth` to
> replace them.

### Run unattended

Use text mode so output is plain, timestamped lines instead of a live Rich panel:

```bash
uvx pixoo-spotify run --ui text --log-format basic
```

For hosts with several interfaces, a VPN, a container network, or a Pixoo on a fixed IP, pin every
moving part explicitly:

```bash
uvx pixoo-spotify run \
  --ui text \
  --log-format basic \
  --device-ip 192.168.1.50 \
  --no-discover \
  --server-port 18080 \
  --public-base-url http://192.168.1.20:18080
```

| Option | What it pins |
| --- | --- |
| `--device-ip` / `--no-discover` | The Pixoo's address; skips discovery entirely |
| `--server-port` | The port the local GIF server listens on |
| `--public-base-url` | The URL the **Pixoo** uses to fetch the GIF — must be reachable *from the Pixoo* |

The Pixoo must be able to reach that server port through the host firewall.

Add `--auto-screen-off` if the panel should turn off while nothing is playing.

### When your Spotify session expires

Spotify refresh tokens expire **six months** after authorization. When that happens — at startup or
mid-run — pixoo-spotify does not hang waiting for input. It discards the token rejected with
`invalid_grant`, prints ready-to-run re-authentication commands (interactive and headless), and
exits non-zero so systemd or your supervisor reports the failure.

Recover with:

```bash
uvx pixoo-spotify auth --client-id "YOUR_CLIENT_ID" --reauth --no-open-browser
```

Then restart the service. See Spotify's
[refresh token expiration announcement](https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration)
for the policy itself.

<details>
<summary><b>What the automatic networking actually does</b></summary>

| Behavior | Detail |
| --- | --- |
| **Pixoo discovery** | Asks Divoom's cloud endpoint which Pixoo devices share your public IP, then uses the first one's private address. It needs outbound internet access, and it fails if the host leaves through a different public IP than the Pixoo — a VPN or an isolated container network is the usual culprit. Pass `--device-ip` to skip it. |
| **Host IP selection** | Asks the OS which local address routes to the Pixoo, so the GIF URL doesn't advertise the wrong Wi-Fi, Ethernet, or VPN address. |
| **Port selection** | Without a config file or explicit port, the first free port in `18080`–`18099` is used. |
| **Rediscovery** | After a Pixoo connection error — or a track change while the device is unreachable — discovery reruns and the GIF URL is rebuilt, so a DHCP address change heals itself. |
| **Cache busting** | Every update appends a fresh timestamp to the GIF URL. |

> **⚠️ Config-file port behavior:** Automatic port selection applies only when `--server-port` is
> omitted and no config file is in play. If a `config.toml` sits in the working directory (it is
> loaded automatically) or you pass `--config`, the port falls back to the built-in default `8000`
> unless you set it. Set `[server] port` explicitly in any config file you use.

Rediscovery is also skipped when you supplied `--device-ip` — an explicit address is always
respected.

</details>

---

## 🔄 Updating

`uvx` runs pixoo-spotify from a cached, isolated environment rather than installing it. Refresh
that cache with:

```bash
uvx --upgrade pixoo-spotify --version
```

Afterwards the plain `uvx pixoo-spotify ...` commands use the new version.

<details>
<summary><b>Other update options</b></summary>

Explicitly request the newest release for a command:

```bash
uvx pixoo-spotify@latest --version
```

If you installed it persistently instead (`uv tool install pixoo-spotify`):

```bash
uv tool upgrade pixoo-spotify
```

All of these upgrade **pixoo-spotify**, not `uv` itself — for that, see the
[uv tools guide](https://docs.astral.sh/uv/guides/tools/).

</details>

---

## 🎨 Customization

### Artwork

The default filter chain (`blur:0.6|median:3|posterize:4|quantize:32`) reduces noise and color
count so 64×64 artwork reads as pixel art. Override it with your own `|`-separated chain:

```bash
uvx pixoo-spotify run --image-filters "blur:0.6|median:3|posterize:4|quantize:32"
```

Or turn it off for plain resize-only behavior:

```bash
uvx pixoo-spotify run --no-image-filters
```

Every filter and its arguments are documented in [docs/image_filters.md](docs/image_filters.md).

### Text and layout

```bash
# Artwork only, no text
uvx pixoo-spotify run --artwork-only

# Bounce the text and pause at each edge
uvx pixoo-spotify run --scroll-mode bounce --scroll-pause-frames 15

# Change what the text says and where it sits
uvx pixoo-spotify run \
  --text-format "{artist}\n{title}" \
  --text-position bottom-right
```

`--text-format` accepts `{title}`, `{artist}`, and `{album}`, up to three `\n`-separated lines.
`--text-position` takes `bottom-left` (default), `bottom-right`, `top-left`, or `top-right`.
`--gif-size` accepts `16`, `32`, or `64`.

### Fonts

A packaged **Misaki Gothic** 8-pixel font covers English and Japanese out of the box. For broader
Latin, Japanese, Korean, and Simplified/Traditional Chinese coverage, install the recommended
**Fusion Pixel Font**:

```bash
uvx pixoo-spotify font-install
```

The command shows the license (OFL-1.1) and asks for confirmation before downloading. You can also
assign your own font to one language:

```bash
uvx pixoo-spotify font-install --lang ja --font-path ./font.ttf
```

---

## 📟 Device commands

```bash
# List Pixoo devices
uvx pixoo-spotify devices

# Turn the panel on or off
uvx pixoo-spotify display on  --device-ip 192.168.1.50
uvx pixoo-spotify display off --device-ip 192.168.1.50

# Set or read brightness (0-100)
uvx pixoo-spotify brightness set --value 40 --device-ip 192.168.1.50
uvx pixoo-spotify brightness get --device-ip 192.168.1.50

# Dump everything the device reports
uvx pixoo-spotify settings all --device-ip 192.168.1.50
```

Omit `--device-ip` on any of these and discovery is used instead.

---

## ⚙️ Configuration file

`run` accepts TOML or JSON. A `config.toml` in the working directory is loaded automatically; use
`--config` to point elsewhere. `auth` accepts the same option.

```toml
poll_interval = 5
idle_poll_interval = 20

[spotify]
client_id = "YOUR_CLIENT_ID"

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

Client ID sources use this precedence, from highest to lowest:

1. `--client-id`
2. `[spotify].client_id` in the selected TOML/JSON configuration
3. An existing `SPOTIFY_CLIENT_ID` environment variable
4. `SPOTIFY_CLIENT_ID` in `.env` in the working directory
5. The Client ID cached by a previous successful `auth` command

This makes TOML preferable for an explicit server configuration while `.env` remains convenient
for a local checkout. Never commit `.env`.

---

## 📂 Where your data lives

Credentials, fonts, and the generated GIF are kept in your user config directory — never in the
repository. Don't commit `.env`, credentials, or token caches.

| Data | File | Location |
| --- | --- | --- |
| Cached Client ID | `auth_spotify_client.json` | config directory |
| Spotify token | `spotify_token.json` | config directory |
| Installed fonts | `fonts/` | config directory |
| Latest GIF | `output/latest.gif` | config directory |

By default, the config directory is `~/Library/Application Support/pixoo-spotify/` on macOS and
`~/.config/pixoo-spotify/` on Linux.

Relocate credentials and fonts with the global `--config-path`, placed **before** the command:

```bash
uvx pixoo-spotify --config-path /srv/pixoo-spotify auth --client-id "YOUR_CLIENT_ID"
uvx pixoo-spotify --config-path /srv/pixoo-spotify run
```

> [!NOTE]
> `--config-path` moves credentials and fonts, but **not** the generated GIF — it stays in the
> platform config directory. Use `run --gif-output PATH` to move that.

---

## 🧪 Try it without a Pixoo

Render a GIF from bundled sample data:

```bash
uvx pixoo-spotify demo --output output/demo.gif
```

Or from track metadata you supply:

```bash
uvx pixoo-spotify gif \
  --artist "Artist" \
  --title "Track" \
  --album "Album" \
  --artwork-url "https://example.com/artwork.jpg" \
  --output output/manual.gif
```

---

## 🩺 Troubleshooting

| Symptom | What to check |
| --- | --- |
| **No Pixoo found** | Run `uvx pixoo-spotify devices`. Discovery needs outbound internet and matches devices by public IP, so a VPN, guest Wi-Fi, or client isolation will break it. Pass `--device-ip` to bypass discovery. |
| **The Pixoo never loads the GIF** | Allow the server port through the host firewall, and make sure `--public-base-url` is an address the *Pixoo* can reach. From another device on the LAN, `curl http://<host-ip>:<port>/` should return `{"status": "ok", "gif": "/spotify_gif"}`. |
| **Spotify authorization missing or expired** | Run the re-authentication command printed by `run`, then restart it. See [When your Spotify session expires](#when-your-spotify-session-expires). |
| **Spotify rejects the callback** | Register `http://127.0.0.1:8888/callback` *exactly* in the dashboard. `localhost` is not accepted. |
| **Boxes instead of characters** | Run `uvx pixoo-spotify font-install`, or install a font for that language. |
| **Display stays blank while music plays** | Confirm the account is added to your Spotify app's user list, and that `uvx pixoo-spotify run` reports a discovered device rather than `not found`. |
| **Need more detail** | Add the global `--verbose` before the command: `uvx pixoo-spotify --verbose run`. |

---

## 🛠️ Development

```bash
git clone https://github.com/hotchpotch/pixoo-spotify.git
cd pixoo-spotify
uv sync --extra dev
uv run --extra dev tox
```

Tox runs pytest, Ruff, and ty.

See [docs/release.md](docs/release.md) for PR validation, local package checks, and the PyPI Trusted
Publishing release process.

<details>
<summary><b>Live Spotify E2E tests (opt-in)</b></summary>

These tests call Spotify's real token and playback endpoints. They use a **dedicated** token cache
and never touch your normal application token.

```bash
cp .env.sample .env   # then set SPOTIFY_CLIENT_ID
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

Keep `RUN_SPOTIFY_E2E=0` in `.env` so ordinary test runs stay offline, and enable live access for a
single command:

```bash
RUN_SPOTIFY_E2E=1 uv run --extra dev pytest -m spotify_e2e
```

The suite verifies `invalid_grant` handling, refreshes the dedicated token, and calls the current
playback API. `.env` is git-ignored — keep it that way.

</details>

---

## License

MIT — see [LICENSE](LICENSE).

## Author

[Yuichi Tateno](https://github.com/hotchpotch) (`@hotchpotch`)
