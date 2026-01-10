from __future__ import annotations

import io
import zipfile
from importlib import resources
from pathlib import Path

import pytest
from pixoo_spotify import fonts as font_module
from pixoo_spotify.fonts import FontInstallError, install_font_for_lang, install_fusion_pixel_fonts


def _misaki_bytes() -> bytes:
    resource = resources.files("pixoo_spotify") / "fonts/misaki/misaki_gothic.ttf"
    return resource.read_bytes()


def test_install_fusion_pixel_fonts(tmp_path: Path) -> None:
    font_bytes = _misaki_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in ["latin.ttf", "ja.ttf", "ko.ttf", "zh_hans.ttf", "zh_hant.ttf"]:
            archive.writestr(f"fusion/{name}", font_bytes)
    installed = install_fusion_pixel_fonts(buffer.getvalue(), tmp_path)
    assert installed["fallback"].exists()
    assert installed["ja"].exists()
    assert installed["ko"].exists()
    assert installed["zh-cn"].exists()
    assert installed["zh-tw"].exists()


def test_install_fusion_pixel_fonts_empty_zip(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("fusion/readme.txt", "no fonts here")
    with pytest.raises(FontInstallError):
        install_fusion_pixel_fonts(buffer.getvalue(), tmp_path)


def test_install_font_for_lang(tmp_path: Path, monkeypatch) -> None:
    font_path = tmp_path / "source.ttf"
    font_path.write_bytes(_misaki_bytes())
    fonts_dir = tmp_path / "fonts"
    dest = install_font_for_lang(fonts_dir, "en", font_path)
    assert dest.exists()
    assert dest.read_bytes() == font_path.read_bytes()


def test_validate_lang_code(monkeypatch) -> None:
    monkeypatch.setattr(font_module, "get_langdetect_languages", lambda: ["en", "ja"])
    assert font_module.validate_lang_code("en") is True
    assert font_module.validate_lang_code("fallback") is True
    assert font_module.validate_lang_code("xx") is False
