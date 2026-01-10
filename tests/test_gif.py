import asyncio
from pathlib import Path

from PIL import Image
from pixoo_spotify.config import GifConfig, ScrollMode
from pixoo_spotify.gif import (
    build_gif_bytes,
    compute_scroll_offset,
    load_font_registry,
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
            bounce_pause_frames=0,
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
            bounce_pause_frames=0,
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
            bounce_pause_frames=1,
            direction=-1,
        )
        for idx in range(6)
    ]
    assert offsets == [0, 0, -1, -2, -2, -1]


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
