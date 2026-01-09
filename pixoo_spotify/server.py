from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def create_app(gif_path: Path) -> FastAPI:
    app = FastAPI(title="pixoo-spotify")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "gif": "/gif"}

    @app.get("/gif")
    async def get_gif() -> FileResponse:
        if not gif_path.exists():
            raise HTTPException(status_code=404, detail="GIF not ready")
        return FileResponse(gif_path, media_type="image/gif")

    return app
