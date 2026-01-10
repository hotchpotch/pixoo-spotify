from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import uvicorn
from spotipy.exceptions import SpotifyException

from pixoo_spotify.config import AppConfig
from pixoo_spotify.gif import (
    build_gif_bytes,
    default_font_config,
    fetch_artwork,
    load_font_registry,
)
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.pixoo import discover_devices, play_gif
from pixoo_spotify.server import create_app
from pixoo_spotify.spotify import SpotifyClient, retry_after_seconds, validate_spotify_config
from pixoo_spotify.ui import render_track


async def run_app(config: AppConfig) -> None:
    validate_spotify_config(config.spotify)
    gif_path = config.gif.output_path
    gif_path.parent.mkdir(parents=True, exist_ok=True)

    fonts_dir = Path("fonts")
    font_registry = await load_font_registry(default_font_config(), fonts_dir)

    app = create_app(gif_path)
    server_config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)

    spotify = SpotifyClient(config.spotify)
    base_url = config.server.base_url()
    device_ip: str | None = config.pixoo.device_ip

    async with httpx.AsyncClient(timeout=10) as client:
        if not device_ip and config.pixoo.discover:
            devices = await discover_devices(client)
            if devices:
                device_ip = devices[0].device_private_ip

        server_task = asyncio.create_task(server.serve())
        last_signature: str | None = None
        idle_streak = 0
        try:
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
                else:
                    idle_streak += 1
                if idle_streak >= 10:
                    sleep_for = max(config.idle_poll_interval, config.poll_interval)
                else:
                    sleep_for = config.poll_interval
                await asyncio.sleep(sleep_for)
        finally:
            server.should_exit = True
            await server_task


async def generate_gif_once(config: AppConfig, track: TrackInfo) -> Path:
    gif_path = config.gif.output_path
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    fonts_dir = Path("fonts")
    font_registry = await load_font_registry(default_font_config(), fonts_dir)
    artwork = await fetch_artwork(
        str(track.artwork_url) if track.artwork_url else None,
        config.gif.image_size or config.gif.size,
    )
    gif_bytes = build_gif_bytes(track=track, config=config.gif, fonts=font_registry, artwork=artwork)
    await asyncio.to_thread(gif_path.write_bytes, gif_bytes)
    return gif_path
