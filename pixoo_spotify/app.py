from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import uvicorn
from spotipy.exceptions import SpotifyException

from pixoo_spotify.config import AppConfig
from pixoo_spotify.gif import build_gif_bytes, fetch_artwork, load_font_registry
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.net import local_ip_for_target
from pixoo_spotify.pixoo import discover_devices, play_gif, set_screen, stop_gif
from pixoo_spotify.server import create_app
from pixoo_spotify.spotify import SpotifyClient, retry_after_seconds, validate_spotify_config
from pixoo_spotify.ui import render_track

logger = logging.getLogger(__name__)


async def run_app(config: AppConfig) -> None:
    validate_spotify_config(config.spotify)
    gif_path = config.gif.output_path
    gif_path.parent.mkdir(parents=True, exist_ok=True)

    fonts_dir = Path(config.spotify.cache_path).parent / "fonts"
    font_registry = await load_font_registry(fonts_dir)

    app = create_app(gif_path)
    server_config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)

    spotify = SpotifyClient(config.spotify)
    device_ip: str | None = config.pixoo.device_ip

    async with httpx.AsyncClient(timeout=10) as client:
        if not device_ip and config.pixoo.discover:
            devices = await discover_devices(client)
            if devices:
                device_ip = devices[0].device_private_ip
                logger.debug("Discovered Pixoo device: %s", device_ip)

        base_url = config.server.base_url()
        if config.server.public_base_url is None and device_ip:
            local_ip = local_ip_for_target(device_ip)
            if local_ip:
                base_url = f"http://{local_ip}:{config.server.port}"
                logger.debug("Resolved local base URL for Pixoo: %s", base_url)

        server_task = asyncio.create_task(server.serve())
        last_signature: str | None = None
        last_playing = False
        idle_streak = 0
        try:
            if config.pixoo.play_on_device and device_ip and config.pixoo.auto_screen_off:
                try:
                    await set_screen(client, device_ip, True)
                except httpx.HTTPError:
                    logger.debug("Failed to turn on Pixoo screen at start.")
            while not server.should_exit:
                try:
                    track = await spotify.current_track()
                except SpotifyException as exc:
                    if exc.http_status == 429:
                        retry_after = retry_after_seconds(exc) or config.poll_interval
                        await asyncio.sleep(retry_after)
                        continue
                    raise
                if track and track.is_playing:
                    if config.pixoo.play_on_device and device_ip and config.pixoo.auto_screen_off:
                        if not last_playing:
                            try:
                                await set_screen(client, device_ip, True)
                            except httpx.HTTPError:
                                logger.debug("Failed to turn on Pixoo screen.")
                    signature = f"{track.id}:{track.title}:{track.artist}"
                    if signature != last_signature:
                        artwork = await fetch_artwork(
                            str(track.artwork_url) if track.artwork_url else None,
                            config.gif.image_size or config.gif.size,
                        )
                        gif_bytes = build_gif_bytes(
                            track=track,
                            config=config.gif,
                            fonts=font_registry,
                            artwork=artwork,
                        )
                        await asyncio.to_thread(gif_path.write_bytes, gif_bytes)
                        if config.pixoo.play_on_device and device_ip:
                            await play_gif(client, device_ip, f"{base_url.rstrip('/')}/gif")
                        if not config.ui.background:
                            render_track(track)
                        last_signature = signature
                    idle_streak = 0
                    last_playing = True
                else:
                    if last_playing and config.pixoo.play_on_device and device_ip:
                        if config.pixoo.auto_screen_off:
                            try:
                                await set_screen(client, device_ip, False)
                            except httpx.HTTPError:
                                logger.debug("Failed to turn off Pixoo screen.")
                        else:
                            try:
                                await stop_gif(client, device_ip)
                            except httpx.HTTPError:
                                logger.debug("Failed to stop Pixoo GIF.")
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
                    except httpx.HTTPError:
                        logger.debug("Failed to turn off Pixoo screen on shutdown.")
                else:
                    try:
                        await stop_gif(client, device_ip)
                    except httpx.HTTPError:
                        logger.debug("Failed to stop Pixoo GIF on shutdown.")
            server.should_exit = True
            await server_task


async def generate_gif_once(config: AppConfig, track: TrackInfo) -> Path:
    gif_path = config.gif.output_path
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    fonts_dir = Path(config.spotify.cache_path).parent / "fonts"
    font_registry = await load_font_registry(fonts_dir)
    artwork = await fetch_artwork(
        str(track.artwork_url) if track.artwork_url else None,
        config.gif.image_size or config.gif.size,
    )
    gif_bytes = build_gif_bytes(track=track, config=config.gif, fonts=font_registry, artwork=artwork)
    await asyncio.to_thread(gif_path.write_bytes, gif_bytes)
    return gif_path
