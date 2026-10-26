import numpy as np

from herz.services.embeddings import split_into_windows

SR = 48000


def test_preview_is_split_into_ten_second_windows() -> None:
    windows = split_into_windows(np.zeros(30 * SR), SR)

    assert [len(window) for window in windows] == [10 * SR] * 3


def test_short_tail_is_dropped_but_long_tail_is_kept() -> None:
    assert [len(w) for w in split_into_windows(np.zeros(23 * SR), SR)] == [10 * SR, 10 * SR]
    assert [len(w) for w in split_into_windows(np.zeros(27 * SR), SR)] == [10 * SR, 10 * SR, 7 * SR]


def test_audio_shorter_than_one_window_is_kept() -> None:
    assert [len(w) for w in split_into_windows(np.zeros(3 * SR), SR)] == [3 * SR]
