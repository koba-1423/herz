import io

import librosa
import numpy as np

from herz.schemas.track import TrackFeatures

# Krumhansl-Kessler の調性プロファイル（Cを基準としたクロマ12音の重み）
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_ANALYSIS_SR = 22050


def _estimate_key(chroma: np.ndarray) -> tuple[int, int]:
    """クロマベクトルの平均と調性プロファイルの相関から主音・長短調を推定する (Krumhansl-Schmuckler法)。"""
    chroma_mean = chroma.mean(axis=1)
    best_score = -np.inf
    best_key = 0
    best_mode = 1

    for shift in range(12):
        major_corr = np.corrcoef(np.roll(_MAJOR_PROFILE, shift), chroma_mean)[0, 1]
        minor_corr = np.corrcoef(np.roll(_MINOR_PROFILE, shift), chroma_mean)[0, 1]

        if major_corr > best_score:
            best_score = major_corr
            best_key = shift
            best_mode = 1
        if minor_corr > best_score:
            best_score = minor_corr
            best_key = shift
            best_mode = 0

    return best_key, best_mode


def analyze_waveform(y: np.ndarray, sr: int) -> TrackFeatures:
    """波形データから音響特徴量を抽出する（信号処理ベースのv1実装）。

    tempo / key / mode / loudness_db / energy / acousticness / speechiness は
    信号処理の指標から直接算出したもの。danceability / valence / instrumentalness /
    liveness はSpotifyが提供していたような意味的な軸を再現できるだけの根拠が
    信号処理単体では得られないため、v1では意図的に含めていない
    （フェーズ2で学習済みモデル/埋め込みによる算出を想定）。
    """
    # librosa.beat.beat_track(y=...) はテンポ0を返すことがあるため、
    # onset_strengthを明示的に経由するlibrosa.feature.tempoを使う
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key, mode = _estimate_key(chroma)

    rms = librosa.feature.rms(y=y)[0]
    loudness_db = float(librosa.amplitude_to_db(np.array([rms.mean()]))[0])
    energy = float(np.clip(rms.mean() * 10, 0.0, 1.0))

    harmonic, percussive = librosa.effects.hpss(y)
    harmonic_energy = float(np.sum(harmonic**2))
    percussive_energy = float(np.sum(percussive**2))
    acousticness = float(np.clip(harmonic_energy / (harmonic_energy + percussive_energy + 1e-9), 0.0, 1.0))

    zcr = librosa.feature.zero_crossing_rate(y)[0]
    speechiness = float(np.clip(zcr.mean() * 5, 0.0, 1.0))

    return TrackFeatures(
        tempo_bpm=tempo,
        key=key,
        mode=mode,
        energy=energy,
        acousticness=acousticness,
        speechiness=speechiness,
        loudness_db=loudness_db,
    )


class DspAudioFeatureExtractor:
    """librosaによる信号処理ベースのAudioFeatureExtractor実装。"""

    def extract(self, audio_bytes: bytes) -> TrackFeatures:
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=_ANALYSIS_SR, mono=True)
        return analyze_waveform(y, int(sr))
