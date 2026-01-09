import asyncio
from pathlib import Path

from PIL import Image
from pixoo_spotify.config import GifConfig
from pixoo_spotify.gif import FontConfig, FontSpec, build_gif_bytes, load_font_registry
from pixoo_spotify.models import TrackInfo


def test_gif_generation(tmp_path: Path) -> None:
    track = TrackInfo(artist="Artist", title="Title", album="Album")
    config = GifConfig(output_path=tmp_path / "out.gif")
    font_config = FontConfig(fonts={"en": FontSpec(name="default")}, fallback_langs=["en"])

    fonts = asyncio.run(load_font_registry(font_config, tmp_path))
    gif_bytes = build_gif_bytes(track=track, config=config, fonts=fonts, artwork=None)

    output = tmp_path / "out.gif"
    output.write_bytes(gif_bytes)

    image = Image.open(output)
    assert image.format == "GIF"
    assert image.size == (config.size, config.size)
    assert getattr(image, "n_frames", 1) >= 1
