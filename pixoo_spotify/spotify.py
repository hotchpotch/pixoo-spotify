from __future__ import annotations

import asyncio
import json
from pathlib import Path

import spotipy
from pydantic import ValidationError
from spotipy.exceptions import SpotifyException

from pixoo_spotify.config import SpotifyConfig
from pixoo_spotify.models import TrackInfo

CLIENT_ID_CACHE_PATH = Path(".cache/spotify_client.json")

class SpotifyClient:
    def __init__(self, config: SpotifyConfig):
        self._config = config
        cache_path = Path(config.cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._auth_manager = spotipy.SpotifyPKCE(
            client_id=config.client_id,
            redirect_uri=config.redirect_uri,
            scope=config.scope,
            cache_path=str(cache_path),
            open_browser=config.open_browser,
        )
        self._client = spotipy.Spotify(auth_manager=self._auth_manager)

    async def current_track(self) -> TrackInfo | None:
        payload = await asyncio.to_thread(self._client.current_user_playing_track)
        try:
            return TrackInfo.from_spotify(payload)
        except ValidationError:
            return None

    def authorize_interactive(self) -> None:
        token = self._auth_manager.get_access_token()
        if not token:
            raise RuntimeError("Failed to fetch access token.")


def validate_spotify_config(config: SpotifyConfig) -> None:
    missing = [
        name
        for name, value in {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing Spotify configuration: {', '.join(missing)}")


def retry_after_seconds(exc: SpotifyException) -> float | None:
    header = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def load_cached_client_id(path: Path | None = None) -> str | None:
    cache_path = path or CLIENT_ID_CACHE_PATH
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(payload, dict):
        client_id = payload.get("client_id")
        if isinstance(client_id, str) and client_id.strip():
            return client_id.strip()
    return None


def save_client_id(client_id: str, path: Path | None = None) -> Path:
    cache_path = path or CLIENT_ID_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"client_id": client_id}), encoding="utf-8")
    return cache_path
