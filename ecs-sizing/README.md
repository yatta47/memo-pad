# ECSサイジング用 CloudWatch データ収集クエリ集

EC2→ECS段階移行（20%→50%→100%）のサイジング設計に使うデータの取得手順。

## 方針

**主: リクエスト単価法（RPS正規化）** — CloudWatchで全部取れるので精度最優先ならこれ。

```
リクエスト単価 a = ECS側RPSが1増えたときに増える消費CPU units（回帰の傾き）
固定消費      b = トラフィック0でも食うCPU units（回帰の切片。サイドカー等）
100%時の必要CPU = b + a × 全体ピークRPS（全体RPSはALB実測値、予測不要）
```

1分粒度の「ECS側RPS vs 総消費CPU」を回帰すると点が数千個取れるため、
**R²で線形性の検証までモデルに組み込める**のがこの方法の利点。
2点比率外挿は「検証なしの直線」だが、こちらは「検証付きの直線」になる。

**従: 比率外挿（20%期と50%期の単価一致チェック）** — 2期間で単価aがズレていないかのクロスチェックに使う。±15%以内なら外挿は信頼してよい。

MEMは方式問わず外挿しない（.NET GCは流入に比例しない）。実測ピーク＋ヘッドルームで決める。

## 取得データ一覧

| # | データ | 何を決めるか | 期間/条件 | 取り方 |
|---|---|---|---|---|
| 1 | ECS側TGのRequestCount（→RPS） | 単価回帰の説明変数 | 20%期・50%期それぞれ | スクリプト `req_ecs` |
| 2 | サービス総消費CPU（CpuUtilized×Task数） | 単価回帰の目的変数 | 同上 | スクリプト `total_cpu` |
| 3 | 回帰結果: 単価a・固定消費b・R² | 100%時の必要vCPU・ベースTask数（線形性検証込み） | 1+2から算出 | スクリプトが出力 |
| 4 | ALB全体RequestCount（EC2+ECS合算） | 100%時のピークRPS（実測値、予測不要） | 直近の繁忙日を含む期間 | スクリプト `alb_req` |
| 5 | タスクMEMピーク / コンテナ別MEM日次推移 | MEMサイズ（ヘッドルーム方式）・リーク確認 | 両期間全体 | スクリプト `mem_task` + Logs Insights Q-A |
| 6 | サービスCPU%の8分窓・最大上昇幅 | スケール閾値式の「上昇速度」項 | 直近14日（1分粒度が残る範囲） | スクリプト `rise` |
| 7 | 時間帯別カーブのピーク/谷比 | ベースを攻める価値の判定（2倍以上で有効） | 直近14日 | スクリプト `hourly` |
| 8 | スケールアウト所要時間 | 閾値式の「所要時間」項 | 直近のスケール/デプロイイベント | §3 の手順 |
| 9 | コンテナ別CPU内訳 | 5コンテナ同居のスケールメトリクス頭打ち確認 | 直近 | Logs Insights Q-B |

## 前提・注意（先に読む）

- **Container Insightsは標準でよい（enhanced observability＝拡張は不要）**。本キットが使うのは
  - `ECS/ContainerInsights` のサービス集約メトリクス（CpuUtilized / MemoryUtilized / RunningTaskCount）→ **標準CIで出力される**
  - performanceロググループの `Type="Container"` レコード（Q-A/Q-B）→ **これも標準CIで出力される**（公式リファレンスのログイベント例に Type: Container が含まれる）
  - 拡張が追加するのは「コンテナ単位の**CloudWatchメトリクス化**（ContainerNameディメンション付きメトリクス）」とrestart/health系。サイジング・スケーリング設計には不要
- スケーリングのアラームに使うのは `AWS/ECS CPUUtilization` か `AWS/ApplicationELB RequestCountPerTarget` で、**どちらもContainer Insightsに依存しない**（CI全OFFでも動く）
- 参考: 仮にCIが全OFFでも `AWS/ECS CPUUtilization` の **Average × SampleCount（≒タスク数）× 1024** で総消費CPU unitsは近似できる。標準CIがあるなら不要
- **1分粒度メトリクスは15日で消える**（以降5分に丸め、63日で1時間）。
  - 20%期間が15日以上前なら `PERIOD=300`。回帰の点数は減るが5分平均同士の回帰でも単価は出る。
  - #6（上昇速度）だけは1分粒度必須 → 直近14日以内で取る。
- **Container Insights の performance ロググループ（Q-A/Q-B用）はretention次第で古いデータが消えている**。先に確認:
  `aws logs describe-log-groups --log-group-name-prefix /aws/ecs/containerinsights/ --query 'logGroups[].[logGroupName,retentionInDays]'`
- ディメンション形式: `LoadBalancer` は ARN の `app/` 以降、`TargetGroup` は `targetgroup/` 以降。
- Task数が期間中に変動していても、#2は総消費CPU（×Task数済み）、#1はTG実測なので回帰は壊れない。
- 回帰期間に**デプロイ直後・障害時間帯が混ざると単価が歪む**。既知の異常時間帯は除外して実行する。

## 1. メトリクス収集スクリプト（#1〜#7を一括）

同ディレクトリの `ecs-sizing-metrics.sh` を使う。20%期・50%期・直近14日の3窓を1回の実行でまとめて取得する。

```bash
# 1) スクリプト内の「環境設定」(CLUSTER/SERVICE/ALB/TG_ECS) を書き換える
# 2) 時間窓は「取得窓」(WINDOWS配列) の日付を書き換えるか、-w で都度指定
./ecs-sizing-metrics.sh -p <aws-vaultプロファイル名>

# -w "ラベル|開始|終了|Period秒" で時間窓をコマンドラインから指定（複数可、指定時はWINDOWS配列を無視）
./ecs-sizing-metrics.sh -p myprofile \
  -w "phase20|2026-05-12T00:00:00+09:00|2026-05-19T00:00:00+09:00|300" \
  -w "phase50|2026-06-02T00:00:00+09:00|2026-06-09T00:00:00+09:00|60"

# -p 省略時は AWS_VAULT_PROFILE 環境変数 → それも無ければ素の aws cli で実行
```

時間窓の指定について:

- 開始/終了はISO 8601（`+09:00` 付きでJST指定可）。`get-metric-data` にそのまま渡る
- **回帰用の窓はピーク帯に絞らず、平日を含む数日〜1週間をまるごと指定してよい**。
  回帰は負荷の高低それぞれの点があるほど傾き・切片が安定する（絞るのは2点比較をする場合だけ）
- 窓ごとのPeriodは、15日以内なら `60`、それより古い窓は `300`（1分粒度の保持期限）

出力は窓ごとに「回帰（単価a / 固定消費b / R²）・全体ピークRPS・総消費CPU・タスクMEM・
8分窓最大上昇幅・時間帯別カーブとピーク/谷比」。生データは `./ecs-sizing-out/<label>.json`
に残るので再分析できる。

### 結果から設計値への変換

```
必要総CPU units(100%) = b + a × 全体ピークRPS(#4のp95〜max)
ベースTask数          = ceil( 必要総CPU units ÷ (1024 × 目標使用率0.5〜0.6) )
                        下限: AZ冗長で2〜3
```

- **検証1（線形性）**: R² ≥ 0.7 が目安。低い場合は時間帯別に回帰し直して傾きが揃うか確認。
- **検証2（2期間一致）**: 20%期のaと50%期のaが±15%以内なら外挿を信頼。ズレていたら
  リクエストミックスの差（カナリア振り分け方式）を疑い、保守側（大きいa）を採用。
- **スケールメトリクスをRequestCountPerTargetにする場合**（5コンテナ同居でCPU%が鈍る対策）:
  `ターゲット値 ≒ (1024×0.55 − b/Task数) ÷ a` で req/s/Task が出る。target trackingの
  ALBRequestCountPerTargetは req/分/Target なので60倍して設定（単位は要検算）。

## 2. Logs Insights クエリ（コンテナ単位）

ロググループ: `/aws/ecs/containerinsights/<CLUSTER>/performance`

**Q-A: コンテナ別MEMの日次推移（#5詳細・リーク確認）**

20%期間〜現在まで通しで実行。日次maxが右肩上がりならリーク/保持の疑い。
流入率と無関係にフラットなら「MEMは外挿不要」の裏付けになる。

```
filter Type = "Container" and TaskDefinitionFamily = "<FAMILY>"
| stats max(MemoryUtilized) as mem_max_MB,
        pct(MemoryUtilized, 95) as mem_p95_MB
  by ContainerName, bin(1d) as day
| sort day asc
```

**Q-B: コンテナ別CPU内訳（#9、5コンテナ同居の頭打ち確認）**

サイドカーの固定消費が大きいほど、タスクCPU%はトラフィックに比例しにくく
スケールメトリクスとして鈍る。回帰の切片bの内訳確認も兼ねる。

```
filter Type = "Container" and TaskDefinitionFamily = "<FAMILY>"
| stats avg(CpuUtilized) as cpu_units_avg,
        pct(CpuUtilized, 95) as cpu_units_p95,
        max(CpuUtilized) as cpu_units_max
  by ContainerName
| sort cpu_units_avg desc
```

## 3. スケールアウト所要時間の実測（#8）

「desired増加の指示 → 新タスクがALBでhealthyになり実トラフィックを受けるまで」を測る。

```bash
# (1) 直近のタスク起動イベント時刻を拾う
aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
  --query 'services[0].events[?contains(message, `has started`)].[createdAt,message]' \
  --output table

# (2) その前後のHealthyHostCountの段差時刻を見る
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB \
  --metric-name HealthyHostCount \
  --dimensions Name=TargetGroup,Value="$TG_ECS" Name=LoadBalancer,Value="$ALB" \
  --start-time "<イベント前後30分>" --end-time "<...>" \
  --period 60 --statistics Maximum --output table
```

```
所要時間 = アラーム判定時間（target trackingは3データポイント×1分）
         + (1)→(2) の差分（プロビジョニング + アプリ起動 + ヘルスチェック）
         + slow_start 設定値（入れる場合）
```

直近にスケールイベントがなければ、stg環境で `aws ecs update-service --desired-count +1` を打って計測する（本番でやらない）。

## 最終的に埋めるべき設計値

| 設計値 | 出どころ |
|---|---|
| 100%時の必要vCPU / ベースTask数 | 回帰（a, b）× 全体ピークRPS ÷ 目標使用率50〜60% |
| タスクMEMサイズ | #5のmax + 30〜40%ヘッドルーム（外挿しない） |
| スケールアウト閾値 | 劣化開始点70〜75% − #6の上昇幅（#8の実測が8分と違えば窓を合わせ再計算） |
| min/maxタスク数 | min=谷の必要量+AZ冗長、max=机上100%値×1.5程度+上限到達アラーム |
| スケールイン | クールダウン長め（アウト側だけ攻める） |
| 受容リスクの明文宣言 | 「#8分間で#6pt超の急増時は一時劣化を許容。既知イベントは事前増設」 |
| 移行切替時の特例 | 切替ステップは段差なのでスケーリングに頼らず事前にminを引き上げ |
