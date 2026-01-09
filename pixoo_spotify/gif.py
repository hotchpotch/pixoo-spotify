from __future__ import annotations

import io
from collections.abc import Iterable
from pathlib import Path

import httpx
from langdetect import DetectorFactory, detect_langs
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from pixoo_spotify.config import GifConfig, TextPosition
from pixoo_spotify.fonts import MISAKI_GOTHIC_URL, ensure_font_file
from pixoo_spotify.models import TrackInfo

DetectorFactory.seed = 0


class FontSpec(BaseModel):
    name: str
    path: Path | None = None
    size: int = 8
    download_url: str | None = None


class FontConfig(BaseModel):
    fonts: dict[str, FontSpec]
    fallback_langs: list[str] = Field(default_factory=lambda: ["en", "ja"])


FontType = ImageFont.ImageFont | ImageFont.FreeTypeFont


class FontRegistry:
    def __init__(self, fonts: dict[str, FontType], fallback_langs: list[str]):
        self._fonts = fonts
        self._fallbacks = fallback_langs

    def font_for_text(self, text: str) -> FontType:
        lang = detect_language(text, self._fallbacks)
        return self._fonts.get(lang) or next(iter(self._fonts.values()))


async def load_font_registry(config: FontConfig, fonts_dir: Path) -> FontRegistry:
    fonts: dict[str, FontType] = {}
    for lang, spec in config.fonts.items():
        if spec.path:
            path = spec.path
            if not path.is_absolute():
                path = fonts_dir / path
            if spec.download_url:
                path = await ensure_font_file(path, spec.download_url)
            elif not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                fonts[lang] = ImageFont.truetype(str(path), spec.size)
                continue
        fonts[lang] = ImageFont.load_default()
    return FontRegistry(fonts=fonts, fallback_langs=config.fallback_langs)


def default_font_config() -> FontConfig:
    return FontConfig(
        fonts={
            "en": FontSpec(
                name="misaki_gothic",
                path=Path("misaki_gothic.ttf"),
                size=8,
                download_url=MISAKI_GOTHIC_URL,
            ),
            "ja": FontSpec(
                name="misaki_gothic",
                path=Path("misaki_gothic.ttf"),
                size=8,
                download_url=MISAKI_GOTHIC_URL,
            ),
        },
        fallback_langs=["en", "ja"],
    )


def detect_language(text: str, fallbacks: Iterable[str]) -> str:
    text = text.strip()
    if not text:
        return next(iter(fallbacks))
    try:
        guesses = detect_langs(text)
    except Exception:
        return next(iter(fallbacks))
    if not guesses:
        return next(iter(fallbacks))
    guess = max(guesses, key=lambda item: item.prob)
    return guess.lang


async def fetch_artwork(url: str | None, size: int) -> Image.Image | None:
    if not url:
        return None
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return None
    try:
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        return None
    return image.resize((size, size), Image.Resampling.LANCZOS)


def build_gif_bytes(
    track: TrackInfo,
    config: GifConfig,
    fonts: FontRegistry,
    artwork: Image.Image | None,
) -> bytes:
    frames = build_frames(track=track, config=config, fonts=fonts, artwork=artwork)
    buffer = io.BytesIO()
    duration = int(1000 / config.fps)
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    return buffer.getvalue()


def build_frames(
    track: TrackInfo,
    config: GifConfig,
    fonts: FontRegistry,
    artwork: Image.Image | None,
) -> list[Image.Image]:
    size = config.size
    background = artwork or Image.new("RGB", (size, size), config.background_color)
    background = background.resize((size, size), Image.Resampling.LANCZOS)

    lines = [line[: config.max_chars] for line in track.lines]

    line_metrics = []
    for line in lines:
        font = fonts.font_for_text(line)
        width, height = measure_text(font, line)
        line_metrics.append((font, width, height))

    line_height = max((height for _, _, height in line_metrics), default=8)
    text_area_height = line_height * len(lines)
    origin_y = position_origin_y(config.position, size, text_area_height, config.margin)

    cycles = []
    for (_, width, _) in line_metrics:
        overflow = max(0, width - (size - config.margin * 2))
        if overflow == 0:
            cycles.append(1)
        else:
            cycles.append(width + config.spacer_px)

    total_frames = max(cycles) if cycles else 1

    frames: list[Image.Image] = []
    for frame_index in range(total_frames):
        frame = background.copy().convert("RGBA")
        if config.overlay_opacity > 0:
            overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                (0, origin_y, size, size),
                fill=(0, 0, 0, config.overlay_opacity),
            )
            frame = Image.alpha_composite(frame, overlay)

        draw = ImageDraw.Draw(frame)
        for idx, line in enumerate(lines):
            font, width, _height = line_metrics[idx]
            origin_x = position_origin_x(config.position, size, width, config.margin)
            cycle = cycles[idx]
            if cycle == 1:
                x = origin_x
            else:
                offset = -((frame_index * config.scroll_px_per_frame) % cycle)
                x = origin_x + offset
            y = origin_y + idx * line_height
            draw_scrolling_text(draw, line, font, x, y, cycle, size)
        frames.append(frame.convert("P"))
    return frames


def position_origin_x(position: TextPosition, size: int, width: int, margin: int) -> int:
    if position in (TextPosition.bottom_right, TextPosition.top_right):
        return size - width - margin
    return margin


def position_origin_y(position: TextPosition, size: int, text_height: int, margin: int) -> int:
    if position in (TextPosition.bottom_right, TextPosition.bottom_left):
        return size - text_height - margin
    return margin


def draw_scrolling_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: FontType,
    x: int,
    y: int,
    cycle: int,
    size: int,
) -> None:
    shadow = (0, 0, 0)
    fill = (255, 255, 255)
    draw.text((x + 1, y + 1), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    if cycle > 1:
        wrap_x = x + cycle
        if wrap_x < size:
            draw.text((wrap_x + 1, y + 1), text, font=font, fill=shadow)
            draw.text((wrap_x, y), text, font=font, fill=fill)


def measure_text(font: FontType, text: str) -> tuple[int, int]:
    if not text:
        return (0, 0)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    return (int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1]))
