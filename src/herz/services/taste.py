import asyncio

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herz.models.track import TrackRecord
from herz.schemas.taste import Descriptor, FeatureInsight, TasteProfile, TasteRequest
from herz.schemas.track import TrackSearchQuery
from herz.services.embedding_index import VectorIndex
from herz.services.embeddings import AudioTextEmbedder
from herz.services.track_search import search_tracks

# 好みを言葉にするための語彙 (表示名, CLAPに渡す英語)。CLAPは英語の短い説明文で学習されている
DESCRIPTORS: tuple[tuple[str, str], ...] = (
    ("切ない", "sad melancholic music"),
    ("明るい", "happy upbeat cheerful music"),
    ("穏やか", "calm peaceful relaxing music"),
    ("激しい", "intense aggressive music"),
    ("ノスタルジック", "nostalgic retro music"),
    ("ドリーミー", "dreamy ethereal atmospheric music"),
    ("ダーク", "dark ominous music"),
    ("ロマンチック", "romantic love song"),
    ("壮大", "epic cinematic orchestral music"),
    ("おしゃれ", "stylish sophisticated urban music"),
    ("グルーヴィー", "groovy funky bass line"),
    ("踊れる", "danceable four on the floor beat"),
    ("チル", "chill laid back lo-fi beats"),
    ("ピアノ", "piano"),
    ("アコースティックギター", "acoustic guitar"),
    ("歪んだエレキギター", "distorted electric guitar"),
    ("シンセサイザー", "synthesizer"),
    ("ストリングス", "string section violins"),
    ("ブラス", "brass section horns"),
    ("サックス", "saxophone"),
    ("重低音", "heavy sub bass"),
    ("打ち込みのビート", "electronic drum machine beat"),
    ("生ドラム", "live acoustic drums"),
    ("女性ボーカル", "female vocals"),
    ("男性ボーカル", "male vocals"),
    ("ハイトーンボイス", "high pitched vocals"),
    ("ささやくような歌声", "soft breathy whispering vocals"),
    ("力強い歌声", "powerful belting vocals"),
    ("ラップ", "rap vocals"),
    ("コーラス・ハーモニー", "vocal harmonies and choir"),
    ("インスト", "instrumental music without vocals"),
    ("ローファイ", "lo-fi"),
    ("音数が少ない", "minimal sparse arrangement"),
    ("音の厚み", "dense layered wall of sound"),
    ("ライブ感", "live concert recording"),
    ("ジャジー", "jazzy"),
    ("ロック", "rock"),
    ("エレクトロ", "electronic music"),
    ("ヒップホップ", "hip hop"),
    ("R&B・ソウル", "r&b soul"),
    ("フォーク", "folk"),
    ("シティポップ", "city pop"),
    ("アニソンっぽい", "anime theme song"),
    ("ボカロっぽい", "vocaloid synthesized singing voice"),
    ("ラテン", "latin rhythm"),
    ("アンビエント", "ambient"),
    ("クラシカル", "classical music"),
)

# (カラム名, 表示名)。ライブラリの中での位置（パーセンタイル）を出す
_FEATURES = (
    ("tempo_bpm", "テンポ"),
    ("energy", "エネルギー"),
    ("acousticness", "アコースティック度"),
    ("speechiness", "声・ラップの多さ"),
    ("loudness_db", "音圧"),
)
_TOP_DESCRIPTORS = 8
_AVOIDED_DESCRIPTORS = 3

_descriptor_vectors: dict[str, np.ndarray] = {}


async def analyze_taste(
    session: AsyncSession, request: TasteRequest, embedder: AudioTextEmbedder, index: VectorIndex
) -> TasteProfile:
    records = list(await session.scalars(select(TrackRecord).where(TrackRecord.id.in_(request.track_ids))))
    vectors = [
        vector
        for record in records
        if record.embedding_model == index.model_name and (vector := record.embedding_vector()) is not None
    ]

    descriptors: list[Descriptor] = []
    avoided: list[Descriptor] = []
    library_mean = await index.mean_vector(session)
    if vectors and library_mean is not None:
        # 平均同士の差を見る（どの曲にも高く出る言葉の影響を打ち消すため、ライブラリ全体の平均を引く）
        direction = np.mean(vectors, axis=0) - library_mean
        scores = await _descriptor_matrix(embedder) @ direction
        order = np.argsort(-scores)
        descriptors = [_descriptor(i, scores) for i in order[:_TOP_DESCRIPTORS] if scores[i] > 0]
        avoided = [_descriptor(i, scores) for i in order[::-1][:_AVOIDED_DESCRIPTORS] if scores[i] < 0]

    modes = [record.mode for record in records if record.mode is not None]
    recommendations = (
        await search_tracks(
            session,
            TrackSearchQuery(
                seed_track_ids=[record.id for record in records],
                exclude_seed_artists=True,
                max_per_artist=1,
                limit=request.recommendation_limit,
            ),
            embedder,
            index,
        )
        if request.recommendation_limit and vectors
        else []
    )

    return TasteProfile(
        track_count=len(vectors),
        features=await _feature_insights(session, records),
        major_ratio=sum(modes) / len(modes) if modes else None,
        descriptors=descriptors,
        avoided=avoided,
        recommendations=recommendations,
    )


async def _descriptor_matrix(embedder: AudioTextEmbedder) -> np.ndarray:
    if embedder.model_name not in _descriptor_vectors:
        vectors = [await asyncio.to_thread(embedder.embed_text, prompt) for _, prompt in DESCRIPTORS]
        _descriptor_vectors[embedder.model_name] = np.stack(vectors)
    return _descriptor_vectors[embedder.model_name]


def _descriptor(position: int, scores: np.ndarray) -> Descriptor:
    label, prompt = DESCRIPTORS[position]
    return Descriptor(label=label, prompt=prompt, score=float(scores[position]))


async def _feature_insights(session: AsyncSession, records: list[TrackRecord]) -> list[FeatureInsight]:
    insights: list[FeatureInsight] = []
    for name, label in _FEATURES:
        values = [value for record in records if (value := getattr(record, name)) is not None]
        if not values:
            continue
        mean = float(np.mean(values))
        column = getattr(TrackRecord, name)
        below, total = (
            await session.execute(
                select(func.count().filter(column < mean), func.count(column)).select_from(TrackRecord)
            )
        ).one()
        insights.append(
            FeatureInsight(
                name=name, label=label, value=mean, percentile=100.0 * below / total if total else 50.0
            )
        )
    return insights
