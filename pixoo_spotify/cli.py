from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyOauthError

from pixoo_spotify.app import generate_gif_once, run_app
from pixoo_spotify.config import AppConfig, TextPosition
from pixoo_spotify.dummy import dummy_artwork, dummy_track
from pixoo_spotify.gif import build_gif_bytes, default_font_config, load_font_registry
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.pixoo import discover_devices
from pixoo_spotify.spotify import SpotifyClient, validate_spotify_config

load_dotenv()

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)


def resolve_config(config_path: Path | None, overrides: dict) -> AppConfig:
    if config_path is None:
        default = Path("config.toml")
        config_path = default if default.exists() else None
    return AppConfig.from_sources(config_path, overrides)


def build_overrides(**kwargs) -> dict:
    return {
        "spotify": {
            "client_id": kwargs.get("client_id"),
            "client_secret": kwargs.get("client_secret"),
            "redirect_uri": kwargs.get("redirect_uri"),
            "scope": kwargs.get("scope"),
            "cache_path": kwargs.get("cache_path"),
            "open_browser": kwargs.get("open_browser"),
        },
        "pixoo": {
            "device_ip": kwargs.get("device_ip"),
            "discover": kwargs.get("discover"),
            "play_on_device": kwargs.get("play_on_device"),
        },
        "server": {
            "host": kwargs.get("server_host"),
            "port": kwargs.get("server_port"),
            "public_base_url": kwargs.get("public_base_url"),
        },
        "gif": {
            "size": kwargs.get("gif_size"),
            "fps": kwargs.get("gif_fps"),
            "position": kwargs.get("gif_position"),
            "output_path": kwargs.get("gif_output"),
            "max_chars": kwargs.get("max_chars"),
        },
        "ui": {"background": kwargs.get("background")},
        "poll_interval": kwargs.get("poll_interval"),
    }


@app.command()
def run(
    config: Path | None = typer.Option(None, "--config", help="Config file (toml/json)"),
    client_id: str | None = typer.Option(None, envvar="SPOTIFY_CLIENT_ID"),
    client_secret: str | None = typer.Option(
        None, envvar="SPOTIFY_CLIENT_SECRET", help="Optional (unused for PKCE)"
    ),
    redirect_uri: str | None = typer.Option(None),
    scope: str | None = typer.Option(None),
    cache_path: Path | None = typer.Option(None),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser"),
    device_ip: str | None = typer.Option(None),
    discover: bool = typer.Option(True, "--discover/--no-discover"),
    play_on_device: bool = typer.Option(True, "--play-on-device/--no-play-on-device"),
    server_host: str | None = typer.Option(None),
    server_port: int | None = typer.Option(None),
    public_base_url: str | None = typer.Option(None),
    gif_size: int | None = typer.Option(None),
    gif_fps: int | None = typer.Option(None),
    gif_position: TextPosition | None = typer.Option(None),
    gif_output: Path | None = typer.Option(None),
    max_chars: int | None = typer.Option(None),
    poll_interval: float | None = typer.Option(None),
    background: bool = typer.Option(False, "--background/--foreground"),
) -> None:
    overrides = build_overrides(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        cache_path=cache_path,
        open_browser=open_browser,
        device_ip=device_ip,
        discover=discover,
        play_on_device=play_on_device,
        server_host=server_host,
        server_port=server_port,
        public_base_url=public_base_url,
        gif_size=gif_size,
        gif_fps=gif_fps,
        gif_position=gif_position,
        gif_output=gif_output,
        max_chars=max_chars,
        poll_interval=poll_interval,
        background=background,
    )
    config_obj = resolve_config(config, overrides)
    asyncio.run(run_app(config_obj))


@app.command()
def auth(
    config: Path | None = typer.Option(None, "--config", help="Config file (toml/json)"),
    client_id: str | None = typer.Option(None, envvar="SPOTIFY_CLIENT_ID"),
    client_secret: str | None = typer.Option(
        None, envvar="SPOTIFY_CLIENT_SECRET", help="Optional (unused for PKCE)"
    ),
    redirect_uri: str | None = typer.Option(None),
    scope: str | None = typer.Option(None),
    cache_path: Path | None = typer.Option(None),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser"),
) -> None:
    overrides = build_overrides(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        cache_path=cache_path,
        open_browser=open_browser,
    )
    config_obj = resolve_config(config, overrides)
    validate_spotify_config(config_obj.spotify)
    client = SpotifyClient(config_obj.spotify)
    try:
        client.authorize_interactive()
    except SpotifyOauthError as exc:
        message = str(exc)
        if exc.error_description:
            message = f"{message}\n{exc.error_description}"
        typer.echo("Spotify OAuth error:\n" + message, err=True)
        typer.echo(
            "Check that the Redirect URI is registered exactly in the Spotify dashboard "
            f"(current: {config_obj.spotify.redirect_uri}).",
            err=True,
        )
        raise typer.Exit(code=1) from exc


@app.command()
def devices() -> None:
    async def _discover() -> None:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            devices = await discover_devices(client)
            for device in devices:
                typer.echo(f"{device.device_name} {device.device_private_ip}")

    asyncio.run(_discover())


@app.command()
def demo(
    output: Path = typer.Option(Path("output/demo.gif"), "--output"),
) -> None:
    async def _generate() -> None:
        config = AppConfig()
        config.gif.output_path = output
        track = dummy_track()
        fonts = await load_font_registry(default_font_config(), Path("fonts"))
        gif_bytes = build_gif_bytes(
            track=track,
            config=config.gif,
            fonts=fonts,
            artwork=dummy_artwork(config.gif.size),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(output.write_bytes, gif_bytes)
        typer.echo(f"saved: {output}")

    asyncio.run(_generate())


@app.command()
def gif(
    artist: str = typer.Option(...),
    title: str = typer.Option(...),
    album: str | None = typer.Option(None),
    artwork_url: str | None = typer.Option(None),
    output: Path = typer.Option(Path("output/manual.gif"), "--output"),
) -> None:
    async def _generate() -> None:
        config = AppConfig()
        config.gif.output_path = output
        track = TrackInfo(artist=artist, title=title, album=album, artwork_url=artwork_url)
        await generate_gif_once(config, track)
        typer.echo(f"saved: {output}")

    asyncio.run(_generate())


def main() -> None:
    app()
