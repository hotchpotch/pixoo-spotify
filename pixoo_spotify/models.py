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
        return [self.artist, self.title]

    @classmethod
    def from_spotify(cls, payload: dict[str, Any]) -> TrackInfo | None:
        if not payload:
            return None
        item = payload.get("item")
        if not item:
            return None
        artists = ", ".join(artist.get("name", "") for artist in item.get("artists", []))
        album = (item.get("album") or {}).get("name")
        images = (item.get("album") or {}).get("images", [])
        artwork_url = images[0].get("url") if images else None
        return cls(
            id=item.get("id"),
            title=item.get("name") or "",
            artist=artists or "",
            album=album,
            artwork_url=artwork_url,
            is_playing=bool(payload.get("is_playing", True)),
        )
