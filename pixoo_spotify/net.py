from __future__ import annotations

import socket
from typing import Final


def local_ip_for_target(target_ip: str, target_port: int = 80) -> str | None:
    """Return the local IP used to reach the target, or None if it cannot be determined."""
    timeout: Final[float] = 0.5
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.connect((target_ip, target_port))
            local_ip = sock.getsockname()[0]
        if local_ip and local_ip != "0.0.0.0":
            return local_ip
    except OSError:
        return None
    return None


def find_open_port(host: str, start: int, end: int) -> int | None:
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, port))
                return port
        except OSError:
            continue
    return None
