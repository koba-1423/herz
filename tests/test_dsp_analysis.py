import numpy as np

from herz.services.dsp_analysis import analyze_waveform

SR = 22050


def _click_track(bpm: float, duration_sec: float = 8.0) -> np.ndarray:
    n_samples = int(duration_sec * SR)
    y = np.zeros(n_samples)
    interval = 60.0 / bpm
    t = 0.0
    click = np.hanning(400)
    while t < duration_sec:
        idx = int(t * SR)
        end = min(idx + len(click), n_samples)
        y[idx:end] += click[: end - idx]
        t += interval
    return y


def _chord_wave(freqs: list[float], duration_sec: float = 4.0) -> np.ndarray:
    t = np.linspace(0, duration_sec, int(duration_sec * SR), endpoint=False)
    y = np.zeros_like(t)
    for freq in freqs:
        y += np.sin(2 * np.pi * freq * t)
    return y / len(freqs)


def test_tempo_estimation_is_in_plausible_range() -> None:
    y = _click_track(bpm=120)
    features = analyze_waveform(y, SR)

    assert features.tempo_bpm is not None
    # ビート検出はオクターブ誤り（半分/倍）を起こしうるため許容範囲を広めに取る
    assert 55 <= features.tempo_bpm <= 245


def test_c_major_chord_is_detected_as_major() -> None:
    # C-E-G (C major triad)
    y = _chord_wave([261.63, 329.63, 392.00])
    features = analyze_waveform(y, SR)

    assert features.key == 0  # C
    assert features.mode == 1  # major


def test_a_minor_chord_is_detected_as_minor() -> None:
    # A-C-E (A minor triad)
    y = _chord_wave([220.00, 261.63, 329.63])
    features = analyze_waveform(y, SR)

    assert features.key == 9  # A
    assert features.mode == 0  # minor


def test_features_are_within_declared_bounds() -> None:
    y = _click_track(bpm=90)
    features = analyze_waveform(y, SR)
    energy, acousticness, speechiness = features.energy, features.acousticness, features.speechiness

    assert energy is not None and 0.0 <= energy <= 1.0
    assert acousticness is not None and 0.0 <= acousticness <= 1.0
    assert speechiness is not None and 0.0 <= speechiness <= 1.0
