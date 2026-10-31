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


async def test_artist_previews_keeps_only_songs_and_artist_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["entity"] == "song"
        assert request.url.params["country"] == "US"
        artist = {"wrapperType": "artist", "artistId": 7, "artistName": "Artist"}
        return httpx.Response(200, json={"results": [artist, {**_song(21), "artistId": 7}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ITunesClient(Settings(itunes_country="JP"), http_client)
        tracks = await client.artist_previews("7", limit=10, country="US")

    assert [(track.source_track_id, track.artist_id) for track in tracks] == [("21", "7")]


async def test_bulk_client_retries_when_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter([403, 200])

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("herz.services.itunes.asyncio.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), json={"results": [_song(31)]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ITunesClient(Settings(), http_client, min_api_interval_sec=1.0)
        tracks = await client.lookup_previews(["31"])

    assert [track.source_track_id for track in tracks] == ["31"]
