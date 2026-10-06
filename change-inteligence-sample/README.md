# Change Intelligence PoC

> **別のエージェント / 新しく参加する人へ**: このファイルを最初に読めば、プロジェクトの目的・現在の状態・これまでの判断・作業の作法が分かるように書いています。
> 設計の正本は `change-intelligence-poc-basic-detailed-design-docker.docx`（設計書）です。設計書と実装が食い違う場合は、§9「意思決定の記録」に理由が書いてあるか確認してください。

---

## 0. 30 秒で分かる概要

- **何を作っているか**: 企業システム内の **データ（テーブル）/ API / サービス・バッチ / 担当チーム** の関係を Knowledge Graph（Neo4j）に集め、
  「この変更は何に影響するか」「誰に相談すべきか」「正規ルートを迂回した利用はないか」「正体不明の利用元は何か」「新しいデータを追加すべきか」を答える PoC。
- **想定ユーザー**: デモの閲覧者は経営層。そのため **画面の文言は日本語・ビジネス用語**、**データの名前（Customer App, customer_address など）は英語のまま**。
- **技術構成**: Docker Compose で `frontend`（Next.js 15）/ `backend`（FastAPI）/ `neo4j`（5 Community）/ `seed`（one-shot）。
  ブラウザ → Next.js → Backend → Neo4j。Neo4j に触るのは Backend だけ。
- **状態**: 設計書のユーザーストーリー US-01〜US-08 はすべて fixture データで再現でき、自動テスト 25 件が通る。本番データの収集（Collector）は未着手で、fixture（YAML）が観測ログの代わり。
- **LLM**: 任意。`ANTHROPIC_API_KEY` があるときだけ新規データ設計レビューに解説文が付く。無くても全機能が動く。

---

## 1. 現在の状態（2026-10-06 時点）

| 領域 | 状態 |
|---|---|
| Docker Compose 基盤（P1） | 完了。`docker compose up -d --build` で 3 サービスが healthy。healthcheck はコンテナ内 `127.0.0.1` を使用 |
| Ontology / fixture / seed（P2） | 完了。seed は冪等（2 回実行しても Node 28 / Relation 38 / Evidence 11 のまま）。`SEED_RESET=1` で全削除→再投入 |
| 周辺 Graph / 詳細（P3, US-03） | 完了。中心から 1〜3 段、表示ノード間の辺はすべて返す（誘導部分グラフ） |
| 変更影響分析（P4, US-01/02/06/08） | 完了。`rules.yaml` の traversal ルールで BFS。直接/間接、経路、責任チーム、注意事項、廃止可否 |
| 未特定の利用元 / ルール逸脱（P5, US-04/05） | 完了。Resolve で関係を付け替え・根拠を継承・履歴保持。正規ルート外参照の検出と「迂回」判定 |
| 鮮度・ズレ検知（設計書外の追加） | 完了。観測途絶 / 申告のみ / 観測のみ（影の依存）/ 根拠なし / 未特定の滞留。通知先チーム付き |
| 新規データ設計レビュー（P6, US-07） | 完了。決定論の REUSE / EXTEND / CREATE 判定。LLM 解説は任意 |
| UI（ダッシュボード型） | 完了。サイドバー + KPI タイル + 各画面。グラフは階層表示が既定、Lucide アイコン |
| テスト / README（P7） | 完了。pytest 25 件（単体 + Neo4j 到達時の統合）。本 README |
| Collector（ログ自動収集） | **未着手**（設計書 §18 の将来拡張） |
| 通知（週次ダイジェスト等） | **未着手**。検知ロジックと通知先はあるので送信部分のみ |
| 認証・マルチテナント・HA | 非ゴール（設計書 §1.2） |

動作確認は、API を curl で全ユーザーストーリー分叩くこと、ヘッドレス Chromium で全画面を描画してコンソールエラーが無いことを確認して行っています。

---

## 2. 起動と日常操作

```bash
cp .env.example .env            # NEO4J_PASSWORD を必ず変更
docker compose up -d --build    # frontend / backend / neo4j が healthy になるまで約 30 秒
docker compose run --rm seed    # Ontology / fixture を投入（冪等）
```

- 画面: http://localhost:3000 　API（Swagger）: http://localhost:8000/docs 　Neo4j Browser: http://localhost:7474
- ホスト側ポートは `.env` の `BIND_HOST`（既定 `0.0.0.0`）と `FRONTEND_PORT` / `BACKEND_PORT` / `NEO4J_*_PORT` で変更可。
  コンテナ間は常に `http://backend:8000` / `bolt://neo4j:7687`（localhost 不使用）。
- 開発マシンによってはホストの 8000 が他プロセスに使われていることがあるため、`.env` で `BACKEND_PORT=8001` にしている環境がある。`.env.example` は設計書どおり 8000。

```bash
docker compose ps                                     # healthy 確認
docker compose logs -f backend                        # ログ
docker compose up -d --build --wait backend           # backend のコードを変えたら
docker compose up -d --build --wait frontend          # frontend のコードを変えたら
docker compose run --rm seed                          # fixture を変えたら（名称変更なども MERGE で反映）
docker compose run --rm -e SEED_RESET=1 seed          # デモ後の状態リセット（Unknown が未特定に戻る）
docker compose run --rm --no-deps backend pytest -q   # テスト
docker compose down -v                                # データごと破棄
```

`seed` サービスは backend と同じイメージ（`change-intelligence-poc-backend:local`）を使う。backend を再ビルドすれば seed にも反映される。

---

## 3. アーキテクチャ

```
Browser ──HTTP──> Next.js (frontend:3000)
                    │  /api/backend/* をサーバサイドで中継（route handler）
                    ▼
                  FastAPI (backend:8000) ──Bolt──> Neo4j (neo4j:7687)
                    │
                    ├─ graph/client.py      Neo4j ドライバ（Neo4j に触る唯一の入口）
                    ├─ graph/snapshot.py    Graph 全体をメモリに読み込む（分析系の入力）
                    ├─ services/objects.py  周辺 Graph（Cypher 直書き）
                    ├─ services/unknowns.py Resolve（Cypher 直書き）
                    ├─ services/impact.py   変更影響分析      ┐
                    ├─ services/governance.py 正規ルート外参照  │ snapshot 上で動く
                    ├─ services/drift.py    鮮度・ズレ検知      │ （DB 製品に依存しない）
                    ├─ services/design_review.py 設計レビュー   ┘
                    └─ seed.py              冪等 seed（fixture を Ontology で検証してから MERGE）
```

- **Graph が Source of Truth**。Ontology（型・関係・ルール）は Git 管理の YAML、インスタンス・関係・根拠は Neo4j。
- **分析ロジックは snapshot 上で動く**ため Neo4j 無しで単体テストできる（`tests/conftest.py` が fixture から snapshot を組み立てる）。
- **DB 製品を差し替える**場合に触るのは `graph/client.py`、`services/objects.py`、`services/unknowns.py`、`seed.py` の 4 ファイル。クラウド DB の選択肢は `docs/cloud-deployment-notes.md`。

---

## 4. リポジトリ構成

```
docker-compose.yml        frontend / backend / neo4j / seed(profile "init", backend イメージを共有)
.env.example              秘密値・ポート・BIND_HOST・LLM キー（任意）
README.md                 本ファイル
docs/architecture-overview.html  説明資料（4 システム構成図 + PoC 構成図、インライン SVG）
docs/cost-model.xlsx             費用モデル（月別 × サービス別、数式入り）
docs/cloud-selection-cost-and-ai-plan.md   本番化検討書（クラウド比較・費用見積・AI 活用）
docs/cloud-deployment-notes.md   AWS / Google Cloud で運用する場合の Graph DB 選択肢と影響範囲
change-intelligence-poc-basic-detailed-design-docker.docx   設計書（正本）
ontology/
  object-types.yaml       Object Type（Team / Service / API / BusinessObject / Database / Table / Batch / Unknown）
  relation-types.yaml     Relation Type と from/to 制約、Evidence の必須属性
  rules.yaml              Impact の traversal・リスク判定、Governance の重大度、Design Review の重み・閾値
fixtures/
  objects.yaml            28 Object（名前は英語のまま。description は日本語可）
  relations.yaml          38 Relation（id が冪等キー。access_mode: owner|direct、observation_type）
  evidence.yaml           11 Evidence（relation_id で Relation に紐付く）
backend/
  app/main.py             FastAPI, /health
  app/api/routes.py       REST エンドポイント
  app/graph/              Neo4j クライアント、snapshot
  app/services/           objects / impact / unknowns / governance / drift / design_review / llm / ontology
  app/seed.py             冪等 seed（SEED_RESET 対応）
  tests/                  pytest 25 件
frontend/
  src/app/page.tsx        ダッシュボード（KPI、要確認事項、未特定一覧、ミニマップ）
  src/app/map/            全体マップ
  src/app/objects/[id]/   対象の詳細
  src/app/impact/         変更影響分析
  src/app/unknowns/       未特定の利用元（一覧・詳細/特定）
  src/app/governance/     ルール逸脱の確認（鮮度・ズレ、正規ルート外参照、責任チーム未設定）
  src/app/design-review/  新規データ設計レビュー
  src/app/api/backend/[...path]/route.ts   Backend への中継（ブラウザは Next.js とだけ通信）
  src/components/         Sidebar / Page(PageHeader, StatCard) / GraphView(Cytoscape) / Badges / Evidence / Icon
  src/lib/api.ts          API クライアント + 用語辞書（TYPE_LABELS / REL_LABELS / DRIFT_LABELS など）
  src/lib/icons.ts        種別ごとの Lucide アイコン割り当て
scripts/seed.py           seed エントリポイント（backend イメージ内で実行）
```

---

## 5. 画面と用語の方針

| 画面（日本語） | 設計書の名称 | パス |
|---|---|---|
| ダッシュボード | （追加） | `/` |
| 全体マップ | System Map | `/map` |
| 対象の詳細 | Object Detail | `/objects/{id}` |
| 変更影響分析 | Impact Analysis | `/impact` |
| 未特定の利用元 | Unknown Inbox | `/unknowns`, `/unknowns/{id}` |
| ルール逸脱の確認 | Governance | `/governance` |
| 新規データ設計レビュー | Design Review | `/design-review` |

- **文言は日本語**: 業務データ=BusinessObject、アプリケーション=Service、担当チーム=Team、責任チーム=Owner、未特定=Unknown、根拠=Evidence、
  関係名は 参照する=READS / 更新する=WRITES / 呼び出す=CALLS / 提供する=PROVIDES / 責任を持つ=OWNS / 操作対象=OPERATES_ON / 実体=REPRESENTS / 依存する=DEPENDS_ON。
  バックエンドが返す注意事項・要約・レビュー理由も日本語。辞書は `frontend/src/lib/api.ts`。
- **データの名前は英語**: サービス・API・テーブル・DB・チーム・ID は fixture の `name` のまま。識別のための固有名詞なので翻訳しない。
- **グラフ表示**: 既定は階層表示（左: 元データ → テーブル → 業務データ → API → サービス/バッチ/未特定、担当チームは下段）。放射表示（選択対象を中心に同心円）に切替可。
  業務データ（概念）は既定で非表示。関係名のラベルはノードをホバー/選択したときだけ表示。正規ルート外参照は赤い破線、未特定はオレンジのひし形。

---

## 6. Graph モデルとルール

- Node: `:Object:{Type}`。`id` にユニーク制約。Unknown は `status`（open / resolved）、`resolved_to` を持つ。
- Relation: property `id`（冪等キー）、`access_mode`（owner / direct）、`observation_type`（declared / observed / manual）、`note`、Resolve 後は `resolved_from`。
- Evidence: `:Evidence` ノード。`relation_id` で Relation に紐付く（Neo4j は Relation に Node を直接つなげないため）。`source_type` / `source_ref` / `first_seen` / `last_seen` / `confidence` / `observation_type`。
- Unknown Resolve: Unknown に接続していた Relation を **同じ id のまま** Known Object へ付け替える → Evidence は自動的に継承。Relation と Evidence に `resolved_from` を記録し、Unknown は `status=resolved` で履歴として残す。再 seed しても resolved は維持される。

`ontology/rules.yaml`:
- **Impact**: Type ごとに辿る Relation と向き。最初の hop が READS/WRITES/CALLS/PROVIDES なら「直接」。Unknown 到達・正規ルート外参照・影響サービス 3 件以上で リスク高。
  同じ関係を直後に逆向きに辿らない（API ← PROVIDES ← Service → PROVIDES → 兄弟 API を影響に含めない）。廃止判定では OWNS と PROVIDES は非ブロッキング。
- **Governance**: `access_mode=direct` の READS/WRITES を検出（Service: 高、Batch: 中、Unknown: 高）。アクセス元がそのテーブルの業務データを操作する API を既に CALLS していれば「迂回」。
- **Drift**: 根拠の `observation_type` と `first_seen`/`last_seen` から 観測途絶（N 日）/ 申告のみ / 観測のみ / 根拠なし / 未特定の滞留 を検知。通知先は両端の責任チーム（テーブルは更新サービス・業務データ経由、API は提供サービス経由で解決）。
- **Design Review**: 項目重複 0.5 / 名称重複 0.3 / 説明類似 0.2。≥0.75 かつ不足なしで REUSE、≥0.35 で EXTEND、それ以外 CREATE。「時点 / 履歴 / snapshot」等があれば CREATE を別案提示。

---

## 7. Backend API

| Method | Path | 用途 |
|---|---|---|
| GET | `/health` | `{"status":"ok","neo4j":"ok","llm":false}` |
| GET | `/api/objects?type=Table&q=cust` | 対象一覧（検索用） |
| GET | `/api/objects/{id}` | 対象の詳細（属性 / 責任チーム / 関係 / 根拠） |
| GET | `/api/objects/{id}/graph?depth=2` | 周辺 Graph（1〜3 段、表示ノード間の辺をすべて含む） |
| GET | `/api/impact?object_id=&change_type=schema_change\|api_change\|delete` | 変更影響分析 |
| GET | `/api/unknowns?status=open\|resolved\|all` | 未特定一覧 |
| GET | `/api/unknowns/{id}` | 未特定の詳細 + 根拠 + 候補（根拠との一致度順） |
| POST | `/api/unknowns/{id}/resolve` | `{"target_id": "..."}` または `{"new_object": {"type":"Batch","name":"...","team_id":"..."}}` |
| GET | `/api/governance/direct-access` | 正規ルート外のデータ参照一覧 |
| GET | `/api/governance/summary` | 集計（正規ルート外 / 責任チーム未設定 / 未特定 / 件数） |
| GET | `/api/governance/drift?stale_days=30` | 鮮度・ズレ検知 |
| POST | `/api/design-review` | `{"name","description","fields":[],"system","use_llm"}` → REUSE/EXTEND/CREATE |
| GET | `/api/ontology` | Ontology（YAML の内容） |

---

## 8. 5 分デモシナリオ

| # | 操作 | 見せるもの | US |
|---|------|-----------|----|
| 0 | **ダッシュボード** | KPI タイル、今すぐ確認したいこと（リスク高）、未特定の一覧、Customer 周辺のミニマップ | 全体 |
| 1 | **全体マップ**で「Customer」を検索（初期表示は Customer 中心・2 段） | テーブル → API → サービス/バッチの階層、担当チームは下段。未特定はひし形、正規ルート外は赤破線 | US-03 |
| 2 | **変更影響分析** → `テーブル: customer` / `テーブル／項目の変更` | リスク高。Billing App・Analytics Daily Batch・UNKNOWN-001 が直接、Order App は `参照する → 提供する → 呼び出す` の間接。相談先 4 チーム | US-01, 06 |
| 3 | → `API: Get Customer` / `API の変更` | 呼び出している側（Order / Billing）と責任チーム | US-02 |
| 4 | **ルール逸脱の確認** | Billing の直接参照が高リスクで「迂回」。責任チーム未設定: Address, Analytics Legacy Batch。鮮度・ズレ: Analytics の直接参照が 8/20 以降観測なし、Billing の API 利用は申告なし、Order → Update Customer は申告のみ | US-05 |
| 5 | **未特定の利用元** → `UNKNOWN-001` | 根拠（`rpt_reader` / `10.20.3.14` / `subnet=analytics-legacy` 03:30）→ 候補先頭の **Analytics Legacy Batch** として特定 | US-04 |
| 6 | 全体マップへ戻る（中心: Analytics Legacy Batch） | 未特定が消え、名前付きで表示。「特定済み」に履歴 | US-04 |
| 7 | **新規データ設計レビュー**で `shipping_address`（初期値） | 類似 customer_address / Address、推奨 **既存を拡張**、「時点」から **新規に作成** の別案 | US-07 |
| 8 | 変更影響分析 → `API: Get Invoice` / `廃止` | 利用先なしで廃止可（低）。`テーブル: customer` / `廃止` は 5 件 + 未特定で不可 | US-08 |

デモ後は `docker compose run --rm -e SEED_RESET=1 seed` で初期状態に戻す。

---

## 9. 意思決定の記録（なぜそうなっているか）

実装中に利用者と相談して決めたこと。設計書に無い、または設計書と異なる点はここに理由を残す。

| 日付 | 決定 | 理由 |
|---|---|---|
| 2026-10-05 | ホスト公開ポートを `BIND_HOST`（既定 0.0.0.0）で明示 | 他マシンからデモを見られるように。ローカル限定にしたいときは 127.0.0.1 |
| 2026-10-05 | Evidence を Relation の属性ではなく `:Evidence` ノードにし、`relation_id` で結ぶ | Neo4j は Relation に Node をつなげない。複数根拠を 1 関係に持たせるため |
| 2026-10-05 | 廃止判定で PROVIDES を非ブロッキングに | API の提供元は「利用者」ではなく「廃止する側」。情報として表示はする |
| 2026-10-05 | 影響分析で同じ関係を直後に逆向きに辿らない | API 変更で同じサービスの兄弟 API が全部影響に出てしまうノイズを防ぐ |
| 2026-10-05 | 周辺 Graph は「表示ノード間の辺をすべて返す」 | 経路上の辺だけだと Team → Service などが欠け、孤立して見えた |
| 2026-10-05 | グラフは階層表示（左→右）を既定にし、放射表示は切替 | 利用者が「元データに近い順に左から並ぶ方が読みやすい」と判断。放射状は汎用ツールの慣習で、ドメインに層があるなら層で並べる方が依存の流れが読める |
| 2026-10-05 | 業務データ（BusinessObject）は既定で非表示 | 抽象概念と具体物が混ざって見える。モデルからは消さない（設計レビュー・正規ルート判定・検索の入口に必要） |
| 2026-10-05 | 担当チームはレーンではなく下段の列 | 左右の流れに置くと「チームが呼び出している」ように見える。OWNS は縦線で区別 |
| 2026-10-05 | アイコンは Lucide（ISC） | 手描き SVG より統一感がある。Service=server、Batch=calendar-clock、Table=table-2、API=code-xml、Team=users、業務データ=tag、Unknown=circle-question-mark |
| 2026-10-05 | 画面文言は日本語、データ名は英語 | 閲覧者は経営層。ただし実在する資産の名前を翻訳すると「どれのことか」で誤解が生じる |
| 2026-10-05 | 鮮度・ズレ検知を追加（設計書外） | 人の記憶に頼る運用は陳腐化する。根拠の日時と申告/観測の区別から機械的に「更新すべき点」を出し、通知先チームを付ける。将来は週次通知へ |
| 2026-10-05 | トップをダッシュボードにし、全体マップは `/map` へ | 経営層向けに KPI と要確認事項を最初に見せる |
| 2026-10-06 | システム名は「Customer System」のように System を付ける | 業務データ Customer・チーム Customer Team と同じ単語が並び、箱がシステムであることが伝わりにくかった。fixture の `system` 属性と資料の図に反映 |
| 2026-10-06 | 構成図は System ⊃ Service ⊃ { API, DB } の入れ子で描く | 「サービスがアプリケーションで、API はその窓口、DB はそのサービスだけが更新するもの」という説明と絵を一致させる。API を素通りして DB に届く線が迂回として見える |
| 2026-10-06 | アプリケーションの名前は「Customer App」、種類の表示は「アプリケーション」 | 「Service」は業務サービスと紛らわしく、「API」は窓口と中身を混同する。App なら API ノード（窓口）と区別でき、経営層にも伝わる |
| 2026-10-05 | `seed` は backend イメージを共有 | 別イメージだと backend だけ再ビルドしたとき seed が古いコードで動く事故があった |

---

## 10. 作業の作法（エージェント向け）

1. **設計書 §17 の制約を守る**: Docker Compose で完結、Neo4j へのアクセスは Backend のみ、seed は冪等、認証・Kafka・Kubernetes・VectorDB・OpenSearch は追加しない、Graph の全件表示を既定にしない、LLM キー無しで US-01〜06, 08 が動く、不明な依存は Unknown として残す。
2. **変更の反映**: backend → `docker compose up -d --build --wait backend`、frontend → 同 `frontend`、fixture/ontology → `docker compose run --rm seed`（Relation の from/to を変えた場合や削除は `SEED_RESET=1`）。
3. **テスト**: `docker compose run --rm --no-deps backend pytest -q`。分析ロジックを変えたら `backend/tests/` に fixture ベースの単体テストを足す（Neo4j 不要）。バックエンドの文言（注意事項など）は日本語で、テストもその文言を見ている。
4. **フロントの用語**: 新しいラベルは `frontend/src/lib/api.ts` の辞書に追加し、ページに直書きしない。種別アイコンは `src/lib/icons.ts`。
5. **画面確認**: 全ページが 200 を返すことに加え、可能ならヘッドレスブラウザで描画してコンソールエラーが無いことを確認する（Playwright + Chromium で `/`, `/map`, `/impact`, `/governance`, `/unknowns`, `/unknowns/unknown%3AUNKNOWN-001`, `/objects/service%3Abilling`, `/design-review`）。
6. **README を更新する**: 挙動・用語・判断を変えたら本ファイルの該当節と §9 に追記する。
7. **デモ状態**: Resolve を試したあとは `SEED_RESET=1` で戻す。fixture の日付は固定なので「経過日数」は実行日で変わる（デモ前に `fixtures/evidence.yaml` の `last_seen` を調整してよい）。

---

## 11. 既知の注意点

- 業務データを非表示にすると、業務データ経由でしかつながっていないノード（customer_address, order, Order Team など）が孤立して見える。必要なら「隠したノードを素通りする辺」か「業務データをグループ枠として描く」対応を検討（未実装）。
- Neo4j は Community 単一ノード。HA / バックアップは対象外。
- フォントは OS 標準（Inter / Noto Sans JP があれば使用）。Web フォントはビルド時のネットワーク依存を避けて未導入。
- LLM 解説は `claude-opus-5-5` を使い、拒否時はサーバサイド fallback（`fallbacks="default"`）を有効化している。不要なら `backend/app/services/llm.py` を外せる。
- 担当チーム名は fixture 上は英語（Customer Team）。実運用では日本語の部署名になる想定で、`name` を変えるだけで対応できる。

## 12. 次の候補（未着手）

- 鮮度・ズレの週次通知（Slack / メール）。検知と通知先は実装済みなので送信部分のみ。
- Collector: DB クエリログ / API ゲートウェイログ / OpenAPI / サービスカタログから Relation と Evidence を生成し、Unknown を自動起票（設計書 §18）。
- 業務データを Cytoscape の compound node（グループ枠）として描く表現。
- 変更申請やデプロイパイプラインで影響分析を自動実行し、Unknown が残っていれば差し戻すゲート。
- クラウド運用の構成検討（`docs/cloud-deployment-notes.md` を出発点にする）。

## 13. 使用しているオープンソース素材

- アイコン: [Lucide](https://lucide.dev)（ISC License）
- グラフ描画: [Cytoscape.js](https://js.cytoscape.org)（MIT）

## 14. 受入条件チェック（設計書 §16）

- [x] `docker compose up -d --build` で frontend / backend / neo4j が healthy
- [x] `docker compose run --rm seed` を 2 回実行しても Node / Relation 数が変わらない（28 / 38 / Evidence 11）
- [x] US-01〜US-08 が fixture だけで再現できる（§8）
- [x] Unknown Resolve 後に Graph と未特定件数へ反映される
- [x] 影響分析の結果に path / owner / warning / unknownCount が含まれる
- [x] Frontend は Backend API 経由のみ。コンテナ内部で localhost を使わない
- [x] README だけで第三者が起動・初期化・デモできる
