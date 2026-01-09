from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

MISAKI_GOTHIC_URL = (
    "https://raw.githubusercontent.com/TakWolf/fusion-pixel-font/master/"
    "assets/fonts/misaki/misaki_gothic.ttf"
)


async def ensure_font_file(path: Path, url: str) -> Path:
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    await asyncio.to_thread(path.write_bytes, response.content)
    return path
