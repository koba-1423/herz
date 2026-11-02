# 別のMacで Herz を動かす

Herz は1台のMacの中で、PostgreSQL・APIサーバー・クローラがすべて動いている。
別のMacに移すときの手順。

## 古いMacで用意するもの

GitHub には入れないもの（容量が大きい、または秘密の値を含む）を1つのフォルダにまとめ、
AirDrop・iCloud Drive・外付けディスクなどで新しいMacに渡す。

```bash
# クローラを止めてから（止めないと書き出し中も曲が増え続ける）
mkdir -p ~/Desktop/herz-migration
/Applications/Postgres.app/Contents/Versions/17/bin/pg_dump -U herz -d herz -Fc \
  -f ~/Desktop/herz-migration/herz.dump
cp .env ~/Desktop/herz-migration/env
# Claude Code の記憶（公開前の確認事項など）
cp -R ~/.claude/projects/-Users-<ユーザー名>-Develop-herz/memory ~/Desktop/herz-migration/claude-memory
```

## 新しいMacでの手順

### 1. PostgreSQL

1. [Postgres.app](https://postgresapp.com/) の PostgreSQL 17 版を入れて起動し、「Initialize」を押す
2. Settings で「Automatically start server」と、ログイン時にアプリを起動する設定をオンにする
3. 利用者とDBを作り、渡されたデータを戻す

```bash
PG=/Applications/Postgres.app/Contents/Versions/17/bin
$PG/psql -d postgres -c "CREATE ROLE herz LOGIN PASSWORD 'herz'"
$PG/psql -d postgres -c "CREATE DATABASE herz OWNER herz"
$PG/psql -d herz -c "CREATE EXTENSION vector"
$PG/pg_restore -U herz -d herz --no-owner --no-comments ~/Desktop/herz-migration/herz.dump   # 4分ほど
```

テスト用のDB（`TEST_POSTGRES_URL` で使う `herz_test`）も同じように作れる。

### 2. コードとPython

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/koba-1423/herz.git ~/Develop/herz
cd ~/Develop/herz
git switch feature/vibe-search
cp ~/Desktop/herz-migration/env .env
uv sync --extra clap
uv run alembic upgrade head   # 戻したDBが最新なら何も変わらない
uv run pytest
```

CLAP と NLLB のモデル（合わせて数GB）は、初回起動時に自動でダウンロードされる。

### 3. 起動

```bash
# APIサーバーと今のフロント（http://127.0.0.1:8000/）
uv run uvicorn herz.main:app --host 127.0.0.1 --port 8000

# クローラ（止まっても30秒後に再開する。熱が気になるときは --threads を減らす）
OMP_NUM_THREADS=3 caffeinate -i bash -c 'while true; do uv run python -m herz.crawl --threads 3; \
  echo "crawler exited ($?), restarting in 30s"; sleep 30; done' >> crawl.log 2>&1
```

クローラは処理済みの記録（`crawl_marks`）もDBに入っているので、古いMacで止めたところから続く。

### 4. フロントのプロトタイプ（任意）

Node.js 20 以上を入れてから:

```bash
cd prototypes
npm ci
npm run dev   # http://localhost:5173/
```

### 5. Claude Code の記憶（任意）

`claude-memory` フォルダを `~/.claude/projects/<作業フォルダのパスの / を - にしたもの>/memory`
に置くと、公開前の確認事項などを引き継げる。
