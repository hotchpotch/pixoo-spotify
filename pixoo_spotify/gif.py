from __future__ import annotations

import io
import logging
from collections.abc import Iterable
from importlib import resources
from pathlib import Path

import httpx
from langdetect import DetectorFactory, detect_langs
from PIL import Image, ImageDraw, ImageFont

from pixoo_spotify.config import DitherMode, GifConfig, PaletteMode, ScrollMode, TextPosition
from pixoo_spotify.langs import get_langdetect_languages
from pixoo_spotify.models import TrackInfo

DetectorFactory.seed = 0
logger = logging.getLogger(__name__)
FONT_EXTENSIONS = (".ttf", ".otf")
SCROLL_END_MARGIN_PX = 16


FontType = ImageFont.ImageFont | ImageFont.FreeTypeFont


class FontRegistry:
    def __init__(
        self,
        fonts: dict[str, FontType],
        font_paths: dict[str, Path],
        fallback_font: FontType,
        fallback_path: Path,
        supported_langs: list[str],
    ):
        self._fonts = fonts
        self._font_paths = font_paths
        self._fallback_font = fallback_font
        self._fallback_path = fallback_path
        self._supported_langs = supported_langs

    def font_for_text(self, text: str) -> FontType:
        lang = detect_language(text, self._supported_langs)
        if lang and lang in self._fonts:
            logger.debug(
                "Font selected lang=%s font=%s text=%s",
                lang,
                self._font_paths[lang],
                _preview_text(text),
            )
            return self._fonts[lang]
        logger.debug(
            "Font fallback lang=%s font=%s text=%s",
            lang,
            self._fallback_path,
            _preview_text(text),
        )
        return self._fallback_font


async def load_font_registry(fonts_dir: Path) -> FontRegistry:
    fonts: dict[str, FontType] = {}
    font_paths: dict[str, Path] = {}
    supported_langs = get_langdetect_languages()

    if fonts_dir.exists():
        logger.debug("Searching fonts in %s", fonts_dir)
    else:
        logger.debug("Fonts directory does not exist: %s", fonts_dir)

    for lang in supported_langs:
        path = _find_font_path(fonts_dir, lang)
        if not path:
            continue
        fonts[lang] = _load_font(path)
        font_paths[lang] = path
        logger.debug("Loaded font for lang=%s path=%s", lang, path)

    fallback_path = _find_font_path(fonts_dir, "fallback")
    if fallback_path is None:
        fallback_path = _packaged_fallback_font()
        logger.debug("Using packaged fallback font: %s", fallback_path)
    else:
        logger.debug("Using fallback font from config dir: %s", fallback_path)
    fallback_font = _load_font(fallback_path)

    return FontRegistry(
        fonts=fonts,
        font_paths=font_paths,
        fallback_font=fallback_font,
        fallback_path=fallback_path,
        supported_langs=supported_langs,
    )


def detect_language(text: str, fallbacks: Iterable[str]) -> str | None:
    text = text.strip()
    if not text:
        return None
    try:
        guesses = detect_langs(text)
    except Exception as exc:
        logger.debug("Language detection failed: %s", exc)
        return None
    if not guesses:
        return None
    guess = max(guesses, key=lambda item: item.prob)
    supported = set(fallbacks)
    if guess.lang not in supported:
        logger.debug("Detected language not supported: %s", guess.lang)
        return None
    logger.debug("Detected language=%s prob=%.3f", guess.lang, guess.prob)
    return guess.lang


def _preview_text(text: str, limit: int = 32) -> str:
    text = text.replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _find_font_path(fonts_dir: Path, name: str) -> Path | None:
    for ext in FONT_EXTENSIONS:
        candidate = fonts_dir / f"{name}{ext}"
        if candidate.exists():
            return candidate
    return None


def _load_font(path: Path) -> FontType:
    try:
        return ImageFont.truetype(str(path), 8)
    except OSError as exc:
        raise RuntimeError(f"Failed to load font at {path}: {exc}") from exc


def _packaged_fallback_font() -> Path:
    resource = resources.files("pixoo_spotify") / "fonts/misaki/misaki_gothic.ttf"
    path = Path(str(resource))
    if not path.exists():
        raise RuntimeError("Packaged fallback font is missing.")
    return path


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
        optimize=config.gif_optimize,
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

    if config.artwork_only:
        frame = background.convert("P")
        return [frame]

    lines = [line[: config.max_chars] for line in format_text_lines(track, config)]

    text_rgba = config.text_rgba()
    shadow_rgba = config.text_shadow_rgba()

    line_metrics = []
    heights: list[int] = []
    for line in lines:
        font = fonts.font_for_text(line)
        width, height, offset_y = measure_text_bbox(font, line)
        line_metrics.append((font, width, height, offset_y))
        heights.append(height)

    line_height = max(heights, default=8)
    line_gap = 1
    line_step = line_height + line_gap
    shadow_extra = 1 if shadow_rgba is not None else 0
    text_area_height = line_height * len(lines) + line_gap * max(len(lines) - 1, 0) + shadow_extra
    origin_y = position_origin_y(config.position, size, text_area_height, config.margin)

    base_margin = config.margin
    margin_left, margin_right = horizontal_margins(
        config.position,
        base_margin,
        config.scroll_mode == ScrollMode.bounce,
    )
    available_width = size - margin_left - margin_right
    widths = [width for _, width, _, _ in line_metrics]
    overflow_flags = [width > available_width for width in widths]
    direction = 1 if config.position in (TextPosition.bottom_right, TextPosition.top_right) else -1

    shared_cycle: int | None = None
    shared_width: int | None = None
    shared_range: int | None = None
    if sum(overflow_flags) >= 2:
        shared_width = max(widths) if widths else size
        if config.scroll_mode == ScrollMode.bounce:
            shared_range = max(0, shared_width - available_width)
            shared_cycle = max(1, shared_range * 2 + config.scroll_pause_frames * 2)
        else:
            shared_cycle = shared_width + available_width + config.spacer_px + SCROLL_END_MARGIN_PX

    cycles = []
    for (_, width, _, _), overflow in zip(line_metrics, overflow_flags, strict=False):
        if overflow:
            if config.scroll_mode == ScrollMode.bounce:
                scroll_range = max(0, width - available_width)
                cycles.append(max(1, scroll_range * 2 + config.scroll_pause_frames * 2))
            else:
                cycles.append(width + available_width + config.spacer_px + SCROLL_END_MARGIN_PX)
        else:
            cycles.append(1)

    total_frames = shared_cycle or (max(cycles) if cycles else 1)

    frames_rgba: list[Image.Image] = []
    for frame_index in range(total_frames):
        frame = background.copy().convert("RGBA")
        overlay_rgba = config.overlay_rgba()
        if overlay_rgba is not None:
            overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_top, overlay_bottom = overlay_bounds(origin_y, text_area_height, size)
            overlay_draw.rectangle(
                (0, overlay_top, size, overlay_bottom),
                fill=overlay_rgba,
            )
            frame = Image.alpha_composite(frame, overlay)

        draw = ImageDraw.Draw(frame)
        for idx, line in enumerate(lines):
            font, width, _height, offset_y = line_metrics[idx]
            if shared_cycle and shared_width is not None:
                base_origin_x = position_origin_x(
                    config.position,
                    size,
                    shared_width,
                    margin_right
                    if config.position in (TextPosition.bottom_right, TextPosition.top_right)
                    else margin_left,
                )
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
                    scroll_pause_frames=config.scroll_pause_frames,
                    direction=direction,
                )
                x = base_origin_x + align_offset + offset
            else:
                origin_x = position_origin_x(
                    config.position,
                    size,
                    width,
                    margin_right
                    if config.position in (TextPosition.bottom_right, TextPosition.top_right)
                    else margin_left,
                )
                cycle = cycles[idx]
                offset = compute_scroll_offset(
                    frame_index=frame_index,
                    cycle=cycle,
                    scroll_mode=config.scroll_mode,
                    scroll_px_per_frame=config.scroll_px_per_frame,
                    available_width=available_width,
                    text_width=width,
                    scroll_range=None,
                    scroll_pause_frames=config.scroll_pause_frames,
                    direction=direction,
                )
                x = origin_x + offset
            line_top = origin_y + idx * line_step
            y = line_top - offset_y
            draw_scrolling_text(
                draw,
                line,
                font,
                x,
                y,
                cycle,
                size,
                wrap=False,
                text_color=text_rgba,
                shadow_color=shadow_rgba,
            )
        frames_rgba.append(frame)

    dither = _dither_option(config.gif_dither)
    palette_image: Image.Image | None = None
    if config.gif_palette == PaletteMode.shared and frames_rgba:
        palette_source = frames_rgba[0].convert("RGB")
        palette_image = palette_source.quantize(colors=config.gif_colors, dither=dither)

    frames: list[Image.Image] = []
    for frame in frames_rgba:
        frames.append(_quantize_frame(frame, config, palette_image, dither))
    return frames


def _dither_option(mode: DitherMode) -> Image.Dither:
    if mode == DitherMode.none:
        return Image.Dither.NONE
    return Image.Dither.FLOYDSTEINBERG


def _quantize_frame(
    frame: Image.Image,
    config: GifConfig,
    palette_image: Image.Image | None,
    dither: Image.Dither,
) -> Image.Image:
    rgb = frame.convert("RGB")
    if palette_image is not None:
        return rgb.quantize(palette=palette_image, dither=dither)
    return rgb.quantize(colors=config.gif_colors, dither=dither)


def horizontal_margins(
    position: TextPosition,
    base_margin: int,
    bounce: bool,
) -> tuple[int, int]:
    bounce_pad = 1 if bounce else 0
    if position in (TextPosition.bottom_left, TextPosition.top_left):
        left_extra = 0 if bounce else 1
        return (base_margin + bounce_pad + left_extra, base_margin + bounce_pad)
    return (base_margin + bounce_pad, base_margin + bounce_pad)


class _SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def format_text_lines(track: TrackInfo, config: GifConfig) -> list[str]:
    template = config.text_format.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    values = _SafeFormatDict(
        {
            "title": track.title or "",
            "artist": track.artist or "",
            "album": track.album or "",
        }
    )
    text = template.format_map(values)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        lines = [track.title, track.artist]
    if len(lines) > 3:
        logger.warning("text_format produced %d lines; truncating to 3.", len(lines))
        lines = lines[:3]
    return lines


def position_origin_x(position: TextPosition, size: int, width: int, margin: int) -> int:
    if position in (TextPosition.bottom_right, TextPosition.top_right):
        return size - width - margin
    return margin


def position_origin_y(position: TextPosition, size: int, text_height: int, margin: int) -> int:
    if position in (TextPosition.bottom_right, TextPosition.bottom_left):
        return size - text_height - margin
    return margin + 1


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
    text_color: tuple[int, int, int, int] | None,
    shadow_color: tuple[int, int, int, int] | None,
) -> None:
    if shadow_color is not None:
        draw.text((x + 1, y + 1), text, font=font, fill=shadow_color)
    if text_color is not None:
        draw.text((x, y), text, font=font, fill=text_color)
    if wrap and cycle > 1:
        wrap_x = x + cycle
        if wrap_x < size:
            if shadow_color is not None:
                draw.text((wrap_x + 1, y + 1), text, font=font, fill=shadow_color)
            if text_color is not None:
                draw.text((wrap_x, y), text, font=font, fill=text_color)


def measure_text_bbox(font: FontType, text: str) -> tuple[int, int, int]:
    if not text:
        return (0, 0, 0)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = int(bbox[2] - bbox[0])
    height = int(bbox[3] - bbox[1])
    return (width, height, int(bbox[1]))


def compute_scroll_offset(
    *,
    frame_index: int,
    cycle: int,
    scroll_mode: ScrollMode,
    scroll_px_per_frame: int,
    available_width: int,
    text_width: int,
    scroll_range: int | None,
    scroll_pause_frames: int,
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
        pause = max(0, scroll_pause_frames)
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
    lead_in = text_width if direction >= 0 else available_width
    return int(lead_in - (step % cycle))


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


def overlay_bounds(origin_y: int, text_area_height: int, size: int) -> tuple[int, int]:
    extra_top = 1
    overlay_top = max(0, origin_y - extra_top)
    overlay_bottom = min(size, origin_y + text_area_height - 1)
    if overlay_bottom <= overlay_top:
        overlay_bottom = min(size, overlay_top + 1)
    return (overlay_top, overlay_bottom)
