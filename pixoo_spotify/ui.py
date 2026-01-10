from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pixoo_spotify.models import TrackInfo

console = Console()


def render_track(track: TrackInfo) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold cyan", width=8)
    table.add_column(style="white")
    table.add_row("Artist", track.artist)
    table.add_row("Title", track.title)
    table.add_row("Album", track.album or "-")
    table.add_row("Artwork", str(track.artwork_url or "-"))
    panel = Panel(table, title="Now Playing", expand=False)
    console.print(panel)
