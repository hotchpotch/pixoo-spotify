from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path

import httpx
from PIL import ImageFont

from pixoo_spotify.langs import get_langdetect_languages

logger = logging.getLogger(__name__)

FUSION_PIXEL_FONT_REPO = "https://github.com/TakWolf/fusion-pixel-font"
FUSION_PIXEL_FONT_LICENSE_URL = (
    "https://github.com/TakWolf/fusion-pixel-font/blob/master/LICENSE-OFL"
)
FUSION_PIXEL_FONT_RELEASES_API = (
    "https://api.github.com/repos/TakWolf/fusion-pixel-font/releases/latest"
)

FUSION_PIXEL_FONT_PATTERN = re.compile(r"fusion-pixel-font-8px-proportional-ttf-.*\.zip$")
FUSION_LANG_MAP = {
    "latin": "fallback",
    "ja": "ja",
    "ko": "ko",
    "zh_hans": "zh-cn",
    "zh_hant": "zh-tw",
}


class FontInstallError(RuntimeError):
    pass


async def fetch_latest_fusion_pixel_zip() -> tuple[str, str, str | None]:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(FUSION_PIXEL_FONT_RELEASES_API)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FontInstallError(f"Failed to fetch releases: {exc}") from exc
        payload = response.json()
        tag = payload.get("tag_name")
        assets = payload.get("assets", [])
        asset_names = [asset.get("name", "") for asset in assets]
        logger.debug("Latest release tag=%s assets=%s", tag, asset_names)
        for asset in assets:
            name = asset.get("name", "")
            if FUSION_PIXEL_FONT_PATTERN.match(name):
                url = asset.get("browser_download_url")
                if url:
                    logger.debug("Selected Fusion Pixel Font asset: %s", name)
                    return url, name, tag
    raise FontInstallError(
        "Failed to find the latest 8px proportional TTF zip asset."
    )


async def download_zip(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FontInstallError(f"Failed to download font zip: {exc}") from exc
        return response.content


async def install_recommended_fonts(fonts_dir: Path) -> tuple[dict[str, Path], str, str | None]:
    url, name, tag = await fetch_latest_fusion_pixel_zip()
    zip_bytes = await download_zip(url)
    installed = install_fusion_pixel_fonts(zip_bytes, fonts_dir)
    return installed, name, tag


def install_fusion_pixel_fonts(zip_bytes: bytes, fonts_dir: Path) -> dict[str, Path]:
    fonts_dir.mkdir(parents=True, exist_ok=True)
    installed: dict[str, Path] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.lower().endswith(".ttf"):
                continue
            lang = _resolve_fusion_lang(info.filename)
            if not lang:
                continue
            data = archive.read(info)
            _validate_font_bytes(data)
            dest = fonts_dir / f"{lang}.ttf"
            dest.write_bytes(data)
            installed[lang] = dest
            logger.debug("Installed font for lang=%s to %s", lang, dest)
    if not installed:
        raise FontInstallError("No compatible fonts found in the zip archive.")
    return installed


def install_font_for_lang(fonts_dir: Path, lang: str, font_path: Path) -> Path:
    fonts_dir.mkdir(parents=True, exist_ok=True)
    if not font_path.exists():
        raise FontInstallError(f"Font path does not exist: {font_path}")
    if font_path.suffix.lower() not in (".ttf", ".otf"):
        raise FontInstallError("Font must be a .ttf or .otf file.")
    _validate_font_file(font_path)
    dest = fonts_dir / f"{lang}{font_path.suffix.lower()}"
    dest.write_bytes(font_path.read_bytes())
    logger.debug("Installed font for lang=%s to %s", lang, dest)
    return dest


def validate_lang_code(lang: str) -> bool:
    if lang == "fallback":
        return True
    return lang in set(get_langdetect_languages())


def _resolve_fusion_lang(filename: str) -> str | None:
    stem = Path(filename).stem.lower()
    stem = stem.replace("-", "_")
    for key, lang in FUSION_LANG_MAP.items():
        if key in stem:
            return lang
    return None


def _validate_font_bytes(data: bytes) -> None:
    try:
        ImageFont.truetype(io.BytesIO(data), 8)
    except OSError as exc:
        raise FontInstallError(f"Font is not loadable at 8px: {exc}") from exc


def _validate_font_file(path: Path) -> None:
    try:
        ImageFont.truetype(str(path), 8)
    except OSError as exc:
        raise FontInstallError(f"Font is not loadable at 8px: {exc}") from exc
