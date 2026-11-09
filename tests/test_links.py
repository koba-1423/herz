import httpx
import pytest

from herz.services.links import UnsupportedLinkError, rank_by_title, resolve_link, youtube_search_terms


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "open.spotify.com":
        assert request.url.path == "/oembed"
        # 貼られたURLではなくIDから組み立てる
        assert request.url.params["url"] == "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        return httpx.Response(200, json={"title": "Never Gonna Give You Up"})
    if request.url.path == "/oembed":
        assert request.url.params["url"] == "https://www.youtube.com/watch?v=x8VYWazR5mE"
        return httpx.Response(
            200,
            json={"title": "YOASOBI「夜に駆ける」 Official Music Video", "author_name": "Ayase / YOASOBI"},
        )
    raise AssertionError(f"unexpected request: {request.url}")


async def _resolve(url: str):  # type: ignore[no-untyped-def]
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as http:
        return await resolve_link(url, http)


async def test_apple_music_urls_carry_itunes_ids() -> None:
    song = await _resolve("https://music.apple.com/jp/album/yoru-ni-kakeru/1542182770?i=1542182776")
    assert (song.track_id, song.country) == ("1542182776", "JP")

    single = await _resolve("https://music.apple.com/us/song/lemon/1537460612")
    assert single.track_id == "1537460612"

    album = await _resolve("https://music.apple.com/jp/album/stray-sheep/1530947020")
    assert (album.album_id, album.track_id) == ("1530947020", None)


async def test_spotify_track_title_comes_from_oembed() -> None:
    lookup = await _resolve("https://open.spotify.com/intl-ja/track/4cOdK2wGLETKBW3PvgPWqT?si=x")
    assert lookup.detected == "Never Gonna Give You Up"
    assert lookup.search_terms == ("Never Gonna Give You Up",)


async def test_youtube_video_title_becomes_search_terms() -> None:
    lookup = await _resolve("https://youtu.be/x8VYWazR5mE?t=10")
    assert lookup.search_terms[0] == "夜に駆ける YOASOBI"


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", "Spotify"),
        ("https://www.youtube.com/@YOASOBI", "YouTube"),
        ("https://example.com/song", "対応"),
    ],
)
async def test_unsupported_links_are_rejected(url: str, message: str) -> None:
    with pytest.raises(UnsupportedLinkError, match=message):
        await _resolve(url)


def test_youtube_search_terms_handle_common_title_styles() -> None:
    terms = youtube_search_terms(
        "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)", "Rick Astley"
    )
    assert "Never Gonna Give You Up Rick Astley" in terms[:2]
    assert (
        youtube_search_terms("【MV】マリーゴールド／あいみょん", "あいみょん")[0]
        == "あいみょん マリーゴールド"
    )


def test_rank_by_title_prefers_the_original_version() -> None:
    titles = ["白日 (Live at TOKYO DOME)", "白日", "Never Gonna Give You Up (Pianoforte)"]
    assert rank_by_title(titles, "白日 King Gnu") == [1, 0, 2]
