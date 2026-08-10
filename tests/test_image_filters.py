import pytest
from PIL import Image
from pixoo_spotify.config import GifConfig
from pixoo_spotify.gif import apply_artwork_filters
from pixoo_spotify.image_filters import (
    ImageFilterGaussianBlur,
    ImageFilterResize,
    build_image_filter_chain,
)


def test_gif_config_parses_image_filters_string() -> None:
    config = GifConfig.model_validate({"image_filters": "blur:0.5|resize:32"})
    assert config.image_filters == ["blur:0.5", "resize:32"]


def test_build_image_filter_chain_appends_resize_when_missing() -> None:
    chain = build_image_filter_chain("blur:0.5", base_size=64)
    assert isinstance(chain.filters[0], ImageFilterGaussianBlur)
    tail = chain.filters[-1]
    assert isinstance(tail, ImageFilterResize)
    assert tail.size == 64


def test_default_expands_into_filters() -> None:
    chain = build_image_filter_chain("default", base_size=64)
    assert isinstance(chain.filters[0], ImageFilterGaussianBlur)
    assert isinstance(chain.filters[-1], ImageFilterResize)
    image = Image.new("RGB", (64, 64), (255, 0, 0))
    output = chain.apply(image)
    assert output.size == (64, 64)


def test_unknown_filter_is_error() -> None:
    with pytest.raises(ValueError):
        build_image_filter_chain("recommend", base_size=64)


def test_config_rejects_unknown_filter() -> None:
    with pytest.raises(ValueError):
        GifConfig(image_filters=["nope"])


@pytest.mark.parametrize(
    "filter_spec",
    [
        "resize:32,box,extra",
        "blur:0.6,median:3",
        "median:3,extra",
        "posterize:4,extra",
        "quantize:16,floyd,extra",
        "sharpen:0.5,extra",
    ],
)
def test_config_rejects_excess_filter_arguments(filter_spec: str) -> None:
    with pytest.raises(ValueError, match="accepts at most"):
        GifConfig(image_filters=[filter_spec])


def test_quantize_reduces_palette() -> None:
    image = Image.new("RGB", (64, 64))
    image.paste((255, 0, 0), (0, 0, 32, 32))
    image.paste((0, 255, 0), (32, 0, 64, 32))
    image.paste((0, 0, 255), (0, 32, 32, 64))
    image.paste((255, 255, 0), (32, 32, 64, 64))
    chain = build_image_filter_chain("quantize:2", base_size=64)
    output = chain.apply(image)
    assert len(set(output.get_flattened_data())) <= 2


def test_apply_artwork_filters_respects_resize_filter() -> None:
    config = GifConfig(size=64, image_filters=["resize:32"])
    artwork = Image.new("RGB", (64, 64), (10, 20, 30))
    filtered, size = apply_artwork_filters(artwork, config)
    assert filtered is not None
    assert filtered.size == (32, 32)
    assert size == 32


def test_apply_artwork_filters_disabled_leaves_size() -> None:
    config = GifConfig(size=64, image_filters=[])
    artwork = Image.new("RGB", (48, 48), (10, 20, 30))
    filtered, size = apply_artwork_filters(artwork, config)
    assert filtered is not None
    assert filtered.size == (48, 48)
    assert size == 64
