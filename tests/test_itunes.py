import httpx
import pytest

from herz.core.config import Settings
from herz.services.itunes import ITunesClient


def _song(track_id: int, preview: bool = True) -> dict[str, object]:
    return {
        "kind": "song",
        "trackId": track_id,
        "trackName": f"Song {track_id}",
        "artistName": "Artist",
        "primaryGenreName": "Jazz",
        "previewUrl": f"https://audio.example/{track_id}.m4a" if preview else None,
    }


@pytest.mark.parametrize("single_entry", [False, True])
async def test_chart_previews_resolves_chart_ids_via_lookup(single_entry: bool) -> None:
    requested: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url)
        if "/rss/topsongs/" in request.url.path:
            entries = [{"id": {"attributes": {"im:id": str(i)}}} for i in (11, 12)]
            return httpx.Response(200, json={"feed": {"entry": entries[0] if single_entry else entries}})
        ids = [int(i) for i in request.url.params["id"].split(",")]
        return httpx.Response(200, json={"results": [_song(i, preview=i != 12) for i in ids]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ITunesClient(Settings(itunes_country="JP"), http_client)
        tracks = await client.chart_previews(genre_id=11, limit=2)

    assert [track.source_track_id for track in tracks] == ["11"]  # プレビューの無い曲は除外
    assert requested[0].path == "/jp/rss/topsongs/limit=2/genre=11/json"
    assert requested[1].params["country"] == "JP"
