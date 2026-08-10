from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PIL import Image, ImageOps
from PIL import ImageFilter as PilImageFilter

DEFAULT_IMAGE_FILTER_SPECS: tuple[str, ...] = (
    "blur:0.6",
    "median:3",
    "posterize:4",
    "quantize:32",
)


class ImageFilterBase:
    """Base class for artwork image filters."""

    name: str = "base"
    changes_size: bool = False

    def apply(self, image: Image.Image) -> Image.Image:
        raise NotImplementedError


@dataclass(frozen=True)
class ImageFilterChain:
    """Apply a sequence of image filters in order."""

    filters: tuple[ImageFilterBase, ...]

    def apply(self, image: Image.Image) -> Image.Image:
        output = image.convert("RGB")
        for filter_item in self.filters:
            output = filter_item.apply(output)
        return output

    @property
    def changes_size(self) -> bool:
        return any(filter_item.changes_size for filter_item in self.filters)


@dataclass(frozen=True)
class ImageFilterResize(ImageFilterBase):
    """Resize artwork to a square size using a PIL resample filter."""

    size: int
    resample: Image.Resampling
    name: str = "resize"
    changes_size: bool = True

    def apply(self, image: Image.Image) -> Image.Image:
        if image.size == (self.size, self.size):
            return image
        return image.resize((self.size, self.size), self.resample)


@dataclass(frozen=True)
class ImageFilterGaussianBlur(ImageFilterBase):
    """Apply a light Gaussian blur to suppress moire and noise."""

    radius: float = 0.6
    name: str = "blur"

    def apply(self, image: Image.Image) -> Image.Image:
        if self.radius <= 0:
            return image
        return image.filter(PilImageFilter.GaussianBlur(self.radius))


@dataclass(frozen=True)
class ImageFilterMedian(ImageFilterBase):
    """Reduce salt-and-pepper noise with a median filter."""

    size: int = 3
    name: str = "median"

    def apply(self, image: Image.Image) -> Image.Image:
        if self.size <= 1:
            return image
        return image.filter(PilImageFilter.MedianFilter(self.size))


@dataclass(frozen=True)
class ImageFilterPosterize(ImageFilterBase):
    """Reduce per-channel bit depth to emphasize pixel art blocks."""

    bits: int = 4
    name: str = "posterize"

    def apply(self, image: Image.Image) -> Image.Image:
        return ImageOps.posterize(image, self.bits)


@dataclass(frozen=True)
class ImageFilterQuantize(ImageFilterBase):
    """Limit palette size with optional dithering (default none)."""

    colors: int = 32
    dither: Image.Dither = Image.Dither.NONE
    name: str = "quantize"

    def apply(self, image: Image.Image) -> Image.Image:
        quantized = image.quantize(colors=self.colors, dither=self.dither)
        return quantized.convert("RGB")


@dataclass(frozen=True)
class ImageFilterSharpen(ImageFilterBase):
    """Sharpen edges using a blend with PIL's SHARPEN filter."""

    strength: float = 0.4
    name: str = "sharpen"

    def apply(self, image: Image.Image) -> Image.Image:
        if self.strength <= 0:
            return image
        sharpened = image.filter(PilImageFilter.SHARPEN)
        if self.strength >= 1:
            return sharpened
        return Image.blend(image, sharpened, self.strength)


_RESAMPLE_ALIASES: dict[str, Image.Resampling] = {
    "nearest": Image.Resampling.NEAREST,
    "box": Image.Resampling.BOX,
    "area": Image.Resampling.BOX,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}

_DITHER_ALIASES: dict[str, Image.Dither] = {
    "none": Image.Dither.NONE,
    "off": Image.Dither.NONE,
    "floyd": Image.Dither.FLOYDSTEINBERG,
    "floydsteinberg": Image.Dither.FLOYDSTEINBERG,
}


def build_image_filter_chain(
    filters: str | Iterable[str] | None,
    *,
    base_size: int,
) -> ImageFilterChain:
    """Parse filter specs into a chain; ensures final resize if none specified."""
    specs = _normalize_filter_specs(filters)
    parsed: list[ImageFilterBase] = []
    for spec in specs:
        if spec.lower() == "default":
            parsed.extend(_parse_default_filters())
            continue
        parsed.append(_parse_filter_spec(spec))
    if not parsed or not any(filter_item.changes_size for filter_item in parsed):
        parsed.append(
            ImageFilterResize(size=base_size, resample=Image.Resampling.LANCZOS)
        )
    return ImageFilterChain(tuple(parsed))


def format_image_filter_chain(chain: ImageFilterChain) -> str:
    """Return a readable description for logging/debugging."""

    return " | ".join(_describe_filter(filter_item) for filter_item in chain.filters)


def _normalize_filter_specs(filters: str | Iterable[str] | None) -> list[str]:
    if filters is None:
        return []
    if isinstance(filters, str):
        text = filters.strip()
        if not text:
            return []
        return [part.strip() for part in text.split("|") if part.strip()]
    specs: list[str] = []
    for item in filters:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        if "|" in text:
            specs.extend(part.strip() for part in text.split("|") if part.strip())
        else:
            specs.append(text)
    return specs


def _parse_filter_spec(spec: str) -> ImageFilterBase:
    name, args = _split_name_args(spec)
    key = name.lower()
    if key in {""}:
        raise ValueError("image filter name is required")
    if key in {"default"}:
        raise ValueError("default must be used as a standalone filter spec")
    if key in {"resize", "scale"}:
        return _parse_resize(args)
    if key in {"blur", "gaussian"}:
        return _parse_blur(args)
    if key == "median":
        return _parse_median(args)
    if key == "posterize":
        return _parse_posterize(args)
    if key == "quantize":
        return _parse_quantize(args)
    if key == "sharpen":
        return _parse_sharpen(args)
    raise ValueError(f"Unknown image filter: {name}")


def _split_name_args(spec: str) -> tuple[str, str]:
    for sep in (":", "="):
        if sep in spec:
            name, args = spec.split(sep, 1)
            return name.strip(), args.strip()
    return spec.strip(), ""


def _split_args(args: str) -> list[str]:
    return [part.strip() for part in args.split(",") if part.strip()]


def _parse_resize(args: str) -> ImageFilterResize:
    parts = _split_args(args)
    if not parts:
        raise ValueError("resize requires a size (16/32/64)")
    if len(parts) > 2:
        raise ValueError("resize accepts at most 2 arguments")
    try:
        size = int(parts[0])
    except ValueError as exc:
        raise ValueError("resize size must be an integer") from exc
    if size not in (16, 32, 64):
        raise ValueError("resize size must be 16, 32, or 64")
    resample_name = parts[1].lower() if len(parts) > 1 else "lanczos"
    resample = _RESAMPLE_ALIASES.get(resample_name)
    if resample is None:
        raise ValueError(
            "resize resample must be one of nearest, box, bilinear, bicubic, lanczos"
        )
    return ImageFilterResize(size=size, resample=resample)


def _parse_blur(args: str) -> ImageFilterGaussianBlur:
    parts = _split_args(args)
    if len(parts) > 1:
        raise ValueError("blur accepts at most 1 argument")
    if not parts:
        return ImageFilterGaussianBlur()
    try:
        radius = float(parts[0])
    except ValueError as exc:
        raise ValueError("blur radius must be a number") from exc
    if radius < 0:
        raise ValueError("blur radius must be >= 0")
    return ImageFilterGaussianBlur(radius=radius)


def _parse_median(args: str) -> ImageFilterMedian:
    parts = _split_args(args)
    if len(parts) > 1:
        raise ValueError("median accepts at most 1 argument")
    if not parts:
        return ImageFilterMedian()
    try:
        size = int(parts[0])
    except ValueError as exc:
        raise ValueError("median size must be an integer") from exc
    if size < 1 or size % 2 == 0:
        raise ValueError("median size must be an odd integer >= 1")
    return ImageFilterMedian(size=size)


def _parse_posterize(args: str) -> ImageFilterPosterize:
    parts = _split_args(args)
    if len(parts) > 1:
        raise ValueError("posterize accepts at most 1 argument")
    if not parts:
        return ImageFilterPosterize()
    try:
        bits = int(parts[0])
    except ValueError as exc:
        raise ValueError("posterize bits must be an integer") from exc
    if bits < 1 or bits > 8:
        raise ValueError("posterize bits must be between 1 and 8")
    return ImageFilterPosterize(bits=bits)


def _parse_quantize(args: str) -> ImageFilterQuantize:
    parts = _split_args(args)
    if len(parts) > 2:
        raise ValueError("quantize accepts at most 2 arguments")
    if not parts:
        return ImageFilterQuantize()
    try:
        colors = int(parts[0])
    except ValueError as exc:
        raise ValueError("quantize colors must be an integer") from exc
    if colors < 2 or colors > 256:
        raise ValueError("quantize colors must be between 2 and 256")
    dither = Image.Dither.NONE
    if len(parts) > 1:
        dither_name = parts[1].lower()
        dither = _DITHER_ALIASES.get(dither_name)
        if dither is None:
            raise ValueError("quantize dither must be none or floyd")
    return ImageFilterQuantize(colors=colors, dither=dither)


def _parse_sharpen(args: str) -> ImageFilterSharpen:
    parts = _split_args(args)
    if len(parts) > 1:
        raise ValueError("sharpen accepts at most 1 argument")
    if not parts:
        return ImageFilterSharpen()
    try:
        strength = float(parts[0])
    except ValueError as exc:
        raise ValueError("sharpen strength must be a number") from exc
    if strength < 0 or strength > 1:
        raise ValueError("sharpen strength must be between 0 and 1")
    return ImageFilterSharpen(strength=strength)


def _parse_default_filters() -> list[ImageFilterBase]:
    filters: list[ImageFilterBase] = []
    for spec in DEFAULT_IMAGE_FILTER_SPECS:
        filters.append(_parse_filter_spec(spec))
    return filters


def _describe_filter(filter_item: ImageFilterBase) -> str:
    if isinstance(filter_item, ImageFilterResize):
        resample_name = _resample_name(filter_item.resample)
        return f"resize:{filter_item.size},{resample_name}"
    if isinstance(filter_item, ImageFilterGaussianBlur):
        return f"blur:{filter_item.radius}"
    if isinstance(filter_item, ImageFilterMedian):
        return f"median:{filter_item.size}"
    if isinstance(filter_item, ImageFilterPosterize):
        return f"posterize:{filter_item.bits}"
    if isinstance(filter_item, ImageFilterQuantize):
        dither_name = "floyd" if filter_item.dither == Image.Dither.FLOYDSTEINBERG else "none"
        return f"quantize:{filter_item.colors},{dither_name}"
    if isinstance(filter_item, ImageFilterSharpen):
        return f"sharpen:{filter_item.strength}"
    return filter_item.name


def _resample_name(resample: Image.Resampling) -> str:
    for name, value in _RESAMPLE_ALIASES.items():
        if value == resample:
            return name
    return "lanczos"
