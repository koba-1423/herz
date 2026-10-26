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
  指標から直接算出（energy は音圧とスペクトル重心＝音の明るさの組み合わせ）。danceability / valence / instrumentalness / liveness は信号処理
  単体では根拠のある値を出せないため意図的に未実装（フェーズ2で学習済みモデル/
  音声埋め込みによる算出を想定。EssentiaはmacOS ARM64 + Python 3.12向けの配布物が
  無く採用を見送った）
- `POST /analyze` — 音声ファイルをアップロードして上記の分析を試せる動作確認用API
  （Spotify等の外部音源連携が無くても手元の音声で試せる）

## 検索の流れ

1. `POST /ingest` — iTunes Search API でキーワード検索し、30秒プレビュー（AAC/m4a）を
   ダウンロード・解析して `tracks` テーブルに保存する（分析済みの曲はスキップ）。
   Spotifyは新規アプリだと `preview_url` が null で返るため、音源取得には iTunes を使う。
   AAC のデコードには ffmpeg 同梱の PyAV を使うため、ffmpeg の別途インストールは不要。
2. `POST /search` — 取り込み済みの楽曲を、ジャンル・キー・長短調・BPM・energy などの
   範囲条件で検索する。範囲条件を指定した特徴量が未算出の曲は結果から除外される。
   `text` に雰囲気を表す英語の文を渡すと、条件で絞り込んだ曲を文との近さ順に並べる（後述）。

```bash
curl -X POST localhost:8000/ingest -H 'content-type: application/json' \
  -d '{"term": "city pop", "limit": 20}'
curl -X POST localhost:8000/search -H 'content-type: application/json' \
  -d '{"tempo_bpm_min": 100, "tempo_bpm_max": 130, "mode": 1, "energy_max": 0.6}'
curl -X POST localhost:8000/search -H 'content-type: application/json' \
  -d '{"text": "relaxing soft piano for a rainy night", "energy_max": 0.5}'
```

## 自然文による雰囲気検索 (CLAP)

音声とテキストを同じベクトル空間に埋め込む [CLAP](https://github.com/LAION-AI/CLAP)
（transformers実装の `laion/larger_clap_general`）で、取り込み時にプレビュー音源の埋め込みを
算出してDBに保存し、検索時は文の埋め込みとのコサイン類似度で並べる。

- torch / transformers が重いため optional extra (`clap`) にしている。未インストール、または
  `CLAP_MODEL` を空にした場合は埋め込みを算出せず、`text` 付きの検索は 503 を返す
- 初回利用時にモデル（約800MB）を Hugging Face からダウンロードする
- テキストエンコーダは英語のみ対応
- CLAPは10秒単位の入力のため、30秒のプレビューを10秒ごとに埋め込んで平均している
  （プロセッサ任せだとランダムに切り出され、結果が毎回変わるため）
- `laion/larger_clap_music` は音楽特化だが、テキスト埋め込みが入力によらずほぼ同一になり
  検索に使えなかったため不採用
- CLAP導入前に取り込んだ曲やモデル変更後の曲は `POST /ingest/embeddings` で埋め込みを後から算出できる
- 類似度計算はアプリ側での総当たり。数万曲を超えるようなら pgvector への移行を検討する

## セットアップ

```bash
uv sync --extra clap  # 自然文検索が不要なら --extra clap は省略可
cp .env.example .env  # DB接続先・Spotify等の認証情報を設定
uv run alembic upgrade head
```

PostgreSQL を用意せずに試す場合は SQLite でも動く:

```bash
export DATABASE_URL=sqlite+aiosqlite:///./herz.db
uv run alembic upgrade head
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
  services/      外部API連携（iTunes, Spotify）・音響特徴量分析・取り込み・検索
  schemas/       Pydanticモデル
  models/        DB用モデル（SQLAlchemy）
migrations/      Alembicマイグレーション
```
