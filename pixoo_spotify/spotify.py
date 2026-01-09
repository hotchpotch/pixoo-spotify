from __future__ import annotations

import asyncio
import json
from pathlib import Path

import spotipy
from platformdirs import user_config_dir
from pydantic import ValidationError
from spotipy.exceptions import SpotifyException

from pixoo_spotify.config import SpotifyConfig
from pixoo_spotify.models import TrackInfo

PIXOO_SPOTIFY_CONFIG_APP_NAME = "pixoo-spotify"
AUTH_CLIENT_FILE_NAME = "auth_spotify_client.json"
SPOTIFY_TOKEN_FILE_NAME = "spotify_token.json"


def resolve_pixoo_spotify_config_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    return Path(user_config_dir(PIXOO_SPOTIFY_CONFIG_APP_NAME))


def get_auth_paths(config_path: Path | None = None) -> tuple[Path, Path]:
    base_path = resolve_pixoo_spotify_config_path(config_path)
    return (base_path / AUTH_CLIENT_FILE_NAME, base_path / SPOTIFY_TOKEN_FILE_NAME)


def resolve_spotify_token_path(config_path: Path | None = None) -> Path:
    return get_auth_paths(config_path)[1]

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

    def authorize_interactive(self) -> str:
        if not self._config.open_browser:
            url = self._auth_manager.get_authorize_url()
            print("Go to the following URL and authorize the app:")
            print(url)
            redirect = input("Enter the URL you were redirected to: ").strip()
            if not redirect:
                raise RuntimeError("No redirect URL provided.")
            _state, code = self._auth_manager.parse_auth_response_url(redirect)
            if not code:
                raise RuntimeError("Failed to parse authorization code.")
            token = self._auth_manager.get_access_token(code=code)
        else:
            token = self._auth_manager.get_access_token()
        if not token:
            raise RuntimeError("Failed to fetch access token.")
        return str(self._config.cache_path)


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


def load_cached_client_id(config_path: Path | None = None) -> str | None:
    auth_path, _token_path = get_auth_paths(config_path)
    if not auth_path.exists():
        return None
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(payload, dict):
        client_id = payload.get("client_id")
        if isinstance(client_id, str) and client_id.strip():
            return client_id.strip()
    return None


def save_client_id(client_id: str, config_path: Path | None = None) -> Path:
    auth_path, _token_path = get_auth_paths(config_path)
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps({"client_id": client_id}), encoding="utf-8")
    return auth_path


def auth_files_exist(config_path: Path | None = None) -> bool:
    auth_path, token_path = get_auth_paths(config_path)
    return auth_path.exists() or token_path.exists()
