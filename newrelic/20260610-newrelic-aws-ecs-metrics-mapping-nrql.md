# New Relic × AWS ECS メトリクスマッピング表 + NRQL集

作成日: 2026-06-10
出典: New Relic公式ドキュメント / AWS公式ドキュメント / newrelic/nri-docker ソース（2026-06時点で確認）

前提構成: ECS（Nginxサイドカー + アプリの2コンテナタスク）、CloudWatch Metric Streams + newrelic-infra（ECS統合）併用。

---

## 0. 要点

- コンテナ別CPU/MEMは **`ContainerSample` イベント + `FACET containerName`** で見る。CloudWatch側にはこの粒度は存在しない
- ContainerSampleは**Metricではなくイベント**。Metrics Explorerには出ない。Query builderで `FROM ContainerSample` を叩くか、Infrastructure → Containers のUIから入る
- 「メモリ使用率」は3系統で**分母が全部違う**（→ §4 落とし穴）

## 1. マッピング表

### CPU系

| 観測対象 | AWS/ECS (CW) | ECS/ContainerInsights (CW) | ContainerSample (newrelic-infra) |
|---|---|---|---|
| Service CPU使用率（予約比%） | `CPUUtilization` (dim: ClusterName+ServiceName) | — | — |
| Cluster CPU使用率/予約率（**EC2のみ**） | `CPUUtilization` / `CPUReservation` (dim: ClusterName) | — | — |
| Service/TaskDef CPU実量 (Units) | — | `CpuUtilized` / `CpuReserved` | — |
| コンテナ別 CPU使用率% | — | — | `cpuUsedCoresPercent`, `cpuPercent` |
| コンテナ別 CPUコア実量/上限 | — | — | `cpuUsedCores` / `cpuLimitCores`(Linux) |
| コンテナ別 kernel/user分解 | — | — | `cpuKernelPercent` / `cpuUserPercent` |
| コンテナ別 CPUスロットル | — | — | `cpuThrottleTimeMs` / `cpuThrottlePeriods`(Linux) |

### メモリ系

| 観測対象 | AWS/ECS (CW) | ECS/ContainerInsights (CW) | ContainerSample (newrelic-infra) |
|---|---|---|---|
| Service メモリ使用率（予約比%） | `MemoryUtilization` (dim: ClusterName+ServiceName) | — | — |
| Cluster メモリ使用率/予約率（**EC2のみ**） | `MemoryUtilization` / `MemoryReservation` (dim: ClusterName) | — | — |
| Service/TaskDef メモリ実量 (MiB) | — | `MemoryUtilized` / `MemoryReserved` ※単位表記はMegabytesだが実際はMiB | — |
| コンテナ別 メモリ使用/上限バイト | — | — | `memoryUsageBytes` / `memorySizeLimitBytes`(Linux) |
| コンテナ別 メモリ使用率% | — | — | `memoryUsageLimitPercent` |
| コンテナ別 RSS / キャッシュ / Swap | — | — | `memoryResidentSizeBytes` / `memoryCacheBytes` / `memorySwapUsageBytes`(Linux) |

### ネットワーク・ストレージ系

| 観測対象 | AWS/ECS (CW) | ECS/ContainerInsights (CW) | ContainerSample (newrelic-infra) |
|---|---|---|---|
| Service 送受信バイト | — | `NetworkRxBytes` / `NetworkTxBytes` (awsvpc/bridgeのみ) | — |
| コンテナ別 送受信バイト/秒 | — | — | `networkRxBytesPerSecond` / `networkTxBytesPerSecond` |
| コンテナ別 エラー/ドロップ | — | — | `networkRxErrors`, `networkRxDropped` 等 |
| Service ストレージR/W | — | `StorageReadBytes` / `StorageWriteBytes` | — |
| コンテナ別 I/O バイト/秒 | — | — | `ioReadBytesPerSecond` / `ioWriteBytesPerSecond`(Linux) |

### FACET/WHEREに使える識別子（ContainerSample）

| 属性名 | 値の例 | 備考 |
|---|---|---|
| `containerName` | `nginx` / `app` | Docker name由来。サフィックスが付くことあり |
| `ecsContainerName` | `nginx` / `app` | **ECSタスク定義のコンテナ名。絞り込みはこちらが安定** |
| `ecsClusterName` | `my-cluster` | |
| `ecsTaskArn` | `arn:aws:ecs:...:task/...` | タスク個体まで絞るデバッグ用 |
| `ecsTaskDefinitionFamily` / `ecsTaskDefinitionVersion` | `my-app-task` / `3` | |
| `ecsLaunchType` | `FARGATE` | |
| `awsRegion` | `ap-northeast-1` | |

クラスター概況は `EcsClusterSample`（`clusterName`, `arn`, `awsRegion`, `ecsLaunchType`）。

## 2. NRQL集

### コンテナ別CPU使用率（時系列、NginxとAppが別の線）

```sql
SELECT average(cpuUsedCoresPercent)
FROM ContainerSample
WHERE ecsClusterName = 'my-cluster'
  AND ecsTaskDefinitionFamily = 'my-app-task'
FACET containerName
TIMESERIES 1 minute SINCE 1 hour ago
```

### コンテナ別メモリ（使用量・リミット・使用率の一覧）

```sql
SELECT
  latest(memoryUsageBytes) / 1048576 AS 'Used (MiB)',
  latest(memorySizeLimitBytes) / 1048576 AS 'Limit (MiB)',
  latest(memoryUsageLimitPercent) AS 'Util (%)'
FROM ContainerSample
WHERE ecsClusterName = 'my-cluster'
FACET containerName
SINCE 30 minutes ago
```

### メモリ使用率アラート用（リミット未設定タスクを除外）

```sql
SELECT average(memoryUsageBytes / memorySizeLimitBytes * 100)
FROM ContainerSample
WHERE ecsClusterName = 'my-cluster'
  AND memorySizeLimitBytes > 0
FACET containerName
TIMESERIES 1 minute SINCE 1 hour ago
```

### Nginxサイドカーだけのネットワーク

```sql
SELECT average(networkRxBytesPerSecond), average(networkTxBytesPerSecond)
FROM ContainerSample
WHERE ecsClusterName = 'my-cluster'
  AND ecsContainerName = 'nginx'
TIMESERIES 1 minute SINCE 1 hour ago
```

### CW Metric Streams側: Service CPU/メモリ使用率（予約比%）

```sql
SELECT average(aws.ecs.CPUUtilization)
FROM Metric
WHERE collector.name = 'cloudwatch-metric-streams'
  AND aws.ecs.ClusterName = 'my-cluster'
FACET aws.ecs.ServiceName
TIMESERIES 1 minute SINCE 1 hour ago
```

```sql
SELECT average(aws.ecs.MemoryUtilization)
FROM Metric
WHERE collector.name = 'cloudwatch-metric-streams'
  AND aws.ecs.ClusterName = 'my-cluster'
FACET aws.ecs.ServiceName
TIMESERIES 5 minutes SINCE 3 hours ago
```

### ContainerInsights実量系（※メトリクス名は要実機確認）

```sql
-- aws.ecs.CpuUtilized か aws.ecs.containerinsights.CpuUtilized かは公式に明記なし（未確認）
-- Metrics Explorer で "aws.ecs" prefix 検索して実名を確認してから使う
SELECT average(aws.ecs.CpuUtilized), average(aws.ecs.CpuReserved)
FROM Metric
WHERE collector.name = 'cloudwatch-metric-streams'
  AND aws.ecs.ClusterName = 'my-cluster'
FACET aws.ecs.ServiceName
TIMESERIES 1 minute SINCE 1 hour ago
```

## 3. Metric Streamsの命名変換ルール

```
namespace/metric → aws.<namespace小文字>.<MetricName>
次元             → aws.<namespace小文字>.<DimensionName>（大小文字保持）
```

| CloudWatch | NRQL上の名前 |
|---|---|
| AWS/ECS `CPUUtilization` | `aws.ecs.CPUUtilization` |
| AWS/ECS `MemoryUtilization` | `aws.ecs.MemoryUtilization` |
| ECS/ContainerInsights `CpuUtilized` | 未確認（Metrics Explorerで実名確認） |

次元属性: `aws.ecs.ClusterName` / `aws.ecs.ServiceName` / `aws.ecs.TaskDefinitionFamily`（CIのみ）

タグ: Metric Streams由来は `tags.<key>`、API Polling由来は `label.<key>`。**Polling前提のNRQL・アラートはMetric Streams移行で壊れる**。

## 4. 落とし穴

1. **「メモリ使用率」の分母が3系統で違う**
   - `AWS/ECS MemoryUtilization`: タスク定義の予約値が分母
   - `ECS/ContainerInsights MemoryUtilized`: 実量（MiB）なので分母なし
   - `memoryUsageLimitPercent`: **コンテナ定義のmemoryリミット**が分母
   - 同じ瞬間でも全く違う値になる。アラート閾値を流用しない
2. **Fargateでコンテナレベルのmemoryリミット未設定 → `memorySizeLimitBytes` = 0** → 使用率も0表示。`WHERE memorySizeLimitBytes > 0` を必ず入れる
3. WHERE絞り込みは `containerName` より **`ecsContainerName`**（ECS定義名で安定）
4. cgroup依存属性（スロットル系・swap・kernel memory等）は「Linux only」表記で**Fargateで取れるか公式に明記なし**（要実機確認）
5. `AWS/ECS` のClusterスコープメトリクス（CPUReservation等）は**EC2起動タイプ専用**。FargateはServiceスコープのみ
6. Container Insightsは別途有効化が必要: `aws ecs update-cluster-settings --cluster <name> --settings name=containerInsights,value=enabled`（追加課金あり）

## 5. 公式推奨アラート3点セット（ECS統合）

- `cpuUsedCoresPercent > 90%`
- `memoryUsageBytes / memorySizeLimitBytes > 0.8`
- `max(restartCount) - min(restartCount) > 5`（再起動ループ検知）

## 参照URL

- https://docs.newrelic.com/docs/infrastructure/elastic-container-service-integration/understand-use-ecs-data/
- https://docs.newrelic.com/docs/infrastructure/elastic-container-service-integration/ecs-integration-recommended-alert-conditions/
- https://docs.newrelic.com/docs/infrastructure/host-integrations/host-integrations-list/docker-container-monitoring-integration/
- https://docs.newrelic.com/docs/infrastructure/amazon-integrations/get-started/aws-integrations-metrics/
- https://github.com/newrelic/nri-docker/blob/master/src/nri/sampler.go
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/available-metrics.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-ECS.html
