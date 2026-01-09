from __future__ import annotations

import asyncio

import spotipy
from pydantic import ValidationError

from pixoo_spotify.config import SpotifyConfig
from pixoo_spotify.models import TrackInfo


class SpotifyClient:
    def __init__(self, config: SpotifyConfig):
        self._config = config
        self._auth_manager = spotipy.SpotifyPKCE(
            client_id=config.client_id,
            redirect_uri=config.redirect_uri,
            scope=config.scope,
            cache_path=str(config.cache_path),
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
