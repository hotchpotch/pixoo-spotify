from __future__ import annotations

from pixoo_spotify.models import TrackInfo


def render_track(track: TrackInfo) -> None:
    lines = [
        "Now Playing",
        f"Artist : {track.artist}",
        f"Title  : {track.title}",
        f"Album  : {track.album or '-'}",
        f"Artwork: {track.artwork_url or '-'}",
    ]
    print("\n".join(lines))
