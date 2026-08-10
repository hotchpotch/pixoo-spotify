import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pixoo_spotify.config import SpotifyConfig
from pixoo_spotify.models import TrackInfo
from pixoo_spotify.spotify import SpotifyClient, SpotifyReauthenticationRequired

pytestmark = pytest.mark.spotify_e2e


@pytest.fixture(scope="module")
def spotify_client_id() -> str:
    load_dotenv()
    if os.environ.get("RUN_SPOTIFY_E2E") != "1":
        pytest.skip("set RUN_SPOTIFY_E2E=1 to call the live Spotify API")
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    if not client_id:
        pytest.skip("SPOTIFY_CLIENT_ID is required for live Spotify tests")
    return client_id


@pytest.fixture(scope="module")
def spotify_token_cache(spotify_client_id: str) -> Path:
    del spotify_client_id
    configured_path = os.environ.get("SPOTIFY_E2E_TOKEN_CACHE", "").strip()
    if not configured_path:
        pytest.skip("SPOTIFY_E2E_TOKEN_CACHE is required for authenticated Spotify tests")
    cache_path = Path(os.path.expandvars(configured_path)).expanduser()
    if not cache_path.is_file():
        pytest.skip(f"E2E token cache not found: {cache_path}")
    return cache_path


def test_live_spotify_rejects_invalid_refresh_token(
    spotify_client_id: str, tmp_path: Path
) -> None:
    cache_path = tmp_path / "invalid_spotify_token.json"
    config = SpotifyConfig(client_id=spotify_client_id, cache_path=cache_path)
    cache_path.write_text(
        json.dumps(
            {
                "access_token": "expired-for-e2e-test",
                "refresh_token": f"invalid-for-e2e-test-{uuid.uuid4().hex}",
                "expires_at": 0,
                "scope": config.scope,
                "token_type": "Bearer",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SpotifyReauthenticationRequired) as exc_info:
        asyncio.run(SpotifyClient(config).current_track())

    assert exc_info.value.reason == "expired"
    assert exc_info.value.cache_discarded is True
    assert cache_path.exists() is False


def test_live_spotify_refreshes_token_and_reads_playback(
    spotify_client_id: str, spotify_token_cache: Path
) -> None:
    token = json.loads(spotify_token_cache.read_text(encoding="utf-8"))
    assert isinstance(token, dict)
    token["expires_at"] = 0
    spotify_token_cache.write_text(json.dumps(token), encoding="utf-8")

    config = SpotifyConfig(client_id=spotify_client_id, cache_path=spotify_token_cache)
    track = asyncio.run(SpotifyClient(config).current_track())

    refreshed_token = json.loads(spotify_token_cache.read_text(encoding="utf-8"))
    assert refreshed_token["expires_at"] > time.time()
    assert isinstance(refreshed_token.get("refresh_token"), str)
    assert track is None or isinstance(track, TrackInfo)
