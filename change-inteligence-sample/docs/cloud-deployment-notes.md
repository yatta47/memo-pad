# クラウド運用に向けたメモ（Graph DB の選択肢）

作成日: 2026-10-05
状態: PoC 段階のメモ。クラウドで運用する構成を別途検討するときの材料。

現在の PoC は Docker Compose 上の **Neo4j 5 Community** を Graph の Source of Truth としている。
Backend のうち Neo4j に触るのは `backend/app/graph/client.py` と、Cypher を直接書いている
`backend/app/services/objects.py`（周辺 Graph）、`backend/app/services/unknowns.py`（Resolve）、
`backend/app/seed.py`（冪等 seed）の 4 ファイル。影響分析・Governance・Design Review は
`graph/snapshot.py` が作るインメモリ snapshot 上で動くため、DB 製品には依存しない。

---

## 1. AWS

| 選択肢 | 概要 | 向いている場面 | PoC からの変更 |
|---|---|---|---|
| **Neo4j AuraDB**（Neo4j 社のマネージド SaaS） | AWS リージョン上で Neo4j 社が運用。Free / Professional / Business Critical / Enterprise（Virtual Dedicated Cloud）。AWS Marketplace 経由で契約でき AWS クレジットを充当可 | PoC → パイロット。運用負荷を最小にしたい | `NEO4J_URI` を `neo4j+s://xxxx.databases.neo4j.io` に変更するだけ |
| **自前運用 Neo4j on EC2** | Marketplace AMI または Docker。クラスタ（HA）とオンラインバックアップは Enterprise ライセンスが必要。Community は単一ノード | VPC 内に閉じたい。ライセンスを自社管理したい | ほぼ無し（compose 構成をそのまま載せられる） |
| **Neo4j on EKS / ECS** | 公式 Helm chart。クラスタ化は Enterprise | 既に Kubernetes 基盤がある | Neo4j の Helm 化のみ |
| **Amazon Neptune**（AWS ネイティブ） | Neo4j ではない AWS のグラフ DB。openCypher を **Bolt** で受けるため Python の neo4j ドライバから接続可。Serverless あり | AWS 純正で揃えたい。Neo4j ライセンスを持ちたくない | コード修正が必要（下記） |

### Neptune を選ぶ場合の注意点
- `CREATE CONSTRAINT` / `CREATE INDEX` が無い → seed の冪等性はアプリ側の `MERGE` だけで担保
- APOC / Graph Data Science は使えない（PoC では未使用）
- 接続 URI は `bolt://` のみ。`neo4j://` ルーティングは不可
- `LOAD CSV` は無い。大量投入は AWS Glue 等の ETL 前提（fixture 規模なら Bolt 経由の MERGE で十分）
- ドライバの `notifications_min_severity` など Neo4j 5 固有オプションは外す

### 閉域接続
- Aura の **PrivateLink** は Enterprise ティア限定（Free / Pro では不可）

---

## 2. Google Cloud

| 選択肢 | 概要 | PoC からの変更 |
|---|---|---|
| **Spanner Graph**（Google ネイティブ） | Spanner 上のプロパティグラフ機能。クエリは ISO 標準 **GQL**（openCypher 構文の互換サポートあり）。同じテーブルを SQL とグラフの両方から扱える | 接続方式・スキーマ・更新系クエリの書き換え（下記） |
| **Neo4j AuraDB on Google Cloud** | Google Cloud Marketplace から契約。閉域接続は Private Service Connect（Enterprise ティア） | `NEO4J_URI` の差し替えのみ |
| **自前運用 Neo4j on GCE / GKE** | compose をそのまま VM へ、または公式 Helm chart で GKE | ほぼ無し |

### Spanner Graph を選ぶ場合の注意点（Neptune より変更が大きい）
- **Bolt が無い**。`google-cloud-spanner` クライアント経由になるため `graph/client.py` を差し替える
- **スキーマが必要**。ノード／エッジのテーブルと `CREATE PROPERTY GRAPH` 定義を先に作る。
  `ontology/object-types.yaml` / `relation-types.yaml` から生成できる。Ontology をスキーマとして強制できる利点にもなる
- **GQL と Cypher は似て非なるもの**。`MATCH` パターンはほぼ同じだが `MERGE` は無く INSERT / UPDATE の SQL で書く。
  seed と Unknown Resolve の書き換えが必要。可変長パス `-[*1..3]-` は GQL でも書ける
- **最小構成でも Spanner の課金が乗る**。PoC 用途なら Neo4j Community コンテナや AuraDB Free のほうが安い
- 以前 Google が案内していた Bigtable 上の JanusGraph 構成は現在は推奨されず、Spanner Graph が後継の位置づけ

---

## 3. 判断の軸

1. **Neo4j を使い続けるか、クラウド純正に寄せるか**
   - Neo4j 継続: Aura（マネージド）または自前運用。コード変更はほぼ無し。Bloom / Browser / GDS などツール群が使える
   - 純正寄せ: AWS → Neptune（小〜中規模の修正）、Google Cloud → Spanner Graph（グラフ層の書き直し）
2. **閉域接続（VPC 内に閉じる）が必須か** → Aura なら Enterprise ティア。自前運用なら制約なし
3. **HA / バックアップの要件** → Neo4j 自前運用は Enterprise ライセンスが必要になる境界
4. **コスト** → PoC〜パイロットは Aura Free / Professional が最安。純正 DB は最小課金に注意
5. **将来の Collector（設計書 §18）** → ログ収集基盤（CloudWatch / Cloud Logging、Glue / Dataflow）との距離が近いのは純正 DB

### 段階的な進め方（案）
1. PoC: Docker Compose + Neo4j Community（現状）
2. パイロット: AuraDB Professional。`NEO4J_URI` の差し替えのみで移行し、Collector を 1〜2 本追加
3. 本番: 閉域・SLA 要件が固まった時点で Aura Enterprise か自前 Enterprise、または純正 DB への移行を判断

---

## 4. 参考: 類似製品のカテゴリ

- データカタログ / リネージ: Collibra, Alation, Atlan, Informatica, Microsoft Purview, Google Dataplex, Solidatus, MANTA(IBM), Select Star, Secoda, Coalesce Catalog。OSS: OpenMetadata, DataHub, Apache Atlas, Amundsen, Marquez / OpenLineage
- サービスカタログ / 内部開発者ポータル: Backstage, Port, Cortex, OpsLevel, Atlassian Compass
- EA / ソフトウェアインテリジェンス: LeanIX, Ardoq, BiZZdesign, CAST Imaging, vFunction, CodeLogic, ServiceNow Service Mapping, Dynatrace Smartscape, Datadog Service Map
- オントロジー型: Palantir Foundry Ontology（本 PoC の Object Type / Relation Type の発想元）, Stardog, Graphwise
- 発展形の現実解: データ側 OpenMetadata or DataHub + サービス側 Backstage のメタデータを Neo4j 等に寄せて横断分析

## 参考リンク
- Neo4j on AWS: https://neo4j.com/cloud/aura-aws/
- Aura + AWS PrivateLink: https://neo4j.com/blog/auradb/neo4j-aws-privatelink-configuration/
- Neptune と Neo4j の互換性: https://docs.aws.amazon.com/neptune/latest/userguide/migration-compatibility.html
- Spanner Graph: https://cloud.google.com/spanner/docs/graph
- Spanner Graph への移行: https://cloud.google.com/spanner/docs/graph/migrate
