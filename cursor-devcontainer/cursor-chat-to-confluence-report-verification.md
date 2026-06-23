# 確認手順書: Cursor IDE Chat → 日報 → Confluence（会社PC内で完結）

**作成日**: 2026-06-24
**実施予定**: 翌営業日、会社PCにて
**ゴール**: 「Cursor の IDE Chat 履歴 → 日報生成 → Confluence へ投稿」を **会社PC の外にデータを出さずに** 実現できるか確認する。

---

## 0. 前提（確認済み）

- Cursor: 会社が正式提供。**Cloud 版**。**DevContainer 接続**で利用。
- Confluence: **Cloud 版**。API トークン発行可。タスク管理は「1ページに表で集約・進捗はコメント追記」。
- IDE Chat の履歴は **ホスト（会社PC本体）の SQLite `state.vscdb`** に保存される（コンテナ内ではない）。
- ホスト（会社PC）は**ガチガチ管理で情報持ち出し不可**。
  → **持ち帰るのは技術スキーマ・OK/NG・動いたコマンドのみ**。会話本文・社内URL・スペースキー・トークンは持ち出さない。

### 確認の全体像（分岐）

```
Step1 IDE Chat の DB は読めるか？
  ├─ YES → Step2 コンテナ or ホストでスクリプトを動かせるか？
  │         ├─ YES → ★本命: IDE Chat→日報→Confluence を会社PC内で完結
  │         └─ NO  → ホスト側で直接動かす経路を探す（管理者相談 / ターミナル可否）
  └─ NO  → ▼フォールバック: CLI 運用（コンテナ内 ~/.cursor/chats/）へ方針転換
```

---

## Step 0: OS の確認

`state.vscdb` のパスが OS で変わるため最初に確認する。

| OS | globalStorage の state.vscdb |
|----|------------------------------|
| Windows | `%APPDATA%\Cursor\User\globalStorage\state.vscdb` |
| macOS | `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` |
| Linux | `~/.config/Cursor/User/globalStorage/state.vscdb` |

---

## Step 1: IDE Chat の DB 所在と当日会話の有無

> ⚠ **読む前に Cursor を一旦終了** するか、**DB をコピーしてから読む**（起動中はロックされ得る）。
> 以下は Python 標準ライブラリ（sqlite3）のみ。pip 不要。読み取り専用(`mode=ro`)で開く。

### 1-1. DB をコピー（安全のため）

```bash
# macOS/Linux 例
cp "<上表の state.vscdb パス>" /tmp/cursor_state_copy.vscdb
```

```powershell
# Windows PowerShell
Copy-Item "$env:APPDATA\Cursor\User\globalStorage\state.vscdb" "$env:TEMP\cursor_state_copy.vscdb"
```

### 1-2. テーブルとキー形式を確認（Python ワンライナー）

```bash
python3 - <<'PY'
import sqlite3
db = "/tmp/cursor_state_copy.vscdb"        # ← コピー先に置換（Windows は %TEMP% のパス）
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()
print("=== tables ===")
print([r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")])
print("=== cursorDiskKV key sample (先頭20件) ===")
try:
    for (k,) in cur.execute("SELECT key FROM cursorDiskKV LIMIT 20"):
        print(k)
    print("bubble件数:", cur.execute("SELECT count(*) FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'").fetchone()[0])
    print("composer件数:", cur.execute("SELECT count(*) FROM cursorDiskKV WHERE key LIKE 'composerData:%'").fetchone()[0])
except Exception as e:
    print("cursorDiskKV を読めない:", e)
PY
```

**確認ポイント（メモする）**:
- [ ] `cursorDiskKV` テーブルが存在するか
- [ ] キー形式は `bubbleId:<composerId>:<messageId>` / `composerData:<composerId>` か（バージョンで変わる）
- [ ] bubble/composer の件数が 0 でないか（＝当日までの会話が入っているか）

### 1-3. 1件だけ中身の構造を見る（timestamp / 本文フィールド名の特定）

```bash
python3 - <<'PY'
import sqlite3, json
db = "/tmp/cursor_state_copy.vscdb"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()
row = cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%' LIMIT 1").fetchone()
if row:
    print("keys in bubble JSON:", list(json.loads(row[1]).keys()))
else:
    print("bubble なし")
PY
```

**確認ポイント**:
- [ ] 日付で絞り込めるフィールド（`createdAt` / `timestamp` 等）の名前
- [ ] 本文フィールド（`text` / `richText` 等）の名前

---

## Step 2: コンテナ or ホストでスクリプトを動かせるか

DB はホスト保存。スクリプトをどこで実行できるかを確認する。

### 2-A. コンテナからホストの Cursor ディレクトリを mount できるか

`devcontainer.json` に追記してリビルド → コンテナ内から見えるか:

```jsonc
// 例: Linux ホスト。Win/Mac はホスト側パスを置換
"mounts": [
  "source=${localEnv:HOME}/.config/Cursor,target=/host-cursor,type=bind,readonly"
]
```

```bash
# コンテナ内で
ls -l /host-cursor/User/globalStorage/state.vscdb
```

- [ ] コンテナから読めた / 読めない（管理ポリシーで mount 不可の可能性）

### 2-B. ホストで直接 Python を動かせるか

- [ ] 会社PCホストで `python3 --version` が通るか
- [ ] 任意スクリプト実行が許可されているか

---

## Step 3: エクスポート手段（拡張優先 → OSS → 自前の順で確認）

> ⚠ **公式の「Shared transcripts」はクラウド共有（チーム/公開リンク）で会社情報が外部に出るため使わない。**
> ローカルで `state.vscdb` を読んで Markdown 化する手段だけを採用する（会社PC内完結）。
> **前提メモ**: 会社PCで Cursor 公式 DevContainer 拡張が入れられている＝拡張インストールは通る環境。
> よって Open VSX 拡張も入る見込みが高い（ただし「公式 allowlist 限定」運用の可能性は残るので確認する）。

### 3-A【最優先】Open VSX 拡張で出せるか

CursorはOpen VSXを使う（VS Code Marketplaceは標準で不可）。**Open VSX掲載＝Cursorにそのまま入る**。

- 第一候補: **Cursor Chat Bulk Export**（Open VSX, `AnasAbbasCode.cursor-chat-bulk-export`）
  workspaceのチャットをメタ付きMarkdownで**ローカル**出力。
- 予備: **Cursor Chat Transfer**（Open VSX, `ibrahim317.cursor-chat-transfer`）

確認:
- [ ] 拡張パネル（Open VSX）から `Cursor Chat Bulk Export` を検索・インストールできるか
- [ ] 当日チャットを **ローカルのMarkdownファイル**に出力できたか（外部に出ていないか）
- [ ] 出力に日付・workspace・本文が含まれるか（日報の材料になるか）

### 3-B 入らない場合: VS Code Marketplace 拡張を VSIX 手動

`CursorChat Downloader` / `Cursor Chat Exporter` / `Cursor Chat Viewer` は VS Code MP 配布。
VSIX を落として手動インストールできるか（ポリシー次第）。**クラウド同期型(SpecStory/WayLog)は外部送信なので避ける**。

- [ ] VSIX 手動インストールが許可されているか

### 3-C それも不可: OSS CLI / 自前抽出

- `iksnae/cursor-session`（IDE+CLI両対応エクスポータ）/ `S2thend/cursor-history`
- または Step1 の Python ワンライナーを土台に自前抽出（sqlite3 標準のみ・pip不要）

- [ ] OSS が入る/動く、または自前抽出でMarkdown化できる

---

## Step 4: Confluence API 疎通

`confluence-read` スキル（`cursor-devcontainer/skills/confluence-read/`）の README「会社PCで最初に1件だけ挙動確認する」を実施:

- [ ] API トークン発行
- [ ] `python scripts/confluence.py spaces` が通る（認証疎通）
- [ ] `python scripts/confluence.py page <PAGE_ID>` でタスク表が Markdown で取れる
- [ ] `python scripts/confluence.py comment <PAGE_ID> --text "疎通テスト"`（dry-run で対象確認）
- [ ] `--save` で実投稿 → Web UI でコメント確認

---

## 判定マトリクス（持ち帰って方式を決める）

| Step3-A 拡張で出せる | Step1 DB読める | Step2 実行可 | → 方式 |
|---|---|---|---|
| **Yes（Open VSX拡張）** | - | - | ★★最楽: 拡張でMarkdown出力 → 日報整形 → Confluence。SQLite を自前で読む必要なし |
| No | Yes | Yes | 本命: 自前抽出（Python sqlite3）→ 日報 → Confluence。スキーマは Step1 で控える |
| No | Yes | No | ホスト側実行経路を探す（管理者相談）。不可なら下へ |
| No | No | - | ▼フォールバック: **CLI 運用**へ転換（業務会話を `cursor-agent` CLI で行い、コンテナ内 `~/.cursor/chats/` を日報ソースに。`devcontainer.json` で `~/.cursor` を named volume 永続化） |

---

## 持ち帰りメモ（このテンプレを埋めて持ち帰る／固有情報は書かない）

```text
OS:
【拡張ルート（最優先）】
Open VSX 拡張インストール: 可 / 不可（公式allowlist限定か？）
Cursor Chat Bulk Export: 入った / 入らない
ローカルMarkdown出力: できた / できない（出力形式・場所: ___）
【自前ルート（拡張不可の場合）】
state.vscdb パス: あり / なし
cursorDiskKV テーブル: あり / なし
キー形式: （例 bubbleId:<id>:<id> ）
当日会話 件数: bubble=__ / composer=__
日付フィールド名: / 本文フィールド名:
コンテナから mount: 可 / 不可
ホスト直 python: 可 / 不可
【投稿先】
Confluence 疎通: spaces OK/NG, page OK/NG, comment dry-run OK/NG, --save OK/NG
→ 採用方式（判定マトリクスより）:
```

> ※ 会話本文・社内URL・スペースキー・API トークンは**書かない・持ち出さない**。上記は技術構造のみ。

---

## 補足: 関連資産

- 日報の投稿先スキル: `cursor-devcontainer/skills/confluence-read/`（memo-pad にコピー済み）
- 実体・正典は life-project 側 `shared-skills/confluence-read/`
- IDE Chat 保存場所の根拠: Global DB=`globalStorage/state.vscdb`(`cursorDiskKV`)、メッセージは `bubbleId:` キー
- CLI 版の保存場所（フォールバック時）: `~/.cursor/chats/`（IDE Chat とは別ストレージ）
