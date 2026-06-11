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
- **B/G構成は `TG_ECS` に現用・待機の両方をカンマ区切りで指定**（FILLで0埋め合算するので、期間中にスワップを跨いでも正しく取れる）。TGの値は `ecs-sizing-discover.sh` の3段目の出力をコピーする。**req_ecsが空のまま（回帰が「有効データ点が不足」）の場合はTG指定が現用TGとズレている**ので、discoverの末尾の検算（TG別の直近リクエスト数）で確認する。
- Task数が期間中に変動していても、#2は総消費CPU（×Task数済み）、#1はTG実測なので回帰は壊れない。
- 回帰期間に**デプロイ直後・障害時間帯が混ざると単価が歪む**。既知の異常時間帯は除外して実行する。

## 0. 環境設定値の調べ方（ecs-sizing-discover.sh）

`ecs-sizing-metrics.sh` に書く CLUSTER / SERVICE / ALB / TG_ECS は、同ディレクトリの
`ecs-sizing-discover.sh` で段階的に絞り込んで取得する。

```bash
./ecs-sizing-discover.sh -p <profile>                            # 1) クラスタ一覧
./ecs-sizing-discover.sh -p <profile> -c <cluster>               # 2) サービス一覧
./ecs-sizing-discover.sh -p <profile> -c <cluster> -s <service>  # 3) ALB/TG解決
```

3段目は `CLUSTER="..."` 形式でそのまま貼れる値を出力する。B/G構成でTGが2本ある場合は
両方表示し、末尾の検算（直近3時間のRequestCount合計）で**現用側のTG**を見分けられる
（0 reqの方が待機側）。

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
8分窓最大上昇幅・時間帯別カーブとピーク/谷比」。生データは `./ecs-sizing-out/<label>.json`、
**分析用のtidy形式CSVが `./ecs-sizing-out/<label>.csv`** に残る。

### M365 Copilot / Excel で分析する場合

CSV（1行=1時点）を渡す。生JSON（タイムスタンプ配列と値配列が分離した形式）は渡さない。

| 列 | 内容 |
|---|---|
| `timestamp_jst` | JST時刻 |
| `ecs_rps` | ECS側TGのリクエスト/秒（回帰の説明変数） |
| `total_cpu_units` | サービス総消費CPU units、1024=1vCPU（回帰の目的変数） |
| `task_count` / `task_cpu_avg_units` | Task数 / タスク平均消費 |
| `svc_cpu_pct` | サービスCPU%（アラームが見るのと同じ値） |
| `task_mem_max_mb` | タスクMEM最大 |
| `alb_total_rps` | ALB全体リクエスト/秒（EC2+ECS合算） |

- 1分粒度×1週間で約10,000行。**Copilot チャットへの直接添付は行数でサンプリングされる
  ことがある**ので、Excelで開いてテーブル化 → Excel内のCopilot（Pythonによる高度な分析）に
  かけるのが確実。チャットに渡すならピーク帯だけに絞ったCSVにする
- プロンプト例:
  `total_cpu_units = a × ecs_rps + b の線形回帰でa・b・R²を出して。時間帯による傾きの違いと外れ値も教えて`
- 回帰のa/b/R²はスクリプト自身も出力するので、Copilot側の結果と突き合わせると検算になる

### 結果から設計値への変換

```
必要総CPU units(100%) = b + a × 全体ピークRPS(#4のp95〜max)
ベースTask数          = ceil( 必要総CPU units ÷ (1024 × 目標使用率0.5〜0.6) )
                        下限: AZ冗長で2〜3
```

- **検証1（線形性）**: R² ≥ 0.7 が目安。低い場合は時間帯別に回帰し直して傾きが揃うか確認。
- **検証2（2期間一致）**: 20%期のaと50%期のaが±15%以内なら外挿を信頼。ズレていたら
  リクエストミックスの差（カナリア振り分け方式）を疑い、保守側（大きいa）を採用。
- **RequestCountPerTargetはスケールメトリクスに採用しない**（設計判断 2026-06-11）。
  リクエストには軽い/重いのミックスがあり、同じreq数でも重いリクエストが偏るとCPUに跳ねる。
  仕事量を直接積分しているCPUの方がトリガーとして正確。CPU%が負荷に追従しない事態
  （5コンテナ同居の頭打ち等）への保険は、req基準への切替ではなくレイテンシ/ThreadPool系の
  検知アラートで張る。

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

注意: `bin(1d)` の日付境界は**UTC**（JSTの朝9時区切り）。JSTの日次＋営業時間帯（7:00〜23:00）で
取るならこちらを使う（期間ピッカーは対象日数分を広めに指定）:

```
fields toMillis(@timestamp) + 32400000 as jst_ms
| fields floor((jst_ms % 86400000) / 3600000) as jst_hour,
         datefloor(fromMillis(jst_ms), 1d) as jst_day
| filter Type = "Container" and TaskDefinitionFamily = "<FAMILY>"
| filter jst_hour >= 7 and jst_hour < 23
| stats max(MemoryUtilized) as mem_max_MB,
        pct(MemoryUtilized, 95) as mem_p95_MB
  by ContainerName, jst_day
| sort jst_day asc
```

（toMillisでエポックms化→+9h、%86400000でその日の経過ms→時を抽出。`jst_day` はJSTの日付として読む。
1日だけ見るならクエリを変えず、期間ピッカーのCustom→Absoluteでローカルタイム07:00〜23:00を指定する方が簡単）

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

## スケーリングポリシー構成（設計合意版 2026-06-11）

CPUとMEMで**方式を分ける**。同じApplication Auto Scalingの傘の下で、Target Tracking（目標値を渡すとAWSが台数を比例計算）とStep Scaling（アラーム発火で固定数を増減）を併用する。

| ポリシー | 方式 | 設定 | 役割 |
|---|---|---|---|
| CPU | **Target Tracking** | ターゲット50〜60%。スケールインのクールダウンはアウトより長く（アウトだけ攻める） | 容量の主役。負荷に追従 |
| MEM | **Step Scaling（アウト専用）** | `AWS/ECS MemoryUtilization` **Maximum統計** > 92% で **+1台**。クールダウン15〜30分。イン方向は定義しない | 個体危篤時の先回り増援 |
| 時刻 | Scheduled | 開放（朝）前にminを引き上げ。夜間閉塞時は**minとmaxの両方**を落とす | 段差はスケジュールで受ける |

MEM Stepの設計理由（経緯の要約）:
- Target TrackingでのMEMはAWS公式が.NET名指しで非推奨（平均メモリは負荷と無相関・比例制御の前提が壊れる・複数target tracking時のスケールイン封鎖）
- Step×Maximum×アウト専用にすると上記が全部回避される: 比例計算をしない / 平均でなく個体を見る / イン側に干渉しない
- 増援は膨らんだ個体を救わない（OOM後の頭数を先回り確保する保険）。救う側は下記の洗い替えが担当
- **スケールインの責任者は常にCPU Target Tracking 1人**（MEM Stepはアウト専用でイン方向を定義しない、スケジュールはminを動かすだけ）。併用時の競合は公式仕様「大きい容量を提示した方が勝つ」で安全側に解決される。既知の干渉は「Stepが足した1台をTTが余剰と見て回収する」ピンポンで、対策は ①TTのイン側クールダウンを長く ②95%自己洗い替えで膨らみ自体を解消（収束する） ③92%発火の慢性化はサイズ増量シグナルとして扱う

### MEMの閾値の階段（スケールとアラートの全体像）

```
85%（個体Max）  → 通知（人: 器のサイズ見直し判断の材料）
92%（個体Max）  → Step Scalingで+1台（先回り増援）
95%（自己診断）  → コンテナヘルスチェックでunhealthy → ECSが自動洗い替え
OOM kill        → ECS自動補充 + stopped reason検知で通知
```

- 95%の自動洗い替えは**アプリ改修不要**で2通り:
  - 本命: **夜間の定期洗い替え** — EventBridge Schedulerから `ecs:UpdateService(forceNewDeployment)` を直接呼ぶ（Lambda不要）。閉塞中＝トラフィックゼロの窓で全タスクを新品化し、メモリの複数日蓄積を設計から消す。夜のスケジュール縮小で大半は自然に日次洗い替えされており、夜間min生存分のケアが主目的
  - 補助: **タスク定義healthCheckでcgroupを読む** — `CMD-SHELL` でコンテナ自身の `/sys/fs/cgroup/memory.current` / `memory.max` を比較し95%超でunhealthy → ECSが自動入替。タスク定義のみで完結。要stg検証: イメージにshell/catがあること・Fargateバージョンでのcgroupパス。閾値ジッタ±数%で一斉自爆を防ぐ
- **閾値の順序（92%増援→95%退場）が「先に1台増やしてから高い個体を落とす」の振り付けになる**。司令塔は不要で、Step・ヘルスチェック・TTが独立に動くだけで surge型洗い替えに近い動きが成立する（順序は保証でなく傾向。92→95が増援起動より速い異常時は数分N-1＝ベース設計で吸収。93〜94%で停滞する個体は夜間定期洗い替えが回収）
- **Step発火回数をメトリクス化する**こと。月に何度も発火する状態は「器が小さい」シグナルなので、自動増援で隠さずタスクMEM増量に回す

## 公式引用集（説明資料用）

出典は主に ECS Best Practices Guide「Optimizing Amazon ECS service auto scaling」
（https://docs.aws.amazon.com/AmazonECS/latest/developerguide/capacity-autoscaling-best-practice.html）
と Application Auto Scaling User Guide
（https://docs.aws.amazon.com/autoscaling/application/userguide/target-tracking-scaling-policy-overview.html）。

**① MEMスケーリング非推奨（GCランタイム、.NET名指し）** — 「MEMでスケールしない」根拠スライド用

> "as with Java, we don't recommend scaling these applications based on memory, because their observed average memory utilization is often uncorrelated with throughput or concurrency."
> （訳: Javaと同様、**.NETやRuby等のGCランタイムをメモリでスケールさせることは推奨しない**。観測される平均メモリ使用率がスループットや同時実行数と無相関になることが多いため）

**② メモリを解放しないアプリへの明示的非推奨** — 同上の補強

> "Some memory-bound applications don't free the memory that's associated with a request when it ends, so that a reduction in concurrency doesn't result in a reduction in the memory used. For this, we don't recommend that you use memory-based scaling."
> （訳: リクエスト終了後もメモリを解放しないアプリは、同時実行数が減ってもメモリが減らない。**この場合メモリベースのスケーリングは推奨しない**）

**③ スケーリングメトリクスの適格条件（比例性）** — メトリクス選定の判断軸スライド用

> "The metric value must scale in proportion to capacity. (...) So, doubling the number of tasks should cause the metric to decrease by 50%."
> （訳: メトリクスは容量に比例して変化しなければならない。**タスク数を2倍にしたらメトリクスは50%下がるべき**）

**④ 複数target trackingポリシーのスケールイン条件** — MEMをtarget trackingに足すと何が起きるかの根拠

> "It will scale out the scalable target if any of the target tracking policies are ready for scale out, but will scale in only if all of the target tracking policies (with the scale-in portion enabled) are ready to scale in."
> （訳: スケールアウトはいずれか1つのポリシー条件で発動するが、**スケールインは全ポリシーの条件が揃わないと発動しない**）

**⑤ CPU飽和の観測例（70-80%）** — 劣化開始点70〜75%の傍証

> "if CPU utilization increases from 0% to 70-80% as you add load, then stays at that level after you add even more load, then it's safe to say that the CPU is saturated."
> （訳: 負荷を足してもCPUが70-80%で頭打ちになるなら、CPUは飽和していると判断してよい）

**注意点2つ**:
- 「常時使用率50〜60%が効率的」という**数値の明文推奨はAWS公式にはない**。公式の立場は「比例性のあるメトリクスを選び、目標値はロードテストとSLOから導く」。数値目安は業界慣行として提示し、出典は付けない（付けると捏造になる）
- 公式は「CPUバウンドでなければ平均スループット/平均同時実行でスケールせよ」とも書いている。**「うちはCPUバウンドなのか」という質疑が来うる**。回答ライン: 実測回帰でCPUと負荷の相関（R²）を確認済みのためCPUで成立する。CPUが追従しない事態はレイテンシ/ThreadPool系の検知で別途拾う

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
