# dir-dump

指定ディレクトリ配下の全テキストファイルを1つの Markdown ストリームに連結する。LLM への貼り付け・コンテキスト渡しを想定したツール。

## 使い方

```bash
# カレントディレクトリ全体
./dir-dump.sh > dump.md

# 特定ディレクトリ
./dir-dump.sh workspace/issue-639/ > dump.md

# 1ファイルの上限を変える（default: 1MB）
./dir-dump.sh --max-bytes 524288 path/to/dir > dump.md

# 隠しファイルも含める
./dir-dump.sh --include-hidden path/to/dir > dump.md
```

## Issue workspace での想定用途

```bash
# 例: Issue #639 の作業内容を丸ごとLLMに渡したいとき
cd workspace/issue-639/
~/repos/github/life-project/tools/dir-dump/dir-dump.sh > /tmp/issue-639-dump.md

# あるいはどこからでも
~/repos/github/life-project/tools/dir-dump/dir-dump.sh \
  ~/repos/github/life-project/workspace/issue-639/ > /tmp/issue-639-dump.md
```

## 出力フォーマット

```markdown
# Dump: /abs/path/to/root

_Generated: 2026-05-15T..._

## Tree

​```
README.md
docs/
  architecture.md
  api-trigger-flow.md
artifacts/
  ...
​```

## file: README.md

​```markdown
<内容>
​```

## file: docs/architecture.md

​```markdown
<内容>
​```
```

- 冒頭に **ディレクトリツリー** を表示（LLMが構造を把握しやすい）
- ファイルは `LC_ALL=C sort` 順
- 言語ヒント (` ```python ` 等) は拡張子から推定
- バイナリは検出して中身省略
- サイズ上限超過は中身省略

## 除外パターン（default）

| カテゴリ | 内容 |
|---------|------|
| ディレクトリ | `.git/`, `.terraform/`, `node_modules/`, `__pycache__/`, `.venv/`, `venv/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.idea/`, `.vscode/`, `dist/`, `build/`, `.next/`, `.cache/` |
| 拡張子 | 画像 (`.png`, `.jpg` 等), 音声 (`.mp3` 等), 動画 (`.mp4` 等), アーカイブ (`.zip` 等), ドキュメント (`.pdf`, `.docx` 等), バイナリ (`.so`, `.dll`, `.exe` 等), フォント, DB |
| ファイル名 | `.DS_Store`, `Thumbs.db`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`, `uv.lock`, `composer.lock`, `Gemfile.lock` |
| 隠しファイル | デフォルトで除外（`--include-hidden` で含める） |

## 他ツールとの違い

| ツール | スコープ | 用途 |
|--------|---------|------|
| [tf-dump](../tf-dump/) | Terraformモジュール + ローカル参照モジュール | Terraform専用、`*.tf` のみ |
| dir-dump | 任意ディレクトリ | 汎用、全テキスト |

Terraformコード固有のレビューには `tf-dump`、Issue workspace やプロジェクト全体を渡したいときは `dir-dump` を使う。

## オプション

| オプション | デフォルト | 説明 |
|----------|---------|------|
| `--max-bytes N` | 1048576 (1MB) | 1ファイルあたりの上限。超過分は中身省略 |
| `--include-hidden` | OFF | 隠しファイル/ディレクトリも含める |
| `-h`, `--help` | - | ヘルプ表示 |

## 落とし穴

- **シンボリックリンクは追わない**: `find -type f` で実体のみ
- **NULバイトでバイナリ判定**: テキストでもNULを含むファイル（一部のSQLite dumpなど）はバイナリ扱いされる
- **大量ファイル時の出力サイズに注意**: LLMのcontext window を超えると貼り付け失敗。事前に `wc -l dump.md` でサイズ確認
- **言語ヒント未対応の拡張子**: fence は ` ``` ` で空のlang指定になる（描画上は問題なし）

## 拡張案（将来）

- 除外パターンを `.dumpignore` で設定可能に
- 含めるファイルを `--include-only "*.tf"` などで指定
- 出力をXML形式に切り替え（Claude推奨の構造化フォーマット）
