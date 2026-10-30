import threading
from typing import TYPE_CHECKING, Protocol

import numpy as np

from herz.services.dsp_analysis import decode_audio

if TYPE_CHECKING:
    from transformers import ClapModel, ClapProcessor

_CLAP_SR = 48000
# CLAP(unfused)が一度に受け付ける長さ。これより長い音声はプロセッサがランダムに切り出してしまう
_WINDOW_SEC = 10.0
# 末尾の端数がこれより短ければ捨てる（無音に近いパディングが平均を薄めるのを避ける）
_MIN_TAIL_SEC = 5.0


class AudioTextEmbedder(Protocol):
    """音声と自然文を同じベクトル空間に埋め込む手段を抽象化するインターフェース。

    返すベクトルはL2正規化済みのfloat32で、内積がそのままコサイン類似度になる。
    """

    model_name: str

    def embed_audio(self, audio_bytes: bytes) -> np.ndarray: ...

    def embed_text(self, text: str) -> np.ndarray: ...


def split_into_windows(y: np.ndarray, sr: int) -> list[np.ndarray]:
    window = int(_WINDOW_SEC * sr)
    windows = [y[start : start + window] for start in range(0, len(y), window)]
    if len(windows) > 1 and len(windows[-1]) < _MIN_TAIL_SEC * sr:
        windows.pop()
    return windows


def _normalize(vector: np.ndarray) -> np.ndarray:
    return (vector / (np.linalg.norm(vector) + 1e-12)).astype(np.float32)


class ClapEmbedder:
    """LAION CLAP (transformers実装) によるAudioTextEmbedder。

    `laion/larger_clap_music` はテキスト側の埋め込みが入力によらずほぼ同一になり使えないため、
    実際のiTunesプレビューでの検索精度を比較して `laion/larger_clap_general` を既定にしている。
    テキストエンコーダは英語のみ対応。モデルは初回利用時に読み込む（初回はダウンロードが走る）。
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: ClapModel | None = None
        self._processor: ClapProcessor | None = None
        # 推論は同時実行してもCPUを奪い合うだけなので直列化する
        self._lock = threading.Lock()

    def _load(self) -> tuple["ClapModel", "ClapProcessor"]:
        from transformers import ClapModel, ClapProcessor

        if self._model is None or self._processor is None:
            self._model = ClapModel.from_pretrained(self.model_name).eval()
            self._processor = ClapProcessor.from_pretrained(self.model_name)
        return self._model, self._processor

    def warm_up(self) -> None:
        """モデルを読み込んでおく。初回の検索がモデル読み込み待ちで遅くなるのを避けるために使う。"""
        with self._lock:
            self._load()

    def embed_audio(self, audio_bytes: bytes) -> np.ndarray:
        import torch

        windows = split_into_windows(decode_audio(audio_bytes, sr=_CLAP_SR), _CLAP_SR)
        with self._lock, torch.inference_mode():
            model, processor = self._load()
            inputs = processor(audio=windows, sampling_rate=_CLAP_SR, return_tensors="pt")
            embeddings = model.get_audio_features(**inputs).pooler_output.numpy()
        return _normalize(embeddings.mean(axis=0))

    def embed_text(self, text: str) -> np.ndarray:
        import torch

        with self._lock, torch.inference_mode():
            model, processor = self._load()
            inputs = processor(text=[text], return_tensors="pt", padding=True)
            embedding = model.get_text_features(**inputs).pooler_output.numpy()[0]
        return _normalize(embedding)
