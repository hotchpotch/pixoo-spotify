from __future__ import annotations

import json
import tomllib
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class TextPosition(str, Enum):
    bottom_right = "bottom-right"
    bottom_left = "bottom-left"
    top_left = "top-left"
    top_right = "top-right"


class ScrollMode(str, Enum):
    loop = "loop"
    bounce = "bounce"


class SpotifyConfig(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str = "http://127.0.0.1:8888/callback"
    scope: str = "user-read-currently-playing user-read-playback-state"
    cache_path: Path = Path(".cache/spotify_token.json")
    open_browser: bool = True


class PixooConfig(BaseModel):
    device_ip: str | None = None
    discover: bool = True
    play_on_device: bool = True


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    public_base_url: HttpUrl | None = None

    def base_url(self) -> str:
        if self.public_base_url:
            return str(self.public_base_url).rstrip("/")
        host = "localhost" if self.host == "0.0.0.0" else self.host
        return f"http://{host}:{self.port}".rstrip("/")


class GifConfig(BaseModel):
    size: int = Field(64, ge=16, le=64)
    image_size: int | None = Field(None, ge=16, le=64)
    fps: int = Field(8, ge=1, le=60)
    scroll_mode: ScrollMode = ScrollMode.loop
    bounce_pause_frames: int = Field(4, ge=0, le=120)
    position: TextPosition = TextPosition.bottom_right
    max_chars: int = Field(40, ge=1, le=80)
    output_path: Path = Path("output/latest.gif")
    background_color: tuple[int, int, int] = (120, 120, 120)
    overlay_opacity: int = Field(120, ge=0, le=255)
    scroll_px_per_frame: int = Field(1, ge=1, le=10)
    spacer_px: int = Field(8, ge=0, le=64)
    margin: int = Field(0, ge=0, le=8)

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: int) -> int:
        if value not in (16, 32, 64):
            raise ValueError("size must be 16, 32, or 64")
        return value

    @model_validator(mode="after")
    def validate_image_size(self) -> GifConfig:
        if self.image_size is None:
            return self
        if self.image_size not in (16, 32, 64):
            raise ValueError("image_size must be 16, 32, or 64")
        if self.image_size > self.size:
            raise ValueError("image_size must be less than or equal to size")
        return self


class UiConfig(BaseModel):
    background: bool = False


class AppConfig(BaseModel):
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)
    pixoo: PixooConfig = Field(default_factory=PixooConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    gif: GifConfig = Field(default_factory=GifConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    poll_interval: float = Field(5.0, ge=1.0, le=60.0)

    @classmethod
    def from_sources(cls, config_path: Path | None, overrides: dict[str, Any]) -> AppConfig:
        base: dict[str, Any] = {}
        if config_path:
            config_data = load_config_file(config_path)
            if config_data:
                base = config_data
        merged = merge_dicts(base, overrides)
        return cls.model_validate(merged)


def load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.suffix == ".toml":
        with path.open("rb") as handle:
            return tomllib.load(handle)
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("config file must be .toml or .json")


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        value = _strip_none(value)
        if value is None or (isinstance(value, dict) and not value):
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            stripped = _strip_none(item)
            if stripped is None:
                continue
            if isinstance(stripped, dict) and not stripped:
                continue
            cleaned[key] = stripped
        return cleaned
    return value
