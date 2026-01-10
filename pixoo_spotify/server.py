from __future__ import annotations

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger("pixoo_spotify.http")


def create_server(gif_path: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = _make_handler(gif_path)
    return ThreadingHTTPServer((host, port), handler)


class GifHttpServer:
    def __init__(self, gif_path: Path, host: str, port: int):
        self._gif_path = gif_path
        self._host = host
        self._port = port
        self._server = create_server(gif_path, host, port)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("HTTP server started on %s:%s", self._host, self._port)

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("HTTP server stopped")


def _make_handler(gif_path: Path) -> type[BaseHTTPRequestHandler]:
    class GifHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/" or self.path.startswith("/?"):
                payload = json.dumps({"status": "ok", "gif": "/spotify_gif"}).encode("utf-8")
                self._send_bytes(HTTPStatus.OK, payload, "application/json")
                return
            if self.path.split("?", 1)[0].startswith("/spotify_gif"):
                if not gif_path.exists():
                    self._send_bytes(HTTPStatus.NOT_FOUND, b"GIF not ready", "text/plain")
                    return
                try:
                    data = gif_path.read_bytes()
                except OSError:
                    self._send_bytes(
                        HTTPStatus.INTERNAL_SERVER_ERROR, b"Failed to read GIF", "text/plain"
                    )
                    return
                self._send_bytes(HTTPStatus.OK, data, "image/gif")
                return
            self._send_bytes(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            logger.info("%s - %s", self.client_address[0], format % args)

        def _send_bytes(self, status: HTTPStatus, data: bytes, content_type: str) -> None:
            self.send_response(status.value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return GifHandler
