from __future__ import annotations

from PIL import Image

from pixoo_spotify.models import TrackInfo


def dummy_track() -> TrackInfo:
    return TrackInfo(
        id="dummy",
        title="Dummy Title for Pixoo",
        artist="Dummy Artist",
        album="Dummy Album",
        artwork_url=None,
        is_playing=True,
    )


def dummy_artwork(size: int = 64) -> Image.Image:
    return Image.new("RGB", (size, size), (30, 120, 200))
