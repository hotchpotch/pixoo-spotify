from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir

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


def get_fonts_dir(config_path: Path | None = None) -> Path:
    base_path = resolve_pixoo_spotify_config_path(config_path)
    return base_path / "fonts"
