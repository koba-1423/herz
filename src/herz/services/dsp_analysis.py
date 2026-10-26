import io

import av
import librosa
import numpy as np
import soundfile

from herz.schemas.track import TrackFeatures

# Krumhansl-Kessler の調性プロファイル（Cを基準としたクロマ12音の重み）
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_ANALYSIS_SR = 22050

# energy算出で0-1に写像する範囲 (下限, 上限)
_LOUDNESS_DB_RANGE = (-30.0, -6.0)
_CENTROID_HZ_RANGE = (300.0, 3500.0)


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


def _estimate_energy(y: np.ndarray, sr: int, loudness_db: float) -> float:
    """音圧と音の明るさ（スペクトル重心）を組み合わせて0-1の強度を推定する。

    マスタリング済みの市販音源はRMSが0.1-0.45程度に集中するため、RMSの線形スケールでは
    ほぼ全曲が上限に張り付く。dBに変換した音圧と、歪んだギターやシンセで高くなる
    スペクトル重心を、iTunesプレビューの実測分布 (アンビエント〜EDM/メタル) をもとに
    それぞれ0-1へ写像して重み付けしている。
    """
    loudness = np.clip((loudness_db - _LOUDNESS_DB_RANGE[0]) / np.ptp(_LOUDNESS_DB_RANGE), 0.0, 1.0)
    centroid_hz = float(librosa.feature.spectral_centroid(y=y, sr=sr)[0].mean())
    brightness = np.clip((centroid_hz - _CENTROID_HZ_RANGE[0]) / np.ptp(_CENTROID_HZ_RANGE), 0.0, 1.0)
    return float(0.6 * loudness + 0.4 * brightness)


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
    energy = _estimate_energy(y, sr, loudness_db)

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


def decode_audio(audio_bytes: bytes, sr: int = _ANALYSIS_SR) -> np.ndarray:
    """音声バイト列をモノラル・指定サンプルレートの波形に変換する。

    WAV/FLAC/MP3 等 libsndfile が読める形式は librosa で読み込み、iTunesプレビュー
    (AAC/m4a) のように読めない形式は ffmpeg を同梱した PyAV でデコードする。
    """
    try:
        y, _ = librosa.load(io.BytesIO(audio_bytes), sr=sr, mono=True)
        return y
    except soundfile.LibsndfileError:
        pass

    resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
    chunks: list[np.ndarray] = []
    with av.open(io.BytesIO(audio_bytes), mode="r") as container:
        for frame in container.decode(audio=0):
            chunks.extend(resampled.to_ndarray().reshape(-1) for resampled in resampler.resample(frame))
    chunks.extend(resampled.to_ndarray().reshape(-1) for resampled in resampler.resample(None))

    if not chunks:
        raise ValueError("no audio frames decoded")
    return np.concatenate(chunks)


class DspAudioFeatureExtractor:
    """librosaによる信号処理ベースのAudioFeatureExtractor実装。"""

    def extract(self, audio_bytes: bytes) -> TrackFeatures:
        return analyze_waveform(decode_audio(audio_bytes), _ANALYSIS_SR)
