from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import spotipy
from pydantic import ValidationError
from spotipy.exceptions import SpotifyException, SpotifyOauthError, SpotifyStateError
from spotipy.oauth2 import start_local_http_server

from pixoo_spotify.config import SpotifyConfig
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.paths import get_auth_paths

logger = logging.getLogger(__name__)


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
        client_kwargs = {"auth_manager": self._auth_manager}
        if config.language:
            client_kwargs["language"] = config.language
        self._client = spotipy.Spotify(**client_kwargs)

    async def current_track(self) -> TrackInfo | None:
        payload = await asyncio.to_thread(self._client.current_user_playing_track)
        try:
            track = TrackInfo.from_spotify(payload)
        except ValidationError:
            logger.debug("Failed to parse current_user_playing_track payload.", exc_info=True)
            track = None
        if track is not None:
            return track
        logger.debug("Fallback to current_playback for metadata.")
        payload = await asyncio.to_thread(self._client.current_playback)
        try:
            return TrackInfo.from_spotify(payload)
        except ValidationError:
            logger.debug("Failed to parse current_playback payload.", exc_info=True)
            return None

    def authorize_interactive(self) -> str:
        if not self._config.open_browser:
            return self._authorize_with_manual_redirect()
        url = self._auth_manager.get_authorize_url()
        print("Opening a browser for Spotify authorization.")
        print("If the redirect does not complete, you can paste the URL here at any time.")
        print(url)
        redirect_info = urlparse(self._config.redirect_uri)
        code: str | None = None
        if (
            redirect_info.scheme == "http"
            and redirect_info.hostname in ("127.0.0.1", "localhost")
            and redirect_info.port
        ):
            code = self._wait_for_local_code(redirect_info.port, url)
        else:
            self._open_browser(url)
        if not code:
            code = self._prompt_for_redirect_code()
        token = self._auth_manager.get_access_token(code=code, check_cache=False)
        if not token:
            raise RuntimeError("Failed to fetch access token.")
        return str(self._config.cache_path)

    def _authorize_with_manual_redirect(self) -> str:
        url = self._auth_manager.get_authorize_url()
        print("Go to the following URL and authorize the app:")
        print(url)
        code = self._prompt_for_redirect_code()
        token = self._auth_manager.get_access_token(code=code, check_cache=False)
        if not token:
            raise RuntimeError("Failed to fetch access token.")
        return str(self._config.cache_path)

    def _prompt_for_redirect_code(self) -> str:
        print("If the redirect did not work, paste the full redirected URL here.")
        redirect = input("Enter the URL you were redirected to: ").strip()
        if not redirect:
            raise RuntimeError("No redirect URL provided.")
        _state, code = self._auth_manager.parse_auth_response_url(redirect)
        if not code:
            raise RuntimeError("Failed to parse authorization code.")
        return code

    def _wait_for_local_code(
        self,
        port: int,
        url: str,
    ) -> str | None:
        server = start_local_http_server(port)
        server.timeout = 1.0
        input_queue: queue.Queue[str] = queue.Queue()

        def _read_input() -> None:
            try:
                redirect = input(
                    "Paste the full redirected URL here (optional), then press Enter: "
                ).strip()
            except EOFError:
                return
            if redirect:
                input_queue.put(redirect)

        try:
            self._open_browser(url)
            threading.Thread(target=_read_input, daemon=True).start()
            while server.auth_code is None and server.error is None:
                server.handle_request()
                try:
                    redirect = input_queue.get_nowait()
                except queue.Empty:
                    redirect = None
                if redirect:
                    _state, code = self._auth_manager.parse_auth_response_url(redirect)
                    if not code:
                        raise RuntimeError("Failed to parse authorization code.")
                    return code
            server_state = getattr(server, "state", None)
            if (
                self._auth_manager.state is not None
                and server_state is not None
                and server_state != self._auth_manager.state
            ):
                raise SpotifyStateError(self._auth_manager.state, server_state)
            if server.auth_code is not None:
                return server.auth_code
            if server.error is not None:
                raise SpotifyOauthError(str(server.error))
            return None
        finally:
            server.server_close()

    @staticmethod
    def _open_browser(url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception:
            pass


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
