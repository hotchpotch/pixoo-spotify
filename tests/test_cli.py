from pathlib import Path

import pytest
from pixoo_spotify import cli
from pixoo_spotify.spotify import SpotifyReauthenticationRequired, save_client_id
from typer.testing import CliRunner


def test_run_client_id_precedence_prefers_cli_then_toml_then_dotenv_then_cache(
    tmp_path: Path, monkeypatch
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('[spotify]\nclient_id = "toml-client"\n', encoding="utf-8")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("SPOTIFY_CLIENT_ID=dotenv-client\n", encoding="utf-8")
    auth_path = tmp_path / "auth"
    save_client_id("cached-client", auth_path)
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "environment-client")

    cli_config = cli.resolve_run_config(
        config_file,
        cli.build_overrides(client_id="cli-client"),
        auth_path,
        dotenv_path=dotenv_path,
    )
    toml_config = cli.resolve_run_config(
        config_file,
        cli.build_overrides(client_id=None),
        auth_path,
        dotenv_path=dotenv_path,
    )

    assert cli_config.spotify.client_id == "cli-client"
    assert toml_config.spotify.client_id == "toml-client"


def test_run_client_id_falls_back_to_environment_dotenv_and_cache(
    tmp_path: Path, monkeypatch
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("SPOTIFY_CLIENT_ID=dotenv-client\n", encoding="utf-8")
    auth_path = tmp_path / "auth"
    save_client_id("cached-client", auth_path)

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "environment-client")
    environment_config = cli.resolve_run_config(
        None, {}, auth_path, dotenv_path=dotenv_path
    )
    monkeypatch.delenv("SPOTIFY_CLIENT_ID")
    dotenv_config = cli.resolve_run_config(None, {}, auth_path, dotenv_path=dotenv_path)
    dotenv_path.unlink()
    cached_config = cli.resolve_run_config(None, {}, auth_path, dotenv_path=dotenv_path)

    assert environment_config.spotify.client_id == "environment-client"
    assert dotenv_config.spotify.client_id == "dotenv-client"
    assert cached_config.spotify.client_id == "cached-client"


def test_run_uses_toml_client_id_instead_of_working_directory_dotenv(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, str | None] = {}

    async def capture_config(config, **kwargs) -> None:
        captured["client_id"] = config.spotify.client_id

    (tmp_path / ".env").write_text(
        "SPOTIFY_CLIENT_ID=dotenv-client\n", encoding="utf-8"
    )
    (tmp_path / "config.toml").write_text(
        '[spotify]\nclient_id = "toml-client"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.setattr(cli, "run_app", capture_config)

    result = CliRunner().invoke(
        cli.app,
        [
            "--config-path",
            str(tmp_path / "auth"),
            "run",
            "--server-port",
            "18080",
            "--no-discover",
            "--no-play-on-device",
        ],
    )

    assert result.exit_code == 0
    assert captured["client_id"] == "toml-client"


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
