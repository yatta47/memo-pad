# confluence-read

Confluence Cloud のタスク管理ページを **読む**／進捗を **コメントで書く** ための self-contained スキル。
会社PCの Cursor / Claude Code から使う想定。

## セットアップ

```bash
# devcontainer 内で
pip install atlassian-python-api

# 認証（.envrc / 1Password 等で管理。コードには絶対に書かない）
export CONFLUENCE_BASE_URL="https://your-org.atlassian.net"   # 末尾 /wiki なし
export CONFLUENCE_EMAIL="you@example.com"
export CONFLUENCE_API_TOKEN="xxxxxxxx"   # https://id.atlassian.com/manage-profile/security/api-tokens
```

## 会社PCで最初に 1 件だけ挙動確認する（重要）

設計時にこのスキルは**実 API で未検証**（個人環境に会社の認証情報が無いため）。
会社PCで本運用する前に、必ず 1 件だけ叩いて挙動を確認すること（SKILL.md 設計原則 §4）。

```bash
# 1) スペース一覧が引けるか（認証の疎通確認）
python scripts/confluence.py spaces

# 2) タスク管理ページの本文が取れるか（page_id は URL の pageId= から取得）
python scripts/confluence.py page <PAGE_ID>

# 3) コメントが dry-run で正しい対象を指すか（まだ投稿されない）
python scripts/confluence.py comment <PAGE_ID> --text "疎通テスト"

# 4) 問題なければ --save で実投稿 → Web UI でコメントが付いたか目視確認
python scripts/confluence.py comment <PAGE_ID> --text "疎通テスト" --save
```

確認ポイント:
- 検索 `cql()` のレスポンス構造（`results[].content.title/id`）が想定どおりか。
  違えば `cmd_search` の取り出しを調整。
- `add_comment()` の戻り値に `id` が入るか（完了検証に使用）。
- **dry-run で表示される URL が実在ページを指すか**（環境により `_links.webui` が
  `/wiki/...` か `/spaces/...` かで前置が変わる。ズレていたら `_page_label()` の URL 組み立てを調整）。
- **`pages` の全件取得**: ライブラリの `get_all_pages_from_space` はページ数が `--limit`
  ちょうどの倍数だと末尾を取りこぼす既知挙動がある。全件要るときは `--limit` を実数より大きく取る。

## 機能

| コマンド | 動作 | 副作用 |
|----------|------|--------|
| `search` | CQL/キーワード検索 | なし（読み取り） |
| `page` | ページ本文を Markdown 取得（`--raw` で storage 原文） | なし |
| `spaces` | スペース一覧 | なし |
| `pages` | スペース内ページ一覧 | なし |
| `comment` | 進捗を footer コメント追記 | **あり**（`--save` 時のみ。dry-run 既定） |

## 安全装置

- `comment` は **デフォルト dry-run**。`--save` を付けて初めて実投稿。
- dry-run / 投稿いずれも、先に対象ページのタイトル・URL を表示し page_id 取り違えを防止。
- 書くのは **footer コメント追記のみ**。本文（タスク表）は変更しない。
- 取消: 投稿コメントの削除は Confluence Web UI から（本ツールは削除しない）。

## 限界

- storage→Markdown 変換は MVP。マクロ・添付・ネスト表は簡易/欠落あり。原文は `page --raw`。
- Data Center 版は非対応（公式は別系統）。
- 社内情報を外部 AI に渡すため、会社の AI 利用ポリシーの範囲で使う。

## 今後の拡張（未実装）

- 本文の「## 進捗」セクションへの追記 / タスク表の特定行更新（破壊的なので別途設計）。
  → SKILL.md 設計原則 §2「副作用の性質が違うものは別スキルに分ける」に従い、別スキル化を検討。
