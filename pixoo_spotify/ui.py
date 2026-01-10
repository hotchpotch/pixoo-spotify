from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pixoo_spotify.config import LogFormat
from pixoo_spotify.models import TrackInfo

logger = logging.getLogger("pixoo_spotify.ui")


class LogBuffer:
    def __init__(self, title: str, max_lines: int = 200):
        self._title = title
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def append(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)

    def render(self) -> Panel:
        with self._lock:
            text = Text("\n".join(self._lines))
        return Panel(text, title=self._title, border_style="blue")


class AppUI:
    def __init__(self) -> None:
        self._console = Console()
        self._layout = Layout()
        self._track_panel = Panel("No track", title="Now Playing", border_style="green")
        self._log = LogBuffer("Logs")
        self._lock = threading.Lock()

        self._layout.split_column(
            Layout(name="track", size=6),
            Layout(name="logs"),
        )
        self._refresh()
        self._live = Live(self._layout, console=self._console, refresh_per_second=4)

    def start(self) -> None:
        self._live.start()

    def stop(self) -> None:
        self._live.stop()

    def update_track(self, track: TrackInfo) -> None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold cyan", width=8)
        table.add_column(style="white")
        table.add_row("Title", track.title)
        table.add_row("Artist", track.artist)
        table.add_row("Album", track.album or "-")
        table.add_row("Artwork", str(track.artwork_url or "-"))
        panel = Panel(table, title="Now Playing", border_style="green", expand=True)
        with self._lock:
            self._track_panel = panel
        self._refresh()

    def append_log(self, line: str) -> None:
        self._log.append(line)
        self._refresh()

    def _refresh(self) -> None:
        with self._lock:
            self._layout["track"].update(self._track_panel)
        self._layout["logs"].update(self._log.render())


class UILogHandler(logging.Handler):
    def __init__(self, append: Callable[[str], None], level: int = logging.INFO):
        super().__init__(level=level)
        self._append = append

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        self._append(message)


_UI: AppUI | None = None


def start_ui() -> AppUI:
    global _UI
    if _UI is None:
        _UI = AppUI()
        _UI.start()
    return _UI


def stop_ui() -> None:
    global _UI
    if _UI is not None:
        _UI.stop()
        _UI = None


def render_track(track: TrackInfo) -> None:
    if _UI is not None:
        _UI.update_track(track)
        return
    logger.info(
        "Now Playing | Title=%s | Artist=%s | Album=%s | Artwork=%s",
        track.title,
        track.artist,
        track.album or "-",
        track.artwork_url or "-",
    )


def configure_logging(
    background: bool, verbose: bool, ui: AppUI | None, log_format: LogFormat
) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    if log_format is LogFormat.basic:
        log_format_value = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    else:
        log_format_value = "%(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format_value, datefmt=date_format)

    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    httpx_logger.setLevel(logging.WARNING)
    httpcore_logger.setLevel(logging.WARNING)

    if background or ui is None:
        logging.basicConfig(level=level, format=log_format_value, datefmt=date_format)
        return

    logging.basicConfig(level=logging.WARNING)
    app_handler = UILogHandler(ui.append_log, level=level)
    app_handler.setFormatter(formatter)

    app_logger = logging.getLogger("pixoo_spotify")
    app_logger.handlers = [app_handler]
    app_logger.setLevel(level)
    app_logger.propagate = False

    http_logger = logging.getLogger("pixoo_spotify.http")
    http_logger.setLevel(level)
    http_logger.propagate = True
