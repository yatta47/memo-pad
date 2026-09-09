---
name: case-card
description: URLを1本受け取り、記事を読んで「AI活用事例カード」のJSONを catalog/<id>.json に1件書く。「このURLを事例カードにして」「カードを作って」で使う。
---

# case-card

URL 1本 → `catalog/<id>.json` 1ファイル。スキーマは `docs/case-schema.md` が正。

## 手順

1. URL を WebFetch で読む。出典URL以外のページは読まない。
2. `id` を決める。出典URLの末尾スラッグを基に、英小文字・数字・ハイフンのみ。ドメインの短縮を先頭に付ける（例: `aws-jp-179920-2`）。
3. `catalog/<id>.json` が既にあれば何もせず「既存」と報告して終わる。上書きしない。
4. 下の「各項目の書き方」に従って9項目を埋め、キーの順序を変えずに JSON を書く。
5. `uv run python scripts/validate_catalog.py` を実行し、NG があれば直す。
6. 書いた JSON を表示する。

## 各項目の書き方

| キー | 書き方 |
|---|---|
| `id` | ファイル名と一致 |
| `title` | 40字以内 |
| `who_and_problem` | 主語（部署・役割）を必ず入れる。困りごとを1〜3文 |
| `ai_and_system` | AIがしていることと、AIの外側の仕組み（データ連携、承認、通知、UI）を分けて書く |
| `requirements` | データ・基盤・運用体制の3点。記事に無い点は「記載なし」と書く |
| `confirmed_effects` | 記事に数値や実測の記述があるものだけ。無ければ空文字 `""` |
| `hypothesized_effects` | 記事が「期待」「見込む」「目指す」「検討中」と書いているもの。confirmed と混ぜない |
| `source_url` | 受け取ったURLそのまま |
| `confirmed_at` | 今日の日付 `YYYY-MM-DD` |

## 切り分けの例

- 「作業時間を約70〜80%削減」「導入3か月後の実測」 → `confirmed_effects`
- 「作業負荷の大幅な軽減が期待」「今後、他部署への展開を検討」 → `hypothesized_effects`
- 「精度と一貫性が向上」のように数値も実測も無い記述 → `confirmed_effects` には入れない

## やらないこと

- 記事に無いことを補わない。推測で埋めるくらいなら「記載なし」か空文字。
- 複数URLを一度に処理しない（1回の呼び出しで1件）。
- `catalog/` 以外のファイルを変更しない。
