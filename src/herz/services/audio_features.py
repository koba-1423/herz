from typing import Protocol

from herz.schemas.track import TrackFeatures


class AudioFeatureProvider(Protocol):
    """曲の音響特徴量を取得する手段を抽象化するインターフェース。

    Spotifyの公式Audio Features/Analysis APIは2024年11月以降、新規アプリからは
    利用できなくなっている（既存の拡張アクセス済みアプリのみ利用可）。そのため
    実装を差し替えられるようにしておき、将来的にlibrosaなどによる自前解析や
    他プロバイダへの切り替えに対応できるようにする。
    """

    async def get_features(self, track_id: str) -> TrackFeatures: ...
