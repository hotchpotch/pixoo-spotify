import asyncio
import json

import httpx
from pixoo_spotify.pixoo import discover_devices, play_gif


def test_discover_devices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://app.divoom-gz.com/Device/ReturnSameLANDevice")
        payload = {
            "DeviceList": [
                {
                    "DeviceName": "Pixoo64",
                    "DeviceId": 300346233,
                    "DevicePrivateIP": "192.168.24.83",
                    "DeviceMac": "5c013b48f370",
                    "Hardware": 92,
                }
            ]
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            devices = await discover_devices(client)
            assert len(devices) == 1
            device = devices[0]
            assert device.device_name == "Pixoo64"
            assert device.device_private_ip == "192.168.24.83"

    asyncio.run(run())


def test_play_gif_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://192.168.24.83:80/post")
        body = json.loads(request.content.decode("utf-8"))
        assert body["Command"] == "Device/PlayTFGif"
        assert body["FileType"] == 2
        assert body["FileName"] == "http://example.com/spotify_gif?123"
        return httpx.Response(200, json={"error_code": 0})

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            response = await play_gif(
                client, "192.168.24.83", "http://example.com/spotify_gif?123"
            )
            assert response["error_code"] == 0

    asyncio.run(run())
