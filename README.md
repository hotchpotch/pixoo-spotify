# pixoo_spotify

pixoo_spotify shows the currently playing Spotify artwork and track info on a Divoom Pixoo64 64x64 Pixel Art LED Display.
Because the artwork is rendered at 64x64, it preserves the pixel art feel nicely.

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

## Fonts (optional)

By default, a bundled 8‑pixel font that supports English and Japanese (Misaki) is used:
https://littlelimit.net/misaki.htm

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

If you run with no options, the app will try to infer the Spotify language from your environment and discover the Pixoo device on your local network. You can also provide all values manually.

## Troubleshooting

When the Pixoo device accesses the server, it needs permission to reach port 18080 on the machine running pixoo_spotify. If the OS firewall blocks this port, allow or open it.

## License

- Source code: MIT

## Author

- Yuichi Tateno (@hotchpotch)
