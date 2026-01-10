from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_TEXT_LEN = 40


class TrackInfo(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    album: str | None = None
    artwork_url: str | None = None
    is_playing: bool = True

    @field_validator("title", "artist", "album", mode="before")
    @classmethod
    def clamp_text(cls, value: Any) -> Any:
        if value is None:
            return value
        text = str(value).strip()
        if len(text) > MAX_TEXT_LEN:
            return text[:MAX_TEXT_LEN]
        return text

    @property
    def lines(self) -> list[str]:
        return [self.title, self.artist]

    @classmethod
    def from_spotify(cls, payload: dict[str, Any]) -> TrackInfo | None:
        if not payload:
            return None
        item = payload.get("item")
        if not item:
            return None
        item_type = item.get("type") or payload.get("currently_playing_type")
        is_playing = bool(payload.get("is_playing", True))
        if item_type == "episode" or "show" in item:
            show = item.get("show") or {}
            show_name = show.get("name") or ""
            publisher = show.get("publisher") or ""
            title = item.get("name") or "Podcast episode"
            artist = show_name or publisher or "Podcast"
            album = show_name or publisher or None
            images = item.get("images") or show.get("images") or []
            artwork_url = images[0].get("url") if images else None
            return cls(
                id=item.get("id"),
                title=title,
                artist=artist,
                album=album,
                artwork_url=artwork_url,
                is_playing=is_playing,
            )
        artists = ", ".join(artist.get("name", "") for artist in item.get("artists", []))
        album = (item.get("album") or {}).get("name")
        images = (item.get("album") or {}).get("images", [])
        artwork_url = images[0].get("url") if images else None
        return cls(
            id=item.get("id"),
            title=item.get("name") or "Unknown title",
            artist=artists or "Unknown artist",
            album=album,
            artwork_url=artwork_url,
            is_playing=is_playing,
        )
