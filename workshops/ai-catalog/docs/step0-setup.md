# STEP 0: 環境準備

作成: 2026-09-08
前提: 参加者はエンジニア。Jira はまず個人の Atlassian Cloud で試す。
このマシン（Debian）で先に通し、その後 Local PC（Docker Desktop + Cursor Development VM）に持っていく。

## 0-A. リポジトリ骨格

担当: Claude

```
workshop-ai-catalog/
├── docs/                 # 計画・台本・プロンプト
│   ├── workshop-plan.md
│   ├── step0-setup.md
│   ├── case-schema.md    # 事例カードのスキーマ（STEP 1 の SKILL と事前データが共有）
│   └── prompts/          # 当日貼る指示文4本
├── catalog/              # 事例カードJSON（事前準備 30〜50件 + 当日1件）
├── infra/
│   ├── compose.yml       # PostgreSQL
│   └── init/01-roles.sql # DB とロールだけ。テーブルは作らない（STEP 2 でライブ作成）
├── scripts/
│   └── reset.sh          # DB と Jira を初期状態に戻す
├── .cursor/mcp.json      # Postgres MCP Pro の設定（当日は自作MCPを追記）
├── .env.example
├── .gitignore            # .env, catalog/*.tmp など
└── README.md
```

当日AIが作る4部品（`.claude/skills/`, `app/`, `sync/`, `mcp/`）はディレクトリごと存在させない。SKILL は Claude Code の規約に合わせて `.claude/skills/case-card/SKILL.md` に作らせる。Cursor で使うときは `.cursor/skills` → `../.claude/skills` のシンボリックリンクで共有する。

- [ ] `git init`（未実施。実施可否を確認する）
- [ ] life-project の `.claude/rules/related-repos.md` に登録

## 0-B. PostgreSQL（Docker）

担当: Claude

- イメージ: `postgres:17`
- ホスト側ポート: `5432`（このマシンでは空き。15432 は graphdb-catalog-lab、54329 は ks-db が使用中）
- 環境変数で上書き可能にして Local PC でも同じ compose を使う
- `01-roles.sql` で作るもの
  - DB `aicase`
  - ロール `aicase_rw`（Cursor / Postgres MCP / sync 用。CREATE, INSERT, SELECT, UPDATE）
  - ロール `aicase_ro`（将来の参加者向け。SELECT のみ）
  - **テーブルは作らない**。STEP 2 でCursorに作らせるのが見せ場
- 確認: `psql` で両ロールで接続できること

## 0-C. Python 環境

担当: Claude

- `uv` で管理（このマシンに導入済み。Local PC 側も同じにする）
- `pyproject.toml` に依存を先入れ: `mcp`, `httpx`, `psycopg[binary]`, `streamlit`
- 当日は `uv run` で起動するだけにし、インストール待ちを出さない
- 確認: `uv run python -c "import mcp, httpx, psycopg, streamlit"`

## 0-D. Postgres MCP Pro を Cursor に設定

担当: Claude（設定ファイル）／ユーザー（Cursor 側での接続確認）

- `crystaldba/postgres-mcp` を `uvx` または Docker で起動する形を `.cursor/mcp.json` に書く
- アクセスモードは `unrestricted`（STEP 2 でテーブル作成と挿入をさせるため）。運営外で使うときは `restricted` に戻す
- 接続文字列は `aicase_rw` を使う
- **要確認**: Cursor がどこで動くか（下記「決めること」）で、接続先ホスト名が変わる

## 0-E. Jira（個人 Atlassian Cloud）

担当: ユーザー（サイト作成・プロジェクト作成・トークン発行）／Claude（フィールドID取得スクリプト）

1. Atlassian Cloud の個人サイトを用意する（無料プランで可）
2. Jira プロジェクトを作る。キー `AICASE`、チーム管理プロジェクトで可
3. カスタムフィールドを作る（`docs/case-schema.md` の11項目のうち、タイトルは標準の summary を使うので10）
   - 部署・役割（短いテキスト）
   - 困りごとの型（複数選択、固定8種）
   - 使っている基盤（ラベル or 複数選択）
   - 誰が、何に困っていたか（段落テキスト）
   - AIと周辺の仕組みが、何をしているか（段落テキスト）
   - 必要なデータ・基盤・運用体制（段落テキスト）
   - 確認できた効果（段落テキスト）
   - まだ仮説の効果（段落テキスト）
   - 出典URL（URL）
   - 確認日（日付）
4. API トークンを発行する。スコープ付きで `read:jira-work` と `write:jira-work`（sync が起票するため）。有効期限は最長1年
   - スコープ付きトークンは `https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/...` 経由でしか使えない。サイトURL直叩きは不可
   - Cloud ID は `https://<site>.atlassian.net/_edge/tenant_info` で取れる
5. `.env` に入れる: `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_CLOUD_ID`, `JIRA_PROJECT_KEY=AICASE`
6. Claude がフィールドID取得スクリプトを回し、`docs/jira-fields.md` に対応表を書く。この表を STEP 4 と STEP 5 のプロンプトに貼る

確認: トークンで `AICASE` の Issue 一覧が取れること。0件でよい。

## 0-F. 事例データ（30〜50件）

担当: Claude（生成）／ユーザー（内容の一瞥）

- 種: `ai-architecture-catalog/catalog/index.json` の50件（`link` と `purpose_ja` を持つ）
- 注意: 50件の多くはアーキテクチャ解説記事で、「誰が、何に困っていたか」を持たないものが混じる。カードの形に合わないものは落とし、足りなければ AWS の導入事例（customer stories）で補う
- 生成手順: `docs/case-schema.md` の形で、URL ごとに本文を読んでカードJSONを1件ずつ `catalog/` に書く。当日の STEP 1 と同じ処理を事前に回した、という説明にする
- **STEP 5 の質問文に答えられる事例を必ず含める**。質問文が決まってから最後の数件を選ぶ
- 確認: JSON が `docs/case-schema.md` に対して妥当であること（簡易チェックスクリプト）

## 0-G. 指示文4本

担当: Claude（下書き）／ユーザー（磨き込みとリハーサル）

`docs/prompts/` に置く。指示文はワークショップの主役なので、各本を **注釈付き版**（各行が「情報」か「指示」かを印で示す。画面に出す用）と **当日貼る版**（印なし）の2ファイルで持つ。

| ファイル | 渡す材料 | うち「情報」 | うち「指示」 |
|---|---|---|---|
| `01-skill.md` | カード8項目、出力JSONの形、効果/仮説の切り分け例2つ、出力先 `catalog/` | スキーマ、切り分け例 | 出力先、1URL=1ファイル |
| `03-webapp.md` | Streamlit 1ファイル、一覧と検索のみ、接続文字列は `.env` から | 接続文字列、テーブル名 | 1ファイル、機能を増やさない |
| `04-sync.md` | 挿入のみ、Issue キーで冪等、Jira フィールドID対応表、Cloud ID 経由のエンドポイント | フィールドID表、エンドポイント | 挿入のみ、冪等、LLMを挟まない |
| `05-mcp.md` | `PROJECT_KEY`、対応表、読み取り3ツール名、書き込みなし、JQL を外から受けない | `PROJECT_KEY`、対応表 | 読み取り専用、JQL不可、ツール名 |

STEP 1 の対比用に、雑な指示（「このURLを事例にまとめて」）も `01-skill-sloppy.md` として置く。
STEP 2 は指示文ではなく発話（「catalog/ の JSON を全部 DB に入れて」）なので台本側に書く。

## 0-H. 初期化スクリプト

担当: Claude

- `scripts/reset.sh`: `aicase` DB のテーブルを全部落とす、Jira `AICASE` の Issue を全件削除する、`catalog/` の当日分（事前準備分以外）を消す
- 当日AIが作った4部品のディレクトリを消す
- リハーサルのたびに叩く

## 0-I. 接続確認

担当: ユーザー（Cursor 側）／Claude（サーバ側）

- [ ] Cursor から Postgres MCP Pro が見える（ツール一覧に出る）
- [ ] Cursor → PostgreSQL に SELECT 1 が通る
- [ ] Web Browser → Streamlit の 8501 に届く（ポート転送）
- [ ] Jira トークンで Issue 一覧が取れる
- [ ] STEP 1 用 URL を前日に一度取得できる

## 進捗（2026-09-08）

| 項目 | 状態 | 備考 |
|---|---|---|
| 0-A 骨格 | 済 | git init は未実施 |
| 0-B PostgreSQL | 済 | `postgres:17`、コンテナ名 `aicase-db`、ホスト 5432。`aicase_rw` は CREATE 可、`aicase_ro` は不可を確認。起動は `docker compose --project-directory . -f infra/compose.yml up -d`（`--project-directory` を付けないと init のマウントが外れる） |
| 0-C Python | 済 | `uv sync` 済。mcp 2.2.0 / httpx 0.28 / psycopg 3.3 / streamlit 1.63 |
| 0-D Postgres MCP | 済（Claude Code 側は承認待ち） | `.mcp.json` → `scripts/postgres-mcp.sh`（`.env` を読んで `uvx --with "mcp<2" postgres-mcp` を起動）。Python クライアントから接続し、9ツールと `execute_sql` が `aicase_rw` で通ることを確認。Claude Code では初回起動時に承認が要る。Cursor 用の `.cursor/mcp.json` は同じラッパーを指す形で後から足す |
| 0-E Jira | 未 | ユーザー側の作業待ち |
| 0-F 事例データ | 済（47件＋STEP 1 の1件に `department` / `platforms` 付与済） | AWS JP ブログ 32件、Google Cloud 7件、Microsoft 6件、その他 2件。大成・BTM は不在を確認。`validate_catalog.py` 全件OK、出典URL重複なし。方針: 数値のない定性効果は confirmed に入れず hypothesized 側に「数値の記載なし」と明記 |
| 0-G 指示文 | STEP 1〜3 分は下書き済 | `docs/prompts/01-skill(.annotated).md`, `01-skill-sloppy.md`, `02-insert.md`, `03-webapp(.annotated).md`。04/05 は Jira 後 |
| 0-H 初期化 | 済 | `scripts/reset.sh`。Jira 部分は `scripts/jira_reset.py` を 0-E で追加 |
| 0-I 接続確認 | 一部 | Postgres 側は済。Jira・ポート転送は未 |

### 判明したこと: MCP Python SDK は 2.x で API が変わっている

`uv` で入る `mcp` は 2.2.0。`FastMCP` は `MCPServer` に改名され、import は `from mcp.server.mcpserver import MCPServer`。
`@mcp.tool()` はそのまま、起動は `mcp.run(transport="stdio")`。
`postgres-mcp` は 1.x 前提なので `mcp<2` を固定して動かしている。

**STEP 5 の指示文に SDK のバージョンと import を書く**。書かないとAIが学習時点の `FastMCP` で書いて落ちる。「正しい情報」の実例としてそのまま使える。

## 決めたこと

1. **まず Claude Code で動かす**。このマシンで通した後、Cursor で別途動作確認する（2026-09-08）

2. **STEP 1 の URL は AWS 導入事例から**（2026-09-08）。第一候補: 大成株式会社「Amazon Bedrock と Amazon Q Developer で非エンジニアが実現する契約書管理 AI エージェントの構築」 https://aws.amazon.com/jp/blogs/news/179920-2/ （2026-04-01 公開、5項目すべて記述あり、非エンジニアのPMが構築した点が「正しい指示が要る」と噛み合う）。予備: 株式会社BTM https://aws.amazon.com/jp/blogs/news/genai-case-study-btm/ （AIがMCP経由でDBを引く構成でワークショップ自身と同型）。**この2本は事前データに含めない**（STEP 2 の挿入で重複するため）
3. **まず STEP 1〜3 までを通す**（2026-09-08）。Jira（0-E）と STEP 4〜5 はその後

## 決めること

4. **STEP 5 の質問文**。STEP 4〜5 に入る前に決める
5. **git init と related-repos.md 登録**を今やるか
