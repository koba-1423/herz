# Herz

アーティスト・レーベル・年代のようなメタデータではなく、**曲そのものの雰囲気**（テンポ感、音の質感、声、リズムなど）を軸に楽曲を探せる音楽検索サービスのバックエンド。

## コンセプト

- 検索条件は音楽的・技術的な語彙で表現する（BPM、ジャンル、エネルギー感、アコースティック度など）
- Spotify / Apple Music など既存の音楽サブスクサービスと連携し、独自の楽曲DBは持たずに検索体験を提供する
- まずはAPI/バックエンドのみを対象とし、フロントエンドは後回しにする

## 技術スタック

- Python 3.12 / [uv](https://docs.astral.sh/uv/)
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async) + PostgreSQL + Alembic
- httpx（外部API連携）

## 音響特徴量の分析方針

Spotify公式のAudio Features / Audio Analysis API は2024年11月以降、新規アプリからは
利用できなくなっている（拡張アクセス済みの既存アプリのみ利用可）。そのため
`TrackFeatures` は自前の信号処理（librosa）で分析する方針にしている。

- `herz.services.audio_features.AudioFeatureExtractor` — 音声バイト列から特徴量を
  抽出する手段を抽象化したインターフェース
- `herz.services.dsp_analysis.DspAudioFeatureExtractor` — librosaによる実装（v1）。
  tempo / key / mode / loudness_db / energy / acousticness / speechiness は信号処理の
  指標から直接算出。danceability / valence / instrumentalness / liveness は信号処理
  単体では根拠のある値を出せないため意図的に未実装（フェーズ2で学習済みモデル/
  音声埋め込みによる算出を想定。EssentiaはmacOS ARM64 + Python 3.12向けの配布物が
  無く採用を見送った）
- `POST /analyze` — 音声ファイルをアップロードして上記の分析を試せる動作確認用API
  （Spotify等の外部音源連携が無くても手元の音声で試せる）

## セットアップ

```bash
uv sync
cp .env.example .env  # Spotify等の認証情報を設定
```

## 開発サーバ起動

```bash
uv run uvicorn herz.main:app --reload
```

http://127.0.0.1:8000/docs でAPIドキュメントを確認できる。

## テスト・Lint

```bash
uv run pytest
uv run ruff check .
uv run mypy .
```

## ディレクトリ構成

```
src/herz/
  api/routes/    エンドポイント定義
  core/          設定・DI
  services/      外部API連携（Spotify, Apple Music, 音響特徴量）
  schemas/       Pydanticモデル
  models/        DB用モデル（今後追加）
```
