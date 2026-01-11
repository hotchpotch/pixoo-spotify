from __future__ import annotations

import asyncio
import uuid
from importlib import metadata
from pathlib import Path

import typer
from spotipy.exceptions import SpotifyOauthError

from pixoo_spotify.app import generate_gif_once, run_app
from pixoo_spotify.config import (
    AppConfig,
    DitherMode,
    LogFormat,
    PaletteMode,
    ScrollMode,
    TextPosition,
    UiMode,
)
from pixoo_spotify.dummy import dummy_artwork, dummy_track
from pixoo_spotify.fonts import (
    FUSION_PIXEL_FONT_LICENSE_URL,
    FUSION_PIXEL_FONT_REPO,
    FontInstallError,
    install_font_for_lang,
    install_recommended_fonts,
    validate_lang_code,
)
from pixoo_spotify.gif import build_gif_bytes, load_font_registry
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.net import find_open_port
from pixoo_spotify.paths import get_auth_paths, get_fonts_dir, resolve_pixoo_spotify_config_path
from pixoo_spotify.pixoo import discover_devices
from pixoo_spotify.spotify import (
    SpotifyClient,
    auth_files_exist,
    load_cached_client_id,
    save_client_id,
    validate_spotify_config,
)

PIXOO_SPOTIFY_CONFIG_PATH: Path | None = None
PIXOO_SPOTIFY_VERBOSE: bool = False
DEFAULT_CONFIG = AppConfig()
DEFAULT_TEXT_FORMAT_DISPLAY = DEFAULT_CONFIG.gif.text_format.replace("\n", "\\n")

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
    invoke_without_command=True,
)


def get_version() -> str:
    try:
        return metadata.version("pixoo-spotify")
    except metadata.PackageNotFoundError:
        return "unknown"


@app.callback()
def global_options(
    config_path: Path | None = typer.Option(None, "--config-path", show_default=True),
    verbose: bool = typer.Option(
        False, "--verbose", help="Enable debug logging", show_default=True
    ),
    version: bool = typer.Option(
        False, "--version", help="Show version and exit.", is_eager=True
    ),
) -> None:
    global PIXOO_SPOTIFY_CONFIG_PATH, PIXOO_SPOTIFY_VERBOSE
    if version:
        typer.echo(get_version())
        raise typer.Exit()
    PIXOO_SPOTIFY_CONFIG_PATH = config_path
    PIXOO_SPOTIFY_VERBOSE = verbose


def resolve_config(config_path: Path | None, overrides: dict) -> AppConfig:
    if config_path is None:
        default = Path("config.toml")
        config_path = default if default.exists() else None
    return AppConfig.from_sources(config_path, overrides)


def resolve_config_path(config_path: Path | None) -> Path | None:
    if config_path is None:
        default = Path("config.toml")
        return default if default.exists() else None
    return config_path


def build_overrides(**kwargs) -> dict:
    return {
        "spotify": {
            "client_id": kwargs.get("client_id"),
            "redirect_uri": kwargs.get("redirect_uri"),
            "scope": kwargs.get("scope"),
            "language": kwargs.get("language"),
            "cache_path": kwargs.get("cache_path"),
            "open_browser": kwargs.get("open_browser"),
        },
        "pixoo": {
            "device_ip": kwargs.get("device_ip"),
            "discover": kwargs.get("discover"),
            "play_on_device": kwargs.get("play_on_device"),
            "auto_screen_off": kwargs.get("auto_screen_off"),
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
        "scroll_pause_frames": kwargs.get("scroll_pause_frames"),
        "gif_colors": kwargs.get("gif_colors"),
        "gif_dither": kwargs.get("gif_dither"),
        "gif_palette": kwargs.get("gif_palette"),
        "gif_optimize": kwargs.get("gif_optimize"),
        "text_format": kwargs.get("text_format"),
        "overlay_color": kwargs.get("overlay_color"),
        "text_color": kwargs.get("text_color"),
        "text_shadow_color": kwargs.get("text_shadow_color"),
        "position": kwargs.get("text_position"),
        "output_path": kwargs.get("gif_output"),
            "max_chars": kwargs.get("max_chars"),
        },
        "ui": {
            "mode": kwargs.get("ui_mode"),
            "log_format": kwargs.get("log_format"),
        },
        "poll_interval": kwargs.get("poll_interval"),
        "idle_poll_interval": kwargs.get("idle_poll_interval"),
    }


@app.command(help="Run the Pixoo Spotify GIF server and optional device playback.")
def run(
    config: Path | None = typer.Option(
        None, "--config", help="Config file (toml/json).", show_default=True
    ),
    client_id: str | None = typer.Option(
        None,
        "--client-id",
        help="Override cached Spotify client id (usually not needed).",
        show_default=True,
    ),
    redirect_uri: str | None = typer.Option(
        None,
        help="Redirect URI for Spotify auth (rarely needed for run).",
        show_default=DEFAULT_CONFIG.spotify.redirect_uri,
    ),
    scope: str | None = typer.Option(
        None,
        help="Spotify OAuth scopes (advanced; usually leave default).",
        show_default=DEFAULT_CONFIG.spotify.scope,
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        help="Preferred Spotify metadata language (Accept-Language).",
        show_default=DEFAULT_CONFIG.spotify.language or "auto",
    ),
    cache_path: Path | None = typer.Option(
        None,
        help="Path to Spotify token cache (auto if omitted).",
        show_default=str(DEFAULT_CONFIG.spotify.cache_path),
    ),
    open_browser: bool = typer.Option(
        True,
        "--open-browser/--no-open-browser",
        help="Open browser if re-auth is needed.",
        show_default=True,
    ),
    device_ip: str | None = typer.Option(
        None, help="Pixoo device IP address.", show_default=True
    ),
    discover: bool = typer.Option(
        True,
        "--discover/--no-discover",
        help="Auto-discover Pixoo on LAN.",
        show_default=True,
    ),
    play_on_device: bool = typer.Option(
        True,
        "--play-on-device/--no-play-on-device",
        help="Send GIF to Pixoo.",
        show_default=True,
    ),
    auto_screen_off: bool = typer.Option(
        False,
        "--auto-screen-off/--no-auto-screen-off",
        help="Turn off screen when idle.",
        show_default=True,
    ),
    server_host: str | None = typer.Option(
        None,
        help="HTTP server host (default 0.0.0.0).",
        show_default=DEFAULT_CONFIG.server.host,
    ),
    server_port: int | None = typer.Option(
        None,
        help="HTTP server port (auto-select if omitted).",
        show_default=str(DEFAULT_CONFIG.server.port),
    ),
    public_base_url: str | None = typer.Option(
        None, help="Public base URL used for Pixoo to fetch the GIF.", show_default=True
    ),
    gif_size: int | None = typer.Option(
        None,
        help="GIF canvas size (16/32/64).",
        show_default=str(DEFAULT_CONFIG.gif.size),
    ),
    image_size: int | None = typer.Option(
        None,
        "--image-size",
        help="Artwork source size (16/32/64).",
        show_default="same as --gif-size",
    ),
    gif_fps: int | None = typer.Option(
        None, help="GIF frames per second.", show_default=str(DEFAULT_CONFIG.gif.fps)
    ),
    artwork_only: bool = typer.Option(
        False,
        "--artwork-only/--with-text",
        help="Render only artwork (no text).",
        show_default=True,
    ),
    scroll_mode: ScrollMode | None = typer.Option(
        None,
        "--scroll-mode",
        help="Text scroll mode (loop/bounce).",
        show_default=DEFAULT_CONFIG.gif.scroll_mode.value,
    ),
    scroll_pause_frames: int | None = typer.Option(
        None,
        "--scroll-pause-frames",
        help="Pause frames at bounce edges (loop scroll has no pause).",
        show_default=str(DEFAULT_CONFIG.gif.scroll_pause_frames),
    ),
    gif_colors: int | None = typer.Option(
        None,
        "--gif-colors",
        help="GIF palette size.",
        show_default=str(DEFAULT_CONFIG.gif.gif_colors),
    ),
    gif_dither: DitherMode | None = typer.Option(
        None,
        "--gif-dither",
        help="GIF dither mode.",
        show_default=DEFAULT_CONFIG.gif.gif_dither.value,
    ),
    gif_palette: PaletteMode | None = typer.Option(
        None,
        "--gif-palette",
        help="Palette mode (auto/shared).",
        show_default=DEFAULT_CONFIG.gif.gif_palette.value,
    ),
    gif_optimize: bool | None = typer.Option(
        None,
        "--gif-optimize/--no-gif-optimize",
        help="Enable GIF optimization.",
        show_default=DEFAULT_CONFIG.gif.gif_optimize,
    ),
    text_format: str | None = typer.Option(
        None,
        "--text-format",
        help=(
            "Text template (use {title}, {artist}, {album}; up to 3 lines). "
            'Example: --text-format "{artist}\\n{title}\\n{album}"'
        ),
        show_default=DEFAULT_TEXT_FORMAT_DISPLAY,
    ),
    overlay_color: str | None = typer.Option(
        None,
        "--overlay-color",
        help="Overlay color in #RRGGBBAA.",
        show_default=DEFAULT_CONFIG.gif.overlay_color or "none",
    ),
    text_color: str | None = typer.Option(
        None,
        "--text-color",
        help="Text color in #RRGGBBAA.",
        show_default=DEFAULT_CONFIG.gif.text_color,
    ),
    text_shadow_color: str | None = typer.Option(
        None,
        "--text-shadow-color",
        help="Text shadow color in #RRGGBBAA.",
        show_default=DEFAULT_CONFIG.gif.text_shadow_color,
    ),
    text_position: TextPosition | None = typer.Option(
        None,
        "--text-position",
        help="Text position on the canvas.",
        show_default=DEFAULT_CONFIG.gif.position.value,
    ),
    gif_output: Path | None = typer.Option(
        None,
        help="Output path for generated GIF.",
        show_default=str(DEFAULT_CONFIG.gif.output_path),
    ),
    max_chars: int | None = typer.Option(
        None, help="Max characters per line.", show_default=str(DEFAULT_CONFIG.gif.max_chars)
    ),
    poll_interval: float | None = typer.Option(
        None, help="Polling interval seconds.", show_default=str(DEFAULT_CONFIG.poll_interval)
    ),
    idle_poll_interval: float | None = typer.Option(
        None,
        "--idle-poll-interval",
        help="Polling interval when idle.",
        show_default=str(DEFAULT_CONFIG.idle_poll_interval),
    ),
    ui_mode: UiMode = typer.Option(
        UiMode.rich, "--ui", help="UI mode (rich/text).", show_default=True
    ),
    log_format: LogFormat = typer.Option(
        LogFormat.simple, "--log-format", help="Log format (simple/basic).", show_default=True
    ),
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
        redirect_uri=redirect_uri,
        scope=scope,
        language=language,
        cache_path=cache_path,
        open_browser=open_browser,
        device_ip=device_ip,
        discover=discover,
        play_on_device=play_on_device,
        auto_screen_off=auto_screen_off,
        server_host=server_host,
        server_port=server_port,
        public_base_url=public_base_url,
        gif_size=gif_size,
        image_size=image_size,
        gif_fps=gif_fps,
        artwork_only=artwork_only,
        scroll_mode=scroll_mode,
        scroll_pause_frames=scroll_pause_frames,
        gif_colors=gif_colors,
        gif_dither=gif_dither,
        gif_palette=gif_palette,
        gif_optimize=gif_optimize,
        text_format=text_format,
        overlay_color=overlay_color,
        text_color=text_color,
        text_shadow_color=text_shadow_color,
        text_position=text_position,
        gif_output=gif_output,
        max_chars=max_chars,
        poll_interval=poll_interval,
        idle_poll_interval=idle_poll_interval,
        ui_mode=ui_mode,
        log_format=log_format,
    )
    config_obj = resolve_config(config, overrides)
    if server_port is None and resolve_config_path(config) is None:
        candidate = find_open_port(config_obj.server.host, 18080, 18099)
        if candidate is not None:
            config_obj.server = config_obj.server.model_copy(update={"port": candidate})
            typer.echo(f"Using available port {candidate} (auto-selected).")
    asyncio.run(run_app(config_obj, verbose=PIXOO_SPOTIFY_VERBOSE))


@app.command()
def auth(
    config: Path | None = typer.Option(
        None, "--config", help="Config file (toml/json)", show_default=True
    ),
    client_id: str = typer.Option(..., "--client-id", show_default=True),
    redirect_uri: str | None = typer.Option(
        None, show_default=DEFAULT_CONFIG.spotify.redirect_uri
    ),
    scope: str | None = typer.Option(None, show_default=DEFAULT_CONFIG.spotify.scope),
    cache_path: Path | None = typer.Option(
        None, show_default=str(DEFAULT_CONFIG.spotify.cache_path)
    ),
    open_browser: bool = typer.Option(
        True, "--open-browser/--no-open-browser", show_default=True
    ),
    reauth: bool = typer.Option(False, "--reauth", show_default=True),
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


@app.command("font-install")
def font_install(
    lang: str | None = typer.Option(
        None,
        "--lang",
        help="Language code (e.g. ja, en, zh-cn) or fallback",
        show_default=True,
    ),
    font_path: Path | None = typer.Option(
        None, "--font-path", help="Path to a .ttf/.otf font", show_default=True
    ),
) -> None:
    config_path = resolve_pixoo_spotify_config_path(PIXOO_SPOTIFY_CONFIG_PATH)
    fonts_dir = get_fonts_dir(config_path)

    if lang or font_path:
        if not lang or not font_path:
            typer.echo("Both --lang and --font-path are required for manual install.", err=True)
            raise typer.Exit(code=1)
        if not validate_lang_code(lang):
            typer.echo(f"Unsupported language code: {lang}", err=True)
            raise typer.Exit(code=1)
        try:
            dest = install_font_for_lang(fonts_dir, lang, font_path)
        except FontInstallError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Installed font for {lang}: {dest}")
        return

    typer.echo(
        "This will download the recommended Fusion Pixel Font (OFL-1.1).\n"
        f"Please review the license at {FUSION_PIXEL_FONT_LICENSE_URL}\n"
        f"Repository: {FUSION_PIXEL_FONT_REPO}\n"
        "Do you accept the license and want to install? (y/N): ",
        nl=False,
    )
    answer = input().strip().lower()
    if answer not in ("y", "yes"):
        typer.echo("Canceled.")
        raise typer.Exit(code=1)

    try:
        installed, asset_name, tag = asyncio.run(install_recommended_fonts(fonts_dir))
    except FontInstallError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    tag_display = f" ({tag})" if tag else ""
    typer.echo(f"Downloaded {asset_name}{tag_display}")
    for lang_code, path in sorted(installed.items()):
        typer.echo(f"- {lang_code}: {path}")


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
    output: Path = typer.Option(
        Path("output/demo.gif"), "--output", show_default="output/demo.gif"
    ),
    image_size: int | None = typer.Option(
        None, "--image-size", show_default="same as --gif-size"
    ),
    text_color: str | None = typer.Option(
        None, "--text-color", show_default=DEFAULT_CONFIG.gif.text_color
    ),
    text_shadow_color: str | None = typer.Option(
        None, "--text-shadow-color", show_default=DEFAULT_CONFIG.gif.text_shadow_color
    ),
    artwork_only: bool = typer.Option(
        False, "--artwork-only/--with-text", show_default=DEFAULT_CONFIG.gif.artwork_only
    ),
    gif_colors: int | None = typer.Option(
        None, "--gif-colors", show_default=str(DEFAULT_CONFIG.gif.gif_colors)
    ),
    gif_dither: DitherMode | None = typer.Option(
        None, "--gif-dither", show_default=DEFAULT_CONFIG.gif.gif_dither.value
    ),
    gif_palette: PaletteMode | None = typer.Option(
        None, "--gif-palette", show_default=DEFAULT_CONFIG.gif.gif_palette.value
    ),
    gif_optimize: bool | None = typer.Option(
        None,
        "--gif-optimize/--no-gif-optimize",
        show_default=DEFAULT_CONFIG.gif.gif_optimize,
    ),
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
        fonts_dir = Path(config.spotify.cache_path).parent / "fonts"
        fonts = await load_font_registry(fonts_dir)
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
    artist: str = typer.Option(..., show_default=True),
    title: str = typer.Option(..., show_default=True),
    album: str | None = typer.Option(None, show_default=True),
    artwork_url: str | None = typer.Option(None, show_default=True),
    output: Path = typer.Option(
        Path("output/manual.gif"), "--output", show_default="output/manual.gif"
    ),
    image_size: int | None = typer.Option(
        None, "--image-size", show_default="same as --gif-size"
    ),
    text_color: str | None = typer.Option(
        None, "--text-color", show_default=DEFAULT_CONFIG.gif.text_color
    ),
    text_shadow_color: str | None = typer.Option(
        None, "--text-shadow-color", show_default=DEFAULT_CONFIG.gif.text_shadow_color
    ),
    artwork_only: bool = typer.Option(
        False, "--artwork-only/--with-text", show_default=DEFAULT_CONFIG.gif.artwork_only
    ),
    gif_colors: int | None = typer.Option(
        None, "--gif-colors", show_default=str(DEFAULT_CONFIG.gif.gif_colors)
    ),
    gif_dither: DitherMode | None = typer.Option(
        None, "--gif-dither", show_default=DEFAULT_CONFIG.gif.gif_dither.value
    ),
    gif_palette: PaletteMode | None = typer.Option(
        None, "--gif-palette", show_default=DEFAULT_CONFIG.gif.gif_palette.value
    ),
    gif_optimize: bool | None = typer.Option(
        None,
        "--gif-optimize/--no-gif-optimize",
        show_default=DEFAULT_CONFIG.gif.gif_optimize,
    ),
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
