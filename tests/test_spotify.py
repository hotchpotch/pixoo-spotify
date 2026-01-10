import spotipy
from pixoo_spotify.config import ServerConfig, SpotifyConfig
from pixoo_spotify.paths import get_auth_paths, resolve_pixoo_spotify_config_path
from pixoo_spotify.spotify import (
    SpotifyClient,
    auth_files_exist,
    load_cached_client_id,
    retry_after_seconds,
    save_client_id,
)
from pydantic import HttpUrl, TypeAdapter
from spotipy.exceptions import SpotifyException


def test_spotify_cache_dir_created(tmp_path, monkeypatch) -> None:
    created = {}

    class DummyPKCE:
        def __init__(self, **kwargs):
            created["cache_path"] = kwargs.get("cache_path")

    class DummySpotify:
        def __init__(self, **kwargs):
            self.auth_manager = kwargs.get("auth_manager")

    monkeypatch.setattr(spotipy, "SpotifyPKCE", DummyPKCE)
    monkeypatch.setattr(spotipy, "Spotify", DummySpotify)

    cache_path = tmp_path / "cache" / "spotify_token.json"
    config = SpotifyConfig(client_id="dummy", cache_path=cache_path)
    SpotifyClient(config)

    assert cache_path.parent.exists()
    assert created["cache_path"] == str(cache_path)


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
