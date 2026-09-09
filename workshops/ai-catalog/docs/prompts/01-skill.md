# STEP 1 指示文（当日貼る版）


---

`.claude/skills/case-card/SKILL.md` を作ってください。URLを1本受け取り、記事を読んで「AI活用事例カード」のJSONを1件書くスキルです。

## 出力
- `catalog/<id>.json` に1ファイル。既にあれば上書きしない。
- スキーマは `docs/case-schema.md` に従う。キー名・型・順序を変えない。

## 各項目の書き方
- `department`: 困っていた人の業務機能を短い名詞1つで（10字以内）。会社名ではない。
- `who_and_problem`: 主語（部署・役割）を必ず入れる。困りごとを1〜3文。
- `problem_types`: `docs/case-schema.md` の「困りごとの型（固定の8種）」から1〜2個。先頭が主。一覧以外の語は使わない。
- `ai_and_system`: AIがしていることと、AIの外側の仕組み（データ連携、承認、通知、UI）を分けて書く。
- `platforms`: 記事に出てくるサービス・製品・モデルの名前を、`docs/case-schema.md` の正規化辞書の表記で列挙。記事に無いものは入れない。
- `requirements`: データ・基盤・運用体制の3点。記事に無い点は「記載なし」と書く。
- `confirmed_effects`: 記事に数値や実測の記述があるものだけ。無ければ空文字。
- `hypothesized_effects`: 記事が「期待」「見込む」「目指す」「検討中」と書いているもの。confirmed と混ぜない。
- `source_url`: 受け取ったURLそのまま。`confirmed_at`: 今日の日付。

## 切り分けの例
- 「作業時間を約70〜80%削減」「導入3か月後の実測」 → confirmed_effects
- 「作業負荷の大幅な軽減が期待」「今後、他部署への展開を検討」 → hypothesized_effects

## やらないこと
- 記事に無いことを補わない。推測で埋めるくらいなら「記載なし」か空文字。
- 出典URL以外のページを読まない。
- 複数URLを一度に処理しない（1回の呼び出しで1件）。

作ったら、`https://aws.amazon.com/jp/blogs/news/179920-2/` で1件生成して、結果のJSONを表示してください。
