from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel


class PixooDevice(BaseModel):
    device_name: str
    device_id: int
    device_private_ip: str
    device_mac: str
    hardware: int

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> PixooDevice:
        return cls(
            device_name=payload.get("DeviceName", ""),
            device_id=int(payload.get("DeviceId", 0)),
            device_private_ip=payload.get("DevicePrivateIP", ""),
            device_mac=payload.get("DeviceMac", ""),
            hardware=int(payload.get("Hardware", 0)),
        )


async def discover_devices(client: httpx.AsyncClient) -> list[PixooDevice]:
    response = await client.get("https://app.divoom-gz.com/Device/ReturnSameLANDevice")
    response.raise_for_status()
    payload = response.json()
    devices = payload.get("DeviceList", [])
    return [PixooDevice.from_api(item) for item in devices]


async def play_gif(client: httpx.AsyncClient, device_ip: str, gif_url: str) -> dict[str, Any]:
    payload = {
        "Command": "Device/PlayTFGif",
        "FileType": 2,
        "FileName": gif_url,
    }
    response = await client.post(f"http://{device_ip}:80/post", json=payload)
    response.raise_for_status()
    return response.json()


async def stop_gif(client: httpx.AsyncClient, device_ip: str) -> dict[str, Any]:
    payload = {
        "Command": "Device/PlayTFGif",
        "FileType": 2,
        "FileName": "http://127.0.0.1/invalid.gif",
    }
    response = await client.post(f"http://{device_ip}:80/post", json=payload)
    response.raise_for_status()
    return response.json()


async def set_screen(client: httpx.AsyncClient, device_ip: str, on: bool) -> dict[str, Any]:
    payload = {
        "Command": "Channel/OnOffScreen",
        "OnOff": 1 if on else 0,
    }
    response = await client.post(f"http://{device_ip}:80/post", json=payload)
    response.raise_for_status()
    return response.json()
