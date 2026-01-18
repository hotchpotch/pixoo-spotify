from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx
from requests.exceptions import RequestException
from spotipy.exceptions import SpotifyException

from pixoo_spotify.config import AppConfig, UiMode
from pixoo_spotify.gif import build_gif_bytes, fetch_artwork, load_font_registry
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.net import local_ip_for_target
from pixoo_spotify.pixoo import discover_devices, play_gif, set_screen, stop_gif
from pixoo_spotify.server import GifHttpServer
from pixoo_spotify.spotify import SpotifyClient, retry_after_seconds, validate_spotify_config
from pixoo_spotify.ui import (
    configure_logging,
    render_track,
    start_ui,
    stop_ui,
    update_status,
)

logger = logging.getLogger(__name__)


async def run_app(config: AppConfig, *, verbose: bool = False) -> None:
    ui = None
    background = config.ui.mode == UiMode.text
    if not background:
        ui = start_ui()
    configure_logging(background, verbose, ui, config.ui.log_format)

    try:
        validate_spotify_config(config.spotify)
        if config.spotify.language:
            logger.info("Spotify language: %s", config.spotify.language)
        else:
            logger.info("Spotify language: default (no explicit language)")
        gif_path = config.gif.output_path
        gif_path.parent.mkdir(parents=True, exist_ok=True)

        fonts_dir = Path(config.spotify.cache_path).parent / "fonts"
        font_registry = await load_font_registry(fonts_dir)

        server = GifHttpServer(gif_path, config.server.host, config.server.port)

        spotify = SpotifyClient(config.spotify)
        device_ip: str | None = config.pixoo.device_ip
        auto_device_ip = False
        pixoo_error = False
        if device_ip:
            logger.info("Pixoo device IP (configured): %s", device_ip)

        async with httpx.AsyncClient(timeout=10) as client:
            if not device_ip and config.pixoo.discover:
                devices = await discover_devices(client)
                if devices:
                    device = devices[0]
                    device_ip = device.device_private_ip
                    auto_device_ip = True
                    logger.info("Pixoo device discovered: %s (%s)", device.device_name, device_ip)

            base_url = config.server.base_url()
            auto_base_url = False
            if config.server.public_base_url is None and device_ip:
                local_ip = local_ip_for_target(device_ip)
                if local_ip:
                    base_url = f"http://{local_ip}:{config.server.port}"
                    auto_base_url = True
                    logger.info("Resolved local base URL for Pixoo: %s", base_url)
            if config.server.public_base_url is not None:
                logger.info("Using configured public base URL: %s", base_url)

            def format_pixoo_status() -> str:
                if not config.pixoo.play_on_device:
                    return "disabled"
                if device_ip is None:
                    if config.pixoo.discover:
                        return "not found"
                    return "not configured"
                source = "auto" if auto_device_ip else "configured"
                state = "error" if pixoo_error else "ok"
                return f"{device_ip} ({source}, {state})"

            def update_ui_status() -> None:
                update_status(format_pixoo_status(), base_url)

            async def refresh_pixoo_endpoints(reason: str, *, log_info: bool = False) -> None:
                nonlocal device_ip, base_url, auto_base_url, auto_device_ip
                if not config.pixoo.discover:
                    if log_info:
                        logger.info("Pixoo rediscovery skipped (discover disabled).")
                    return
                if not (auto_device_ip or device_ip is None):
                    if log_info:
                        logger.info("Pixoo rediscovery skipped (device IP configured).")
                    return
                if log_info:
                    logger.info("Attempting Pixoo rediscovery after %s.", reason)
                try:
                    devices = await discover_devices(client)
                except httpx.HTTPError as exc:
                    if log_info:
                        logger.info("Pixoo rediscovery failed after %s: %s", reason, exc)
                    else:
                        logger.debug(
                            "Failed to rediscover Pixoo devices after %s: %s", reason, exc
                        )
                    return
                if not devices:
                    message = "Pixoo rediscovery found no devices after %s; keeping %s"
                    if log_info:
                        logger.info(message, reason, device_ip or "none")
                    else:
                        logger.debug(message, reason, device_ip or "none")
                    return
                device = devices[0]
                new_ip = device.device_private_ip
                if new_ip and (auto_device_ip or device_ip is None) and new_ip != device_ip:
                    device_ip = new_ip
                    auto_device_ip = True
                    logger.info(
                        "Pixoo device rediscovered: %s (%s)", device.device_name, device_ip
                    )
                elif log_info:
                    logger.info(
                        "Pixoo device unchanged after %s: %s", reason, device_ip or "none"
                    )
                if config.server.public_base_url is None and device_ip:
                    local_ip = local_ip_for_target(device_ip)
                    if local_ip:
                        new_base_url = f"http://{local_ip}:{config.server.port}"
                        if new_base_url != base_url:
                            base_url = new_base_url
                            auto_base_url = True
                            logger.info("Updated local base URL for Pixoo: %s", base_url)
                        elif log_info:
                            logger.info("Local base URL unchanged after %s: %s", reason, base_url)
                update_ui_status()

            async def refresh_pixoo_on_request_error(
                exc: httpx.HTTPError, reason: str
            ) -> None:
                nonlocal pixoo_error
                pixoo_error = True
                update_ui_status()
                if isinstance(exc, httpx.RequestError):
                    await refresh_pixoo_endpoints(reason)

            update_ui_status()
            server.start()
            last_signature: str | None = None
            last_playing = False
            screen_initialized = False
            idle_streak = 0
            try:
                while True:
                    try:
                        track = await spotify.current_track()
                    except SpotifyException as exc:
                        if exc.http_status == 429:
                            retry_after = retry_after_seconds(exc) or config.poll_interval
                            await asyncio.sleep(retry_after)
                            continue
                        raise
                    except RequestException as exc:
                        logger.warning("Spotify request failed: %s", exc)
                        logger.debug("Spotify request failed details.", exc_info=True)
                        await asyncio.sleep(config.poll_interval)
                        continue
                    if track and track.is_playing:
                        if config.pixoo.play_on_device and device_ip and config.pixoo.auto_screen_off:
                            if not last_playing or not screen_initialized:
                                try:
                                    await set_screen(client, device_ip, True)
                                    logger.info("Pixoo screen ON")
                                    pixoo_error = False
                                    update_ui_status()
                                except httpx.HTTPError as exc:
                                    logger.debug("Failed to turn on Pixoo screen.")
                                    await refresh_pixoo_on_request_error(exc, "screen_on")
                            screen_initialized = True
                        signature = f"{track.id}:{track.title}:{track.artist}"
                        if signature != last_signature:
                            if config.pixoo.play_on_device and (device_ip is None or pixoo_error):
                                await refresh_pixoo_endpoints("track_change", log_info=True)
                            artwork = await fetch_artwork(
                                str(track.artwork_url) if track.artwork_url else None
                            )
                            gif_bytes = build_gif_bytes(
                                track=track,
                                config=config.gif,
                                fonts=font_registry,
                                artwork=artwork,
                            )
                            await asyncio.to_thread(gif_path.write_bytes, gif_bytes)
                            if config.pixoo.play_on_device and device_ip:
                                epoch = int(time.time())
                                try:
                                    await play_gif(
                                        client,
                                        device_ip,
                                        f"{base_url.rstrip('/')}/spotify_gif?{epoch}",
                                    )
                                    pixoo_error = False
                                    update_ui_status()
                                except httpx.HTTPError as exc:
                                    logger.warning("Failed to send Pixoo GIF: %s", exc)
                                    logger.debug("Pixoo GIF send failed details.", exc_info=True)
                                    await refresh_pixoo_on_request_error(exc, "play_gif")
                            render_track(track)
                            last_signature = signature
                        idle_streak = 0
                        last_playing = True
                    else:
                        if (
                            config.pixoo.play_on_device
                            and device_ip
                            and config.pixoo.auto_screen_off
                            and not screen_initialized
                        ):
                            try:
                                await set_screen(client, device_ip, False)
                                logger.info("Pixoo screen OFF (idle at startup)")
                                pixoo_error = False
                                update_ui_status()
                            except httpx.HTTPError as exc:
                                logger.debug("Failed to turn off Pixoo screen on start.")
                                await refresh_pixoo_on_request_error(exc, "screen_off_start")
                            screen_initialized = True
                        if last_playing and config.pixoo.play_on_device and device_ip:
                            if config.pixoo.auto_screen_off:
                                try:
                                    await set_screen(client, device_ip, False)
                                    logger.info("Pixoo screen OFF")
                                    pixoo_error = False
                                    update_ui_status()
                                except httpx.HTTPError as exc:
                                    logger.debug("Failed to turn off Pixoo screen.")
                                    await refresh_pixoo_on_request_error(exc, "screen_off")
                            else:
                                try:
                                    await stop_gif(client, device_ip)
                                    logger.info("Pixoo display reset (stop GIF)")
                                    pixoo_error = False
                                    update_ui_status()
                                except httpx.HTTPError as exc:
                                    logger.debug("Failed to stop Pixoo GIF.")
                                    await refresh_pixoo_on_request_error(exc, "stop_gif")
                        last_signature = None
                        last_playing = False
                        idle_streak += 1
                    if idle_streak >= 10:
                        sleep_for = max(config.idle_poll_interval, config.poll_interval)
                    else:
                        sleep_for = config.poll_interval
                    await asyncio.sleep(sleep_for)
            finally:
                if config.pixoo.play_on_device and device_ip:
                    if config.pixoo.auto_screen_off:
                        try:
                            await set_screen(client, device_ip, False)
                            logger.info("Pixoo screen OFF (shutdown)")
                            pixoo_error = False
                            update_ui_status()
                        except httpx.HTTPError as exc:
                            logger.debug("Failed to turn off Pixoo screen on shutdown.")
                            await refresh_pixoo_on_request_error(exc, "screen_off_shutdown")
                    else:
                        try:
                            await stop_gif(client, device_ip)
                            logger.info("Pixoo display reset (shutdown)")
                            pixoo_error = False
                            update_ui_status()
                        except httpx.HTTPError as exc:
                            logger.debug("Failed to stop Pixoo GIF on shutdown.")
                            await refresh_pixoo_on_request_error(exc, "stop_gif_shutdown")
                server.stop()
    finally:
        if ui is not None:
            stop_ui()


async def generate_gif_once(config: AppConfig, track: TrackInfo) -> Path:
    gif_path = config.gif.output_path
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    fonts_dir = Path(config.spotify.cache_path).parent / "fonts"
    font_registry = await load_font_registry(fonts_dir)
    artwork = await fetch_artwork(str(track.artwork_url) if track.artwork_url else None)
    gif_bytes = build_gif_bytes(track=track, config=config.gif, fonts=font_registry, artwork=artwork)
    await asyncio.to_thread(gif_path.write_bytes, gif_bytes)
    return gif_path
