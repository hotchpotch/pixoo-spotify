from pixoo_spotify.models import TrackInfo


def test_track_info_from_spotify_episode() -> None:
    payload = {
        "is_playing": True,
        "item": {
            "type": "episode",
            "id": "episode-123",
            "name": "Episode Title",
            "show": {
                "name": "Show Name",
                "publisher": "Publisher Name",
                "images": [{"url": "https://example.com/show.jpg"}],
            },
            "images": [{"url": "https://example.com/episode.jpg"}],
        },
    }

    track = TrackInfo.from_spotify(payload)

    assert track is not None
    assert track.title == "Episode Title"
    assert track.artist == "Show Name"
    assert track.album == "Show Name"
    assert track.artwork_url == "https://example.com/episode.jpg"
