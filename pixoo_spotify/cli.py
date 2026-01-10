from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import typer
from spotipy.exceptions import SpotifyOauthError

from pixoo_spotify.app import generate_gif_once, run_app
from pixoo_spotify.config import AppConfig, DitherMode, PaletteMode, ScrollMode, TextPosition
from pixoo_spotify.dummy import dummy_artwork, dummy_track
from pixoo_spotify.gif import build_gif_bytes, default_font_config, load_font_registry
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.pixoo import discover_devices
from pixoo_spotify.spotify import (
    SpotifyClient,
    auth_files_exist,
    get_auth_paths,
    load_cached_client_id,
    resolve_pixoo_spotify_config_path,
    save_client_id,
    validate_spotify_config,
)

PIXOO_SPOTIFY_CONFIG_PATH: Path | None = None

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)


@app.callback()
def global_options(
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    global PIXOO_SPOTIFY_CONFIG_PATH
    PIXOO_SPOTIFY_CONFIG_PATH = config_path


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
            "image_size": kwargs.get("image_size"),
        "fps": kwargs.get("gif_fps"),
        "artwork_only": kwargs.get("artwork_only"),
        "scroll_mode": kwargs.get("scroll_mode"),
        "bounce_pause_frames": kwargs.get("bounce_pause_frames"),
        "gif_colors": kwargs.get("gif_colors"),
        "gif_dither": kwargs.get("gif_dither"),
        "gif_palette": kwargs.get("gif_palette"),
        "gif_optimize": kwargs.get("gif_optimize"),
        "overlay_color": kwargs.get("overlay_color"),
        "text_color": kwargs.get("text_color"),
        "text_shadow_color": kwargs.get("text_shadow_color"),
        "position": kwargs.get("gif_position"),
        "output_path": kwargs.get("gif_output"),
            "max_chars": kwargs.get("max_chars"),
        },
        "ui": {"background": kwargs.get("background")},
        "poll_interval": kwargs.get("poll_interval"),
        "idle_poll_interval": kwargs.get("idle_poll_interval"),
    }


@app.command()
def run(
    config: Path | None = typer.Option(None, "--config", help="Config file (toml/json)"),
    client_id: str | None = typer.Option(None, "--client-id"),
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
    image_size: int | None = typer.Option(None, "--image-size"),
    gif_fps: int | None = typer.Option(None),
    artwork_only: bool = typer.Option(False, "--artwork-only/--with-text"),
    scroll_mode: ScrollMode | None = typer.Option(None, "--scroll-mode"),
    bounce_pause_frames: int | None = typer.Option(None, "--bounce-pause-frames"),
    gif_colors: int | None = typer.Option(None, "--gif-colors"),
    gif_dither: DitherMode | None = typer.Option(None, "--gif-dither"),
    gif_palette: PaletteMode | None = typer.Option(None, "--gif-palette"),
    gif_optimize: bool | None = typer.Option(None, "--gif-optimize/--no-gif-optimize"),
    overlay_color: str | None = typer.Option(None, "--overlay-color"),
    text_color: str | None = typer.Option(None, "--text-color"),
    text_shadow_color: str | None = typer.Option(None, "--text-shadow-color"),
    gif_position: TextPosition | None = typer.Option(None),
    gif_output: Path | None = typer.Option(None),
    max_chars: int | None = typer.Option(None),
    poll_interval: float | None = typer.Option(None),
    idle_poll_interval: float | None = typer.Option(None, "--idle-poll-interval"),
    background: bool = typer.Option(False, "--background/--foreground"),
) -> None:
    config_path = resolve_pixoo_spotify_config_path(PIXOO_SPOTIFY_CONFIG_PATH)
    resolved_client_id = client_id or load_cached_client_id(config_path)
    if resolved_client_id is None:
        typer.echo(
            "Spotify client id not found. Run `pixoo-spotify auth --client-id <id>` first.",
            err=True,
        )
        raise typer.Exit(code=1)
    if cache_path is None:
        cache_path = get_auth_paths(config_path)[1]
    overrides = build_overrides(
        client_id=resolved_client_id,
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
        image_size=image_size,
        gif_fps=gif_fps,
        artwork_only=artwork_only,
        scroll_mode=scroll_mode,
        bounce_pause_frames=bounce_pause_frames,
        gif_colors=gif_colors,
        gif_dither=gif_dither,
        gif_palette=gif_palette,
        gif_optimize=gif_optimize,
        overlay_color=overlay_color,
        text_color=text_color,
        text_shadow_color=text_shadow_color,
        gif_position=gif_position,
        gif_output=gif_output,
        max_chars=max_chars,
        poll_interval=poll_interval,
        idle_poll_interval=idle_poll_interval,
        background=background,
    )
    config_obj = resolve_config(config, overrides)
    asyncio.run(run_app(config_obj))


@app.command()
def auth(
    config: Path | None = typer.Option(None, "--config", help="Config file (toml/json)"),
    client_id: str = typer.Option(..., "--client-id"),
    client_secret: str | None = typer.Option(
        None, envvar="SPOTIFY_CLIENT_SECRET", help="Optional (unused for PKCE)"
    ),
    redirect_uri: str | None = typer.Option(None),
    scope: str | None = typer.Option(None),
    cache_path: Path | None = typer.Option(None),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser"),
    reauth: bool = typer.Option(False, "--reauth"),
) -> None:
    config_path = resolve_pixoo_spotify_config_path(PIXOO_SPOTIFY_CONFIG_PATH)
    if auth_files_exist(config_path) and not reauth:
        auth_client_path, token_path = get_auth_paths(config_path)
        typer.echo(
            "Auth files already exist at the config path.\n"
            f"- {auth_client_path}\n"
            f"- {token_path}\n"
            "If you want to re-authenticate, run:\n"
            "  pixoo-spotify auth --reauth",
            err=True,
        )
        raise typer.Exit(code=1)
    save_client_id(client_id, config_path)
    if cache_path is None:
        cache_path = get_auth_paths(config_path)[1]
    final_cache_path = cache_path
    temp_cache_path: Path | None = None
    if reauth:
        temp_cache_path = final_cache_path.with_name(
            f".{final_cache_path.name}.reauth-{uuid.uuid4().hex}"
        )
        cache_path = temp_cache_path
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
        token_path = client.authorize_interactive()
    except SpotifyOauthError as exc:
        if temp_cache_path is not None:
            temp_cache_path.unlink(missing_ok=True)
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
    except Exception:
        if temp_cache_path is not None:
            temp_cache_path.unlink(missing_ok=True)
        raise
    if temp_cache_path is not None:
        try:
            temp_cache_path.replace(final_cache_path)
        except OSError as exc:
            typer.echo(
                "Authentication succeeded, but failed to update the token file at:\n"
                f"{final_cache_path}\n{exc}",
                err=True,
            )
            raise typer.Exit(code=1) from exc
        token_path = str(final_cache_path)
    typer.echo(f"Authentication succeeded. Token saved to: {token_path}")


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
    image_size: int | None = typer.Option(None, "--image-size"),
    text_color: str | None = typer.Option(None, "--text-color"),
    text_shadow_color: str | None = typer.Option(None, "--text-shadow-color"),
    artwork_only: bool = typer.Option(False, "--artwork-only/--with-text"),
    gif_colors: int | None = typer.Option(None, "--gif-colors"),
    gif_dither: DitherMode | None = typer.Option(None, "--gif-dither"),
    gif_palette: PaletteMode | None = typer.Option(None, "--gif-palette"),
    gif_optimize: bool | None = typer.Option(None, "--gif-optimize/--no-gif-optimize"),
) -> None:
    async def _generate() -> None:
        config = AppConfig()
        config.gif.output_path = output
        if image_size is not None:
            config.gif = config.gif.model_copy(update={"image_size": image_size})
        if text_color is not None or text_shadow_color is not None:
            config.gif = config.gif.model_copy(
                update={
                    "text_color": text_color or config.gif.text_color,
                    "text_shadow_color": text_shadow_color or config.gif.text_shadow_color,
                }
            )
        if artwork_only:
            config.gif = config.gif.model_copy(update={"artwork_only": True})
        if (
            gif_colors is not None
            or gif_dither is not None
            or gif_palette is not None
            or gif_optimize is not None
        ):
            config.gif = config.gif.model_copy(
                update={
                    "gif_colors": gif_colors or config.gif.gif_colors,
                    "gif_dither": gif_dither or config.gif.gif_dither,
                    "gif_palette": gif_palette or config.gif.gif_palette,
                    "gif_optimize": gif_optimize
                    if gif_optimize is not None
                    else config.gif.gif_optimize,
                }
            )
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
    image_size: int | None = typer.Option(None, "--image-size"),
    text_color: str | None = typer.Option(None, "--text-color"),
    text_shadow_color: str | None = typer.Option(None, "--text-shadow-color"),
    artwork_only: bool = typer.Option(False, "--artwork-only/--with-text"),
    gif_colors: int | None = typer.Option(None, "--gif-colors"),
    gif_dither: DitherMode | None = typer.Option(None, "--gif-dither"),
    gif_palette: PaletteMode | None = typer.Option(None, "--gif-palette"),
    gif_optimize: bool | None = typer.Option(None, "--gif-optimize/--no-gif-optimize"),
) -> None:
    async def _generate() -> None:
        config = AppConfig()
        config.gif.output_path = output
        if image_size is not None:
            config.gif = config.gif.model_copy(update={"image_size": image_size})
        if text_color is not None or text_shadow_color is not None:
            config.gif = config.gif.model_copy(
                update={
                    "text_color": text_color or config.gif.text_color,
                    "text_shadow_color": text_shadow_color or config.gif.text_shadow_color,
                }
            )
        if artwork_only:
            config.gif = config.gif.model_copy(update={"artwork_only": True})
        if (
            gif_colors is not None
            or gif_dither is not None
            or gif_palette is not None
            or gif_optimize is not None
        ):
            config.gif = config.gif.model_copy(
                update={
                    "gif_colors": gif_colors or config.gif.gif_colors,
                    "gif_dither": gif_dither or config.gif.gif_dither,
                    "gif_palette": gif_palette or config.gif.gif_palette,
                    "gif_optimize": gif_optimize
                    if gif_optimize is not None
                    else config.gif.gif_optimize,
                }
            )
        track = TrackInfo(artist=artist, title=title, album=album, artwork_url=artwork_url)
        await generate_gif_once(config, track)
        typer.echo(f"saved: {output}")

    asyncio.run(_generate())


def main() -> None:
    app()
