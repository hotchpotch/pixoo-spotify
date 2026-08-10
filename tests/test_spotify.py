import asyncio

import pytest
import spotipy
from pixoo_spotify.config import ServerConfig, SpotifyConfig
from pixoo_spotify.paths import get_auth_paths, resolve_pixoo_spotify_config_path
from pixoo_spotify.spotify import (
    SpotifyClient,
    SpotifyReauthenticationRequired,
    auth_files_exist,
    load_cached_client_id,
    retry_after_seconds,
    save_client_id,
)
from pydantic import HttpUrl, TypeAdapter
from spotipy.exceptions import SpotifyException, SpotifyOauthError


def test_spotify_cache_dir_created(tmp_path, monkeypatch) -> None:
    created = {}

    class DummyPKCE:
        def __init__(self, **kwargs):
            created["cache_handler"] = kwargs.get("cache_handler")

    class DummySpotify:
        def __init__(self, **kwargs):
            self.auth_manager = kwargs.get("auth_manager")

    monkeypatch.setattr(spotipy, "SpotifyPKCE", DummyPKCE)
    monkeypatch.setattr(spotipy, "Spotify", DummySpotify)

    cache_path = tmp_path / "cache" / "spotify_token.json"
    config = SpotifyConfig(client_id="dummy", cache_path=cache_path)
    SpotifyClient(config)

    assert cache_path.parent.exists()
    assert created["cache_handler"].cache_path == str(cache_path)


def test_current_track_requires_reauthentication_without_token_cache(
    tmp_path, monkeypatch
) -> None:
    cache_path = tmp_path / "spotify_token.json"
    config = SpotifyConfig(client_id="client-123", cache_path=cache_path)
    client = SpotifyClient(config)

    api_called = False

    def current_user_playing_track():
        nonlocal api_called
        api_called = True

    monkeypatch.setattr(client._client, "current_user_playing_track", current_user_playing_track)

    with pytest.raises(SpotifyReauthenticationRequired) as exc_info:
        asyncio.run(client.current_track())

    assert exc_info.value.reason == "missing"
    assert api_called is False


def test_current_track_discards_expired_refresh_token(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "spotify_token.json"
    cache_path.write_text(
        '{"access_token": "expired", "refresh_token": "expired"}', encoding="utf-8"
    )
    config = SpotifyConfig(client_id="client-123", cache_path=cache_path)
    client = SpotifyClient(config)

    def raise_invalid_grant():
        raise SpotifyOauthError("refresh failed", error="invalid_grant")

    monkeypatch.setattr(client._client, "current_user_playing_track", raise_invalid_grant)

    with pytest.raises(SpotifyReauthenticationRequired) as exc_info:
        asyncio.run(client.current_track())

    assert exc_info.value.reason == "expired"
    assert exc_info.value.cache_discarded is True
    assert cache_path.exists() is False


def test_current_track_preserves_cache_for_other_oauth_errors(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "spotify_token.json"
    cache_path.write_text(
        '{"access_token": "current", "refresh_token": "still-valid"}', encoding="utf-8"
    )
    config = SpotifyConfig(client_id="client-123", cache_path=cache_path)
    client = SpotifyClient(config)

    def raise_access_denied():
        raise SpotifyOauthError("access denied", error="access_denied")

    monkeypatch.setattr(client._client, "current_user_playing_track", raise_access_denied)

    with pytest.raises(SpotifyOauthError):
        asyncio.run(client.current_track())

    assert cache_path.exists() is True


def test_server_base_url_trims_trailing_slash() -> None:
    url = TypeAdapter(HttpUrl).validate_python("http://example.com/")
    config = ServerConfig(public_base_url=url)
    assert config.base_url() == "http://example.com"


def test_retry_after_seconds_parses_header() -> None:
    exc = SpotifyException(
        http_status=429,
        code=-1,
        msg="rate limited",
        headers={"Retry-After": "5"},
    )
    assert retry_after_seconds(exc) == 5.0


def test_client_id_cache_roundtrip(tmp_path) -> None:
    config_path = tmp_path / "config"
    assert load_cached_client_id(config_path) is None
    save_client_id("client-123", config_path)
    assert load_cached_client_id(config_path) == "client-123"


def test_resolve_config_paths(tmp_path) -> None:
    resolved = resolve_pixoo_spotify_config_path(tmp_path)
    assert resolved == tmp_path
    auth_path, token_path = get_auth_paths(tmp_path)
    assert auth_path.name == "auth_spotify_client.json"
    assert token_path.name == "spotify_token.json"


def test_auth_files_exist(tmp_path) -> None:
    assert auth_files_exist(tmp_path) is False
    save_client_id("client-123", tmp_path)
    assert auth_files_exist(tmp_path) is True
