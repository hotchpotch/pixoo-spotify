from pathlib import Path

from pixoo_spotify.config import AppConfig, normalize_language_tag


def test_config_merge(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
idle_poll_interval = 25

[server]
port = 9000
host = "127.0.0.1"

[greeting]
unused = true

""".strip(),
        encoding="utf-8",
    )
    overrides = {"server": {"port": 1234}}
    config = AppConfig.from_sources(config_path, overrides)
    assert config.server.port == 1234
    assert config.server.host == "127.0.0.1"
    assert config.idle_poll_interval == 25


def test_normalize_language_tag() -> None:
    assert normalize_language_tag("ja_JP.UTF-8") == "ja-JP"
    assert normalize_language_tag("en") == "en"
    assert normalize_language_tag("pt_BR") == "pt-BR"
    assert normalize_language_tag("C") == ""
