from urllib.parse import unquote

import httpx
from fastapi import FastAPI

from herz.services.query_translation import QueryTranslator, glossary_keywords
from tests.conftest import enable_fake_embedder


class EchoTranslator:
    def translate(self, text: str) -> str:
        return f"translated({text})"


def test_glossary_turns_music_slang_into_keywords() -> None:
    assert glossary_keywords("雨の日に聴きたい切ないピアノ") == ["rainy", "sad melancholic", "piano"]
    assert glossary_keywords("疾走感のあるハードロック") == ["fast driving energetic", "hard rock"]
    assert glossary_keywords("ｴﾓいシティポップ") == ["emotional nostalgic", "city pop"]  # 半角カナも拾う


def test_translator_passes_english_through_and_falls_back_for_unknown_words() -> None:
    translator = QueryTranslator(fallback=EchoTranslator())

    assert translator.to_english("smooth jazz saxophone") == "smooth jazz saxophone"
    assert translator.to_english("チルいlo-fi") == "a chill lo-fi song"
    assert translator.to_english("アニソンっぽいEDM") == "a anime edm song"
    assert translator.to_english("こんにちは") == "translated(こんにちは)"
    assert QueryTranslator().to_english("こんにちは") == "こんにちは"


async def test_search_translates_japanese_queries(app: FastAPI, client: httpx.AsyncClient) -> None:
    enable_fake_embedder(app)
    await client.post("/ingest", json={"term": "anything"})

    response = await client.post("/search", json={"text": "激しいメタル"})

    assert unquote(response.headers["x-herz-query"]) == "a intense aggressive heavy metal song"
    assert response.json()[0]["id"] == "itunes:4"
