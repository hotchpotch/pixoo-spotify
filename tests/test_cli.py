from pathlib import Path

import pytest
from pixoo_spotify import cli
from pixoo_spotify.spotify import SpotifyReauthenticationRequired
from typer.testing import CliRunner


@pytest.mark.parametrize("reason", ["missing", "expired"])
def test_run_explains_spotify_reauthentication_for_server_operators(
    reason: str, tmp_path: Path, monkeypatch
) -> None:
    async def raise_reauthentication_required(*args, **kwargs) -> None:
        raise SpotifyReauthenticationRequired(
            client_id="client-123",
            cache_path=tmp_path / "spotify_token.json",
            reason=reason,
            cache_discarded=reason == "expired",
        )

    monkeypatch.setattr(cli, "run_app", raise_reauthentication_required)

    result = CliRunner().invoke(
        cli.app,
        [
            "--config-path",
            str(tmp_path),
            "run",
            "--client-id",
            "client-123",
            "--server-port",
            "18080",
            "--no-discover",
            "--no-play-on-device",
        ],
    )

    assert result.exit_code == 1
    assert "Spotify authorization" in result.stderr
    assert "expire 6 months after authorization" in result.stderr
    assert "auth --client-id client-123 --reauth" in result.stderr
    assert f"--config-path {tmp_path}" in result.stderr
    assert f"--cache-path {tmp_path / 'spotify_token.json'}" in result.stderr
    assert "--no-open-browser" in result.stderr
    assert "restart the pixoo-spotify service or process" in result.stderr
    assert "Traceback" not in result.stderr
