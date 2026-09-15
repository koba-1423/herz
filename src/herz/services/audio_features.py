from typing import Protocol

from herz.schemas.track import TrackFeatures


class AudioFeatureExtractor(Protocol):
    """音声データから音響特徴量を抽出する手段を抽象化するインターフェース。

    現状はlibrosaによる信号処理ベースの実装（DspAudioFeatureExtractor）のみ。
    将来、学習済みモデル（ムード・ジャンル分類器や音声埋め込み）による実装に
    差し替え・併用できるよう、音声バイト列を入力とするインターフェースにしてある。
    """

    def extract(self, audio_bytes: bytes) -> TrackFeatures: ...
