# 事例カードのスキーマ

STEP 1 の SKILL、事前準備の事例データ、PostgreSQL の列、Jira のカスタムフィールドがすべてこの形を共有する。
1事例 = 1 JSON ファイル。`catalog/<id>.json`。

| キー | 型 | 日本語名 | 備考 |
|---|---|---|---|
| `id` | string | ID | 出典のホスト名とスラッグから作る。ファイル名と一致 |
| `title` | string | タイトル | 40字以内。Jira の summary |
| `department` | string | 部署・役割 | 困っていた人の業務機能を短い名詞1つで（10字以内）。会社名ではない。ソリューション提供企業の事例は、その顧客側の部署・役割 |
| `who_and_problem` | string | 誰が、何に困っていたか | 主語（部署・役割）と困りごとを1〜3文で |
| `problem_types` | string[] | 困りごとの型 | 下の「困りごとの型」から1〜2個。先頭が主。この一覧以外の語は使わない |
| `ai_and_system` | string | AIと周辺の仕組みが、何をしているか | AIの役割と、AIの外側にある仕組み（データ連携、承認、通知など）を分けて書く |
| `platforms` | string[] | 使っている基盤 | 記事に出てくるサービス・製品・モデルの名前を、下の正規化辞書の表記で列挙。1件以上。記事に無いものは入れない |
| `requirements` | string | 必要なデータ・基盤・運用体制 | データ、基盤、運用体制の3点を含む |
| `confirmed_effects` | string | 確認できた効果 | 出典に数値や実測の記述があるものだけ。無ければ空文字 |
| `hypothesized_effects` | string | まだ仮説の効果 | 出典が「期待している」「見込む」と書いているもの。確認済みと混ぜない |
| `source_url` | string | 出典URL | |
| `confirmed_at` | string (YYYY-MM-DD) | 確認日 | カードを書いた日 |

`problem_types`、`department`、`platforms` はグラフの辺の材料。「意味で入って（ベクトル）、関連で広げる（グラフ）」の後者を支える。関連事例の中心は `problem_types`（同じ困りごと）で、部署と基盤はその次。

## 困りごとの型（固定の8種）

| 型 | 例 |
|---|---|
| 情報検索・参照に時間がかかる | 契約書PDFの目視、規程検索、マニュアル参照、過去履歴の検索 |
| 手入力・転記・記録の負荷 | CRM入力、薬歴SOAP、映像メタデータ付与、伝票作成 |
| 文書・資料作成の負荷 | 提案書、報告書、議事録、翻訳、記事生成 |
| 問い合わせ・対応の負荷 | ヘルプデスク、サポート回答、電話対応、FAQ |
| 属人化・スキル差 | ベテラン依存、品質のばらつき、新人育成、判断軸の共有 |
| 調査・分析・原因究明に時間 | システム調査、不良原因、脆弱性、環境分析、市場調査 |
| 開発・運用の速度と統制 | 内製化、全社基盤、ガバナンス、CI/CD、プロトタイピング |
| 監視・見守りの限界 | 一次産業の見回り、セキュリティ運用のアラート |


## `platforms` の正規化辞書

同じものを1つの表記に寄せる。辞書に無いものはベンダーの正式名称で書き、辞書に追記する。

| 正規表記 | 揺れの例 |
|---|---|
| Amazon Bedrock | Bedrock |
| Amazon Bedrock AgentCore | AgentCore, Bedrock AgentCore |
| Amazon Bedrock Knowledge Bases | Knowledge Bases, ナレッジベース |
| Amazon Bedrock Guardrails | Guardrails |
| Amazon Q Developer | Q Developer |
| Amazon Q Business | Q Business |
| Kiro | |
| Strands Agents | Strands |
| Amazon Connect | Connect |
| Amazon Transcribe | Transcribe |
| AWS Lambda | Lambda |
| Amazon S3 | S3 |
| Amazon DynamoDB | DynamoDB |
| Amazon Aurora | Aurora |
| Amazon ECS | ECS, Fargate |
| Amazon API Gateway | API Gateway |
| Amazon OpenSearch Service | OpenSearch |
| Amazon SageMaker | SageMaker |
| Claude | Claude 3.5 Sonnet, Claude 4 など（モデル名の版は落とす） |
| Amazon Nova | Nova |
| Gemini | Gemini 1.5 Pro など |
| Vertex AI | |
| Vertex AI Search | Vertex AI Search and Conversation |
| Google Cloud Speech-to-Text | Speech-to-Text |
| App Engine | Google App Engine |
| BigQuery | |
| Azure OpenAI | Azure OpenAI Service |
| Azure AI Search | Azure Cognitive Search |
| Azure App Service | |
| Microsoft Copilot Studio | Copilot Studio |
| Microsoft 365 Copilot | M365 Copilot |
| GPT | GPT-4, GPT-4o など（版は落とす） |
| Slack | |
| Microsoft Teams | Teams |
| LINE WORKS | |
| Dify | |
| LangChain | |
| MCP | Model Context Protocol |
| Generative AI Use Cases JP | GenU |
| Salesforce | |
| Claude Code | |
| Cursor | |
| Amazon Bedrock Agents | AgentCore とは別物 |
| Amazon S3 Vectors | S3 とは別物 |
| Amazon Titan | |
| Amazon CloudWatch | CloudWatch |
| Amazon RDS | RDS Proxy, RDS PostgreSQL |
| Amazon Redshift / Amazon Neptune / Amazon EKS / Amazon ECR / Amazon SQS / Amazon EventBridge / AWS Step Functions / Amazon Cognito / Amazon CloudFront / Amazon ElastiCache / Amazon Rekognition / Amazon QuickSight / AWS CDK / AWS WAF / AWS KMS / AWS IAM / AWS DevOps Agent | AWS 正式名称のまま |
| Azure Functions / Azure Blob Storage / Azure AI Translator / Azure AI Speech / Microsoft Entra ID / Microsoft SharePoint / Microsoft 365 | Microsoft 正式名称のまま |
| Cloud Storage / Cloud Run / Google Kubernetes Engine / BigQuery / Looker Studio / Dataplex / Datastream / Cloud Workflows / MedLM / Google Workspace / Google Drive | Google Cloud 正式名称のまま |
| Cohere Command | Command R+ など（版は落とす） |
| NVIDIA NeMo Guardrails / Langfuse / LiteLLM / Mastra / OpenTelemetry / Argo CD / FAISS / Databricks / Datadog / Splunk / Jira / GitHub / Auth0 / LINE | OSS・SaaS 正式名称のまま |

入れないもの: 「今後活用予定」「移行元」「比較対象」として出てくる名前、事例側の自社製品名（対象物であって基盤ではない）、言語・小ライブラリ（Python, Flask, pdfminer など）、汎用語（RAG, OCR, CRM, サーバーレス）。

## 効果の切り分け例

| 出典の記述 | 分類 |
|---|---|
| 「処理時間を平均40%短縮した」「月200時間の削減を確認」 | `confirmed_effects` |
| 「年間で数千時間の削減を見込む」「今後、他部署への展開で効果が出ると期待」 | `hypothesized_effects` |

## JSON 例

```json
{
  "id": "example-com-invoice-ocr",
  "title": "請求書処理のOCR＋LLM照合",
  "department": "経理",
  "who_and_problem": "経理部が月1,500件の請求書を手入力しており、締め日前に残業が集中していた。",
  "problem_types": ["手入力・転記・記録の負荷"],
  "ai_and_system": "AIはOCR結果と発注データの照合と不一致理由の要約を担当する。周辺の仕組みは、スキャン取り込み、発注DBとの連携、担当者への承認依頼通知で、AIの外にある。",
  "platforms": ["Amazon Bedrock", "Claude", "AWS Lambda", "Slack"],
  "requirements": "データ: 発注DBと請求書画像。基盤: OCRサービスとLLM API、承認ワークフロー。運用体制: 不一致時の確認担当を経理内で1名固定。",
  "confirmed_effects": "手入力時間を月120時間削減（導入3か月後の実測）。",
  "hypothesized_effects": "不一致の傾向分析により、発注側のミス削減につながると見込んでいる。",
  "source_url": "https://example.com/case/invoice-ocr",
  "confirmed_at": "2026-09-08"
}
```

## PostgreSQL の列（STEP 2 で Cursor / Claude Code が作る想定）

キーをそのまま列名にする。`id` が主キー。`confirmed_at` は `date`。`problem_types` と `platforms` は `text[]`。他は `text`。

## Jira のカスタムフィールド

`title` は標準の summary。残り10項目をカスタムフィールドにする（`problem_types` と `platforms` は複数選択またはラベル、`department` は短いテキスト）。ID の対応表は `docs/jira-fields.md`（0-E で作成）。
