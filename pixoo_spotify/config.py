from __future__ import annotations

import importlib
import json
import locale
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir
from pydantic import AliasChoices, BaseModel, Field, HttpUrl, field_validator, model_validator

tomllib = importlib.import_module("tomllib" if sys.version_info >= (3, 11) else "tomli")


class TextPosition(str, Enum):
    bottom_right = "bottom-right"
    bottom_left = "bottom-left"
    top_left = "top-left"
    top_right = "top-right"


class ScrollMode(str, Enum):
    loop = "loop"
    bounce = "bounce"


class DitherMode(str, Enum):
    none = "none"
    floyd = "floyd"


class PaletteMode(str, Enum):
    auto = "auto"
    shared = "shared"


class LogFormat(str, Enum):
    simple = "simple"
    basic = "basic"


class UiMode(str, Enum):
    rich = "rich"
    text = "text"


class SpotifyConfig(BaseModel):
    client_id: str | None = None
    redirect_uri: str = "http://127.0.0.1:8888/callback"
    scope: str = "user-read-currently-playing user-read-playback-state"
    language: str | None = Field(default_factory=lambda: resolve_default_language())
    cache_path: Path = Field(
        default_factory=lambda: Path(user_config_dir("pixoo-spotify")) / "spotify_token.json"
    )
    open_browser: bool = True

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_language_tag(str(value))
        return normalized or None


class PixooConfig(BaseModel):
    device_ip: str | None = None
    discover: bool = True
    play_on_device: bool = True
    auto_screen_off: bool = False


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
    artwork_only: bool = False
    text_format: str = "{title}\n{artist}"
    scroll_mode: ScrollMode = ScrollMode.loop
    scroll_pause_frames: int = Field(
        15,
        ge=0,
        le=300,
        validation_alias=AliasChoices("scroll_pause_frames", "bounce_pause_frames"),
        serialization_alias="scroll_pause_frames",
    )
    gif_colors: int = Field(256, ge=2, le=256)
    gif_dither: DitherMode = DitherMode.none
    gif_palette: PaletteMode = PaletteMode.shared
    gif_optimize: bool = False
    position: TextPosition = TextPosition.bottom_left
    max_chars: int = Field(40, ge=1, le=80)
    output_path: Path = Field(
        default_factory=lambda: Path(user_config_dir("pixoo-spotify")) / "output" / "latest.gif"
    )
    background_color: tuple[int, int, int] = (120, 120, 120)
    overlay_color: str | None = "#00000078"
    overlay_opacity: int = Field(120, ge=0, le=255)
    text_color: str = "#ffffffff"
    text_shadow_color: str = "#000000ff"
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

    @field_validator("overlay_color", "text_color", "text_shadow_color")
    @classmethod
    def validate_overlay_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) != 8:
            raise ValueError("overlay_color must be in #RRGGBBAA format")
        try:
            int(text, 16)
        except ValueError as exc:
            raise ValueError("color must be valid hex") from exc
        return f"#{text.lower()}"

    def overlay_rgba(self) -> tuple[int, int, int, int] | None:
        if self.overlay_color:
            r, g, b, a = self._hex_to_rgba(self.overlay_color)
            if a == 0xFF:
                return None
            return (r, g, b, a)
        if self.overlay_opacity >= 255:
            return None
        return (0, 0, 0, self.overlay_opacity)

    def text_rgba(self) -> tuple[int, int, int, int]:
        return self._hex_to_rgba(self.text_color)

    def text_shadow_rgba(self) -> tuple[int, int, int, int] | None:
        r, g, b, a = self._hex_to_rgba(self.text_shadow_color)
        if a == 0:
            return None
        return (r, g, b, a)

    @staticmethod
    def _hex_to_rgba(value: str) -> tuple[int, int, int, int]:
        text = value.lstrip("#")
        return (
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
            int(text[6:8], 16),
        )


class UiConfig(BaseModel):
    mode: UiMode = UiMode.rich
    background: bool | None = None
    log_format: LogFormat = LogFormat.simple

    @model_validator(mode="after")
    def resolve_legacy_background(self) -> UiConfig:
        if self.background is None:
            return self
        self.mode = UiMode.text if self.background else UiMode.rich
        self.background = None
        return self


class AppConfig(BaseModel):
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)
    pixoo: PixooConfig = Field(default_factory=PixooConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    gif: GifConfig = Field(default_factory=GifConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    poll_interval: float = Field(5.0, ge=1.0, le=60.0)
    idle_poll_interval: float = Field(20.0, ge=5.0, le=300.0)

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


def normalize_language_tag(value: str) -> str:
    text = value.strip()
    if not text or text.upper() in {"C", "POSIX"}:
        return ""
    text = text.split(".", 1)[0]
    text = text.split("@", 1)[0]
    text = text.replace("_", "-")
    parts = [part for part in text.split("-") if part]
    if not parts:
        return ""
    parts[0] = parts[0].lower()
    if len(parts) >= 2:
        parts[1] = parts[1].upper()
    return "-".join(parts)


def resolve_default_language() -> str | None:
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key)
        if value:
            normalized = normalize_language_tag(value)
            if normalized:
                return normalized
    value, _encoding = locale.getlocale()
    if value:
        normalized = normalize_language_tag(value)
        if normalized:
            return normalized
    return None


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
