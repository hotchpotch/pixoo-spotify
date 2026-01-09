from __future__ import annotations

import io
from collections.abc import Iterable
from pathlib import Path

import httpx
from langdetect import DetectorFactory, detect_langs
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from pixoo_spotify.config import GifConfig, ScrollMode, TextPosition
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
    background = prepare_background(
        artwork=artwork,
        size=size,
        image_size=config.image_size or size,
        background_color=config.background_color,
    )

    lines = [line[: config.max_chars] for line in track.lines]

    line_metrics = []
    for line in lines:
        font = fonts.font_for_text(line)
        width, height = measure_text(font, line)
        line_metrics.append((font, width, height))

    line_height = max((height for _, _, height in line_metrics), default=8)
    text_area_height = line_height * len(lines)
    origin_y = position_origin_y(config.position, size, text_area_height, config.margin)

    margin_x = config.margin + (1 if config.scroll_mode == ScrollMode.bounce else 0)
    available_width = size - margin_x * 2
    widths = [width for _, width, _ in line_metrics]
    overflow_flags = [width > available_width for width in widths]
    direction = 1 if config.position in (TextPosition.bottom_right, TextPosition.top_right) else -1

    shared_cycle: int | None = None
    shared_width: int | None = None
    shared_range: int | None = None
    if sum(overflow_flags) >= 2:
        shared_width = max(widths) if widths else size
        if config.scroll_mode == ScrollMode.bounce:
            shared_range = max(0, shared_width - available_width)
            shared_cycle = max(1, shared_range * 2 + config.bounce_pause_frames * 2)
        else:
            shared_cycle = shared_width + config.spacer_px

    cycles = []
    for (_, width, _), overflow in zip(line_metrics, overflow_flags, strict=False):
        if overflow:
            if config.scroll_mode == ScrollMode.bounce:
                scroll_range = max(0, width - available_width)
                cycles.append(max(1, scroll_range * 2 + config.bounce_pause_frames * 2))
            else:
                cycles.append(width + config.spacer_px)
        else:
            cycles.append(1)

    total_frames = shared_cycle or (max(cycles) if cycles else 1)

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
            if shared_cycle and shared_width is not None:
                base_origin_x = position_origin_x(config.position, size, shared_width, margin_x)
                align_offset = (
                    shared_width - width
                    if config.position in (TextPosition.bottom_right, TextPosition.top_right)
                    else 0
                )
                cycle = shared_cycle
                offset = compute_scroll_offset(
                    frame_index=frame_index,
                    cycle=cycle,
                    scroll_mode=config.scroll_mode,
                    scroll_px_per_frame=config.scroll_px_per_frame,
                    available_width=available_width,
                    text_width=shared_width,
                    scroll_range=shared_range,
                    bounce_pause_frames=config.bounce_pause_frames,
                    direction=direction,
                )
                x = base_origin_x + align_offset + offset
            else:
                origin_x = position_origin_x(config.position, size, width, margin_x)
                cycle = cycles[idx]
                offset = compute_scroll_offset(
                    frame_index=frame_index,
                    cycle=cycle,
                    scroll_mode=config.scroll_mode,
                    scroll_px_per_frame=config.scroll_px_per_frame,
                    available_width=available_width,
                    text_width=width,
                    scroll_range=None,
                    bounce_pause_frames=config.bounce_pause_frames,
                    direction=direction,
                )
                x = origin_x + offset
            y = origin_y + idx * line_height
            draw_scrolling_text(
                draw,
                line,
                font,
                x,
                y,
                cycle,
                size,
                wrap=config.scroll_mode == ScrollMode.loop,
            )
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
    *,
    wrap: bool,
) -> None:
    shadow = (0, 0, 0)
    fill = (255, 255, 255)
    draw.text((x + 1, y + 1), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    if wrap and cycle > 1:
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


def compute_scroll_offset(
    *,
    frame_index: int,
    cycle: int,
    scroll_mode: ScrollMode,
    scroll_px_per_frame: int,
    available_width: int,
    text_width: int,
    scroll_range: int | None,
    bounce_pause_frames: int,
    direction: int,
) -> int:
    if cycle <= 1:
        return 0
    step = frame_index * scroll_px_per_frame
    if scroll_mode == ScrollMode.bounce:
        if scroll_range is None:
            scroll_range = max(0, text_width - available_width)
        if scroll_range == 0:
            return 0
        pause = max(0, bounce_pause_frames)
        path = scroll_range * 2 + pause * 2
        pos = step % path
        if pos < pause:
            pos = 0
        else:
            pos -= pause
            if pos <= scroll_range:
                pos = pos
            else:
                pos -= scroll_range
                if pos < pause:
                    pos = scroll_range
                else:
                    pos -= pause
                    pos = scroll_range - pos
        if direction >= 0:
            return int(scroll_range - pos)
        return -int(pos)
    return -int(step % cycle)


def prepare_background(
    artwork: Image.Image | None,
    size: int,
    image_size: int,
    background_color: tuple[int, int, int],
) -> Image.Image:
    base_size = image_size
    if artwork is None:
        background = Image.new("RGB", (base_size, base_size), background_color)
    else:
        background = artwork.convert("RGB")
        if background.size != (base_size, base_size):
            background = background.resize((base_size, base_size), Image.Resampling.LANCZOS)
    if base_size != size:
        background = background.resize((size, size), Image.Resampling.NEAREST)
    return background
