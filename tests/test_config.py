from pathlib import Path

from pixoo_spotify.config import AppConfig


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
