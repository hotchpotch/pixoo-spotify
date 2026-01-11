import asyncio
from pathlib import Path

from PIL import Image
from pixoo_spotify.config import GifConfig, ScrollMode, TextPosition
from pixoo_spotify.gif import (
    build_gif_bytes,
    compute_scroll_offset,
    format_text_lines,
    horizontal_margins,
    load_font_registry,
    overlay_bounds,
    position_origin_x,
    position_origin_y,
    prepare_background,
)
from pixoo_spotify.models import TrackInfo


def test_gif_generation(tmp_path: Path) -> None:
    track = TrackInfo(artist="Artist", title="Title", album="Album")
    config = GifConfig(output_path=tmp_path / "out.gif")
    fonts = asyncio.run(load_font_registry(tmp_path / "fonts"))
    gif_bytes = build_gif_bytes(track=track, config=config, fonts=fonts, artwork=None)

    output = tmp_path / "out.gif"
    output.write_bytes(gif_bytes)

    image = Image.open(output)
    assert image.format == "GIF"
    assert image.size == (config.size, config.size)
    assert getattr(image, "n_frames", 1) >= 1


def test_prepare_background_pixelates() -> None:
    src_size = 16
    dst_size = 32
    artwork = Image.new("RGB", (src_size, src_size), (255, 0, 0))
    background = prepare_background(
        artwork=artwork,
        size=dst_size,
        image_size=src_size,
        background_color=(0, 0, 0),
    )
    assert background.size == (dst_size, dst_size)
    assert background.getpixel((0, 0)) == background.getpixel((1, 1))


def test_compute_scroll_offset_bounce() -> None:
    offsets = [
        compute_scroll_offset(
            frame_index=idx,
            cycle=4,
            scroll_mode=ScrollMode.bounce,
            scroll_px_per_frame=1,
            available_width=8,
            text_width=10,
            scroll_range=2,
            scroll_pause_frames=0,
            direction=-1,
        )
        for idx in range(5)
    ]
    assert offsets == [0, -1, -2, -1, 0]

    offsets_right = [
        compute_scroll_offset(
            frame_index=idx,
            cycle=4,
            scroll_mode=ScrollMode.bounce,
            scroll_px_per_frame=1,
            available_width=8,
            text_width=10,
            scroll_range=2,
            scroll_pause_frames=0,
            direction=1,
        )
        for idx in range(5)
    ]
    assert offsets_right == [2, 1, 0, 1, 2]


def test_compute_scroll_offset_bounce_with_pause() -> None:
    offsets = [
        compute_scroll_offset(
            frame_index=idx,
            cycle=6,
            scroll_mode=ScrollMode.bounce,
            scroll_px_per_frame=1,
            available_width=8,
            text_width=10,
            scroll_range=2,
            scroll_pause_frames=1,
            direction=-1,
        )
        for idx in range(6)
    ]
    assert offsets == [0, 0, -1, -2, -2, -1]


def test_compute_scroll_offset_loop_with_pause() -> None:
    offsets = [
        compute_scroll_offset(
            frame_index=idx,
            cycle=5,
            scroll_mode=ScrollMode.loop,
            scroll_px_per_frame=1,
            available_width=8,
            text_width=10,
            scroll_range=None,
            scroll_pause_frames=2,
            direction=-1,
        )
        for idx in range(5)
    ]
    assert offsets == [8, 7, 6, 5, 4]


def test_position_origin_respects_corners() -> None:
    assert position_origin_x(TextPosition.top_left, 64, 10, 2) == 2
    assert position_origin_x(TextPosition.bottom_left, 64, 10, 2) == 2
    assert position_origin_x(TextPosition.top_right, 64, 10, 2) == 52
    assert position_origin_x(TextPosition.bottom_right, 64, 10, 2) == 52
    assert position_origin_y(TextPosition.top_left, 64, 12, 3) == 4
    assert position_origin_y(TextPosition.top_right, 64, 12, 3) == 4
    assert position_origin_y(TextPosition.bottom_left, 64, 12, 3) == 49
    assert position_origin_y(TextPosition.bottom_right, 64, 12, 3) == 49


def test_left_align_starts_offscreen() -> None:
    size = 64
    margin = 2
    text_width = 100
    margin_left, margin_right = horizontal_margins(TextPosition.top_left, margin, False)
    available_width = size - margin_left - margin_right
    origin_x = position_origin_x(TextPosition.top_left, size, text_width, margin_left)
    loop_offset = compute_scroll_offset(
        frame_index=0,
        cycle=text_width + 8,
        scroll_mode=ScrollMode.loop,
        scroll_px_per_frame=1,
        available_width=available_width,
        text_width=text_width,
        scroll_range=None,
        scroll_pause_frames=0,
        direction=-1,
    )
    assert origin_x + loop_offset == margin_left + available_width
    bounce_offset = compute_scroll_offset(
        frame_index=0,
        cycle=4,
        scroll_mode=ScrollMode.bounce,
        scroll_px_per_frame=1,
        available_width=available_width,
        text_width=text_width,
        scroll_range=text_width - available_width,
        scroll_pause_frames=0,
        direction=-1,
    )
    assert origin_x + bounce_offset == margin_left


def test_horizontal_margins_add_left_padding() -> None:
    assert horizontal_margins(TextPosition.top_left, 0, False) == (1, 0)
    assert horizontal_margins(TextPosition.bottom_left, 2, False) == (3, 2)
    assert horizontal_margins(TextPosition.top_right, 0, False) == (0, 0)


def test_horizontal_margins_bounce_padding() -> None:
    assert horizontal_margins(TextPosition.top_left, 0, True) == (1, 1)
    assert horizontal_margins(TextPosition.bottom_left, 0, True) == (1, 1)
    assert horizontal_margins(TextPosition.top_right, 0, True) == (1, 1)


def test_overlay_rgba_skips_when_alpha_ff() -> None:
    config = GifConfig(overlay_color="#112233FF")
    assert config.overlay_rgba() is None


def test_text_color_parsing() -> None:
    config = GifConfig(text_color="#11223344", text_shadow_color="#55667700")
    assert config.text_rgba() == (0x11, 0x22, 0x33, 0x44)
    assert config.text_shadow_rgba() is None


def test_artwork_only_generates_single_frame(tmp_path: Path) -> None:
    track = TrackInfo(artist="Artist", title="Title", album="Album")
    config = GifConfig(output_path=tmp_path / "out.gif", artwork_only=True)
    fonts = asyncio.run(load_font_registry(tmp_path / "fonts"))
    gif_bytes = build_gif_bytes(track=track, config=config, fonts=fonts, artwork=None)
    output = tmp_path / "out.gif"
    output.write_bytes(gif_bytes)
    image = Image.open(output)
    assert getattr(image, "n_frames", 1) == 1


def test_text_format_lines_limit() -> None:
    track = TrackInfo(artist="Artist", title="Title", album="Album")
    config = GifConfig(text_format="{title}\n{artist}\n{album}\nextra")
    lines = format_text_lines(track, config)
    assert lines == ["Title", "Artist", "Album"]


def test_text_format_accepts_escaped_newlines() -> None:
    track = TrackInfo(artist="Artist", title="Title", album="Album")
    config = GifConfig(text_format="{title}\\n{artist}\\n{album}")
    lines = format_text_lines(track, config)
    assert lines == ["Title", "Artist", "Album"]


def test_overlay_bounds_clamped_to_text_area() -> None:
    top, bottom = overlay_bounds(origin_y=0, text_area_height=12, size=64)
    assert top == 0
    assert bottom == 11
    top, bottom = overlay_bounds(origin_y=50, text_area_height=10, size=64)
    assert (top, bottom) == (49, 59)
