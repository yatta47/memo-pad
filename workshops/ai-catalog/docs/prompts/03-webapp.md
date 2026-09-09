# STEP 3 指示文（当日貼る版）


---

`app/main.py` に Streamlit のアプリを1ファイルで作ってください。事例カタログを人が見るための画面です。

## データ
- PostgreSQL。接続文字列は `.env` の `DATABASE_URL`（`python-dotenv` で読む）。
- テーブルは `cases`。列は `docs/case-schema.md` のキーと同じ（`id`, `title`, `department`, `who_and_problem`, `problem_types`, `ai_and_system`, `platforms`, `requirements`, `confirmed_effects`, `hypothesized_effects`, `source_url`, `confirmed_at`）。`problem_types` と `platforms` は `text[]`。
- 依存は導入済み: `streamlit`（1.63。`:color-badge[]` と `st.graphviz_chart`（DOT 文字列を渡せばブラウザ側で描画、graphviz 本体は不要）が使える）, `psycopg`, `python-dotenv`。追加しない。

## 機能
1. 絞り込み（サイドバー）: キーワード1箱（`title`, `who_and_problem`, `ai_and_system` を ILIKE で部分一致）、困りごとの型の選択（件数付き）、部署・役割の選択（件数順）、基盤の複数選択（選んだものをすべて含む事例。候補は件数付き）。
2. 一覧: **見出し行付きの行リスト**。`st.columns` で見出し行（項目名を太字）を1行出し、`st.divider()` の下に1事例1行で並べる。`confirmed_at` 降順。列は: タイトル（太字）／部署・役割（`:blue-badge[]`）／使っている基盤（`:gray-badge[]`、上位3つ＋「他n件」）／誰が、何に困っていたか（困りごとの型を `:orange-badge[]` で先に出し、その下に冒頭55字を `st.caption`）／確認できた効果（冒頭50字、無ければ「（まだ仮説段階）」）／確認日／「詳細」ボタン。列幅の目安は `[2.8, 2.0, 2.3, 2.9, 2.5, 1.3, 1.4]`、`vertical_alignment="center"`。ボタンは `use_container_width` を付けない（狭い列で文字が切れる）。`st.dataframe` もカードもモーダルも使わない。
3. 詳細: **別画面**。「詳細」ボタンで `st.query_params["case"]` に id を入れて `st.rerun()`。`?case=<id>` があれば詳細画面を描画し、「← 一覧へ」ボタンで戻る。10項目を項目名付きで全部表示。確認済み効果は `st.success`、仮説の効果は `st.info` で左右に並べ、出典URLはリンク。
4. 関連事例（詳細画面の下）: **同じ困りごとの型を最優先**に、同じ部署、基盤の共有の順で SQL で最大6件（並び順: 共有する型の数 → 主の型が一致 → 同じ部署 → 共有する基盤の数）。左に `st.graphviz_chart`（DOT 文字列、`rankdir=LR`、左=この事例、中=困りごとの型（橙・太線）と部署（青）と共有基盤（灰）、右=関連事例。基盤の線は「困りごとでも部署でも繋がらない事例」にだけ描く）、右に関連事例のカード（タイトル、「同じ困りごと」「同じ部署」「共有する基盤」の根拠バッジ、困りごと冒頭60字、「この事例を見る」ボタン）。

## やらないこと
- 書き込み機能（登録・編集・削除）は作らない。
- 認証、ページング、グラフ、CSS調整はしない。
- SQLは必ずプレースホルダで書く（文字列連結しない）。
- 複数テーブルを結合する SQL では列に必ず別名（`o.id` など）を付ける。
- 表示の条件分岐は if 文で書く。`st.x() if cond else st.y()` のような式文にしない（Streamlit が式の戻り値を画面に描画してしまう）。

作ったら `uv run streamlit run app/main.py --server.headless true --server.address "${STREAMLIT_ADDRESS:-127.0.0.1}"` で起動して、URLを表示してください。`STREAMLIT_ADDRESS` は `.env` にあります。
