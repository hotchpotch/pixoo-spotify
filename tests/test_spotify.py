import spotipy
from pixoo_spotify.config import ServerConfig, SpotifyConfig
from pixoo_spotify.spotify import SpotifyClient
from pydantic import HttpUrl, TypeAdapter


def test_spotify_cache_dir_created(tmp_path, monkeypatch) -> None:
    created = {}

    class DummyPKCE:
        def __init__(self, **kwargs):
            created["cache_path"] = kwargs.get("cache_path")

    class DummySpotify:
        def __init__(self, auth_manager):
            self.auth_manager = auth_manager

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
