# CLAUDE.md — このリポジトリで作業するエージェントへ

## まず読む
- `README.md` … 目的・現在の状態・アーキテクチャ・意思決定の記録（§9）・作業の作法（§10）。**作業前に必ず読む。**
- `change-intelligence-poc-basic-detailed-design-docker.docx` … 設計書（正本）。README と食い違う点は README §9 に理由がある。
- `docs/architecture-overview.html` … 説明資料（4 システム構成図 + PoC 構成図）。fixture を変えたら図も更新する。
- `docs/cost-model.xlsx` … 費用モデル（数式入り Excel）。数字を変えるときは前提シートの黄色セルを編集し、検討書の要約も合わせる。
- `docs/cloud-selection-cost-and-ai-plan.md` … 本番化検討書（クラウド比較・費用・AI 活用）。予算の前提はここ。
- `docs/cloud-deployment-notes.md` … クラウド運用（AWS / Google Cloud）を検討するときの材料。

## 一言で
企業システムの データ / API / サービス / 担当チーム の関係を Neo4j の Knowledge Graph に集め、
変更影響分析・未特定の利用元の特定・正規ルート外参照の検出・鮮度ズレの検知・新規データ設計レビューを行う PoC。
Docker Compose（frontend: Next.js 15 / backend: FastAPI / neo4j 5 Community / seed）。閲覧者は経営層。

## 守ること（設計書 §17 と利用者の判断）
- Docker Compose で完結。Neo4j に触るのは backend のみ。seed は冪等。Graph の全件表示を既定にしない。
- 認証・Kafka・Kubernetes・VectorDB・OpenSearch は追加しない。LLM キー無しで全機能が動くこと。
- 不明な依存は削除せず Unknown として残す。
- **画面の文言は日本語・ビジネス用語、データの名前（Customer App, customer_address, Get Customer …）は英語のまま。**
- 新しい画面ラベルは `frontend/src/lib/api.ts` の辞書に追加する。アイコンは Lucide（`frontend/src/lib/icons.ts`）。
- 挙動・用語・判断を変えたら README の該当節と §9（意思決定の記録）を更新する。

## よく使うコマンド
```bash
docker compose up -d --build --wait              # 全体起動
docker compose run --rm seed                     # fixture 投入（冪等）
docker compose run --rm -e SEED_RESET=1 seed     # 全削除→再投入（デモ状態リセット）
docker compose up -d --build --wait backend      # backend 変更の反映
docker compose up -d --build --wait frontend     # frontend 変更の反映
docker compose run --rm --no-deps backend pytest -q   # テスト（25 件）
```
- 画面 http://localhost:3000 / API http://localhost:8000/docs（この開発機では `.env` で backend を 8001 に変えている場合がある。`docker compose ps` で確認）。
- 画面確認は curl の 200 だけでなく、可能ならヘッドレス Chromium で全ページを描画してコンソールエラーが無いことを見る。

## コードの地図
- 分析ロジック（impact / governance / drift / design_review）は `backend/app/graph/snapshot.py` のインメモリ snapshot 上で動き、Neo4j 無しで単体テストできる。
- Cypher を直接書いているのは `graph/client.py`、`services/objects.py`、`services/unknowns.py`、`seed.py` の 4 ファイルだけ。
- ルール（辿り方・重大度・閾値）は `ontology/rules.yaml`。fixture は `fixtures/*.yaml`（Relation の `id` が冪等キー）。
- フロントは `frontend/src/app/*`（ダッシュボード `/`、全体マップ `/map`、他）。グラフ描画は `components/GraphView.tsx`（階層表示が既定、`LANES` でレーン順）。
