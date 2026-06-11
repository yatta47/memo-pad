#!/usr/bin/env bash
# ecs-sizing-metrics.sh — ECSサイジング用メトリクス一括取得
#
# 20%期 / 50%期 / 直近14日 の3窓をまとめて取得し、設計値の元数字を出力する。
# 要: aws cli v2, python3（aws-vault は任意）。Bash 3.2 互換。
#
# 使い方:
#   1) 下の「環境設定」を書き換える
#   2) 時間窓は「取得窓」(WINDOWS配列) の日付を書き換えるか、-w で都度指定する
#   3) ./ecs-sizing-metrics.sh -p <aws-vaultプロファイル名>
#      -p 省略時は AWS_VAULT_PROFILE 環境変数、それも無ければ素の aws で実行
#
#   -w "ラベル|開始|終了|Period秒" で時間窓をコマンドラインから指定（複数可）。
#   -w を1つでも指定すると WINDOWS 配列は無視される。例:
#     ./ecs-sizing-metrics.sh -p myprofile \
#       -w "phase50|2026-06-02T00:00:00+09:00|2026-06-09T00:00:00+09:00|60"
#
# 出力:
#   標準出力       … 窓ごとの回帰(単価a/固定消費b/R2)・ピークRPS・MEM・上昇幅・カーブ
#   ./ecs-sizing-out/<label>.json … 生データ（再分析用）
set -euo pipefail

PROFILE="${AWS_VAULT_PROFILE:-}"
CLI_WINDOWS=()
while getopts "p:w:h" opt; do
  case "$opt" in
    p) PROFILE="$OPTARG" ;;
    w) CLI_WINDOWS+=("$OPTARG") ;;
    h) sed -n '2,20p' "$0"; exit 0 ;;
    *) exit 1 ;;
  esac
done

# ===== 環境設定（書き換える）=====
CLUSTER="my-cluster"
SERVICE="my-service"
ALB="app/my-alb/0123456789abcdef"            # ALB ARNの "app/" 以降
TG_ECS="targetgroup/my-ecs-tg/0123456789ab"  # ECS側TGの "targetgroup/" 以降

# 取得窓: ラベル|開始|終了|Period秒
#   - 15日より古い窓は1分粒度が消えているので 300 にする
#   - 比較する窓は同じ曜日構成（平日を含む1週間など）で揃える
WINDOWS=(
  "phase20|2026-05-12T00:00:00+09:00|2026-05-19T00:00:00+09:00|300"
  "phase50|2026-06-02T00:00:00+09:00|2026-06-09T00:00:00+09:00|60"
  "recent14d|2026-05-28T00:00:00+09:00|2026-06-11T00:00:00+09:00|60"
)
# =================================

# -w 指定があればそちらを優先
if [ ${#CLI_WINDOWS[@]} -gt 0 ]; then
  WINDOWS=("${CLI_WINDOWS[@]}")
fi

awscli() {
  if [ -n "$PROFILE" ]; then
    aws-vault exec "$PROFILE" -- aws "$@"
  else
    aws "$@"
  fi
}

OUTDIR="./ecs-sizing-out"
mkdir -p "$OUTDIR"

for WIN in "${WINDOWS[@]}"; do
  IFS='|' read -r LABEL START END PERIOD <<< "$WIN"

  MDQ="$OUTDIR/$LABEL.query.json"
  cat > "$MDQ" <<EOF
[
  {"Id":"svc_cpu","MetricStat":{"Metric":{"Namespace":"AWS/ECS","MetricName":"CPUUtilization","Dimensions":[{"Name":"ClusterName","Value":"${CLUSTER}"},{"Name":"ServiceName","Value":"${SERVICE}"}]},"Period":${PERIOD},"Stat":"Average"}},
  {"Id":"cpu_task","MetricStat":{"Metric":{"Namespace":"ECS/ContainerInsights","MetricName":"CpuUtilized","Dimensions":[{"Name":"ClusterName","Value":"${CLUSTER}"},{"Name":"ServiceName","Value":"${SERVICE}"}]},"Period":${PERIOD},"Stat":"Average"}},
  {"Id":"tasks","MetricStat":{"Metric":{"Namespace":"ECS/ContainerInsights","MetricName":"RunningTaskCount","Dimensions":[{"Name":"ClusterName","Value":"${CLUSTER}"},{"Name":"ServiceName","Value":"${SERVICE}"}]},"Period":${PERIOD},"Stat":"Average"}},
  {"Id":"total_cpu","Expression":"cpu_task * tasks","Label":"TotalCpuUnits"},
  {"Id":"req_ecs","MetricStat":{"Metric":{"Namespace":"AWS/ApplicationELB","MetricName":"RequestCount","Dimensions":[{"Name":"TargetGroup","Value":"${TG_ECS}"},{"Name":"LoadBalancer","Value":"${ALB}"}]},"Period":${PERIOD},"Stat":"Sum"}},
  {"Id":"alb_req","MetricStat":{"Metric":{"Namespace":"AWS/ApplicationELB","MetricName":"RequestCount","Dimensions":[{"Name":"LoadBalancer","Value":"${ALB}"}]},"Period":${PERIOD},"Stat":"Sum"}},
  {"Id":"mem_task","MetricStat":{"Metric":{"Namespace":"ECS/ContainerInsights","MetricName":"MemoryUtilized","Dimensions":[{"Name":"ClusterName","Value":"${CLUSTER}"},{"Name":"ServiceName","Value":"${SERVICE}"}]},"Period":${PERIOD},"Stat":"Maximum"}}
]
EOF

  echo "===== ${LABEL} (${START} -> ${END}, period=${PERIOD}s) ====="
  awscli cloudwatch get-metric-data \
    --start-time "$START" --end-time "$END" \
    --metric-data-queries "file://$MDQ" \
    --output json > "$OUTDIR/$LABEL.json"

  METRICS_JSON="$OUTDIR/$LABEL.json" PERIOD="$PERIOD" python3 - <<'PY'
import json, os, statistics, collections, datetime

PERIOD = int(os.environ["PERIOD"])
JST = datetime.timezone(datetime.timedelta(hours=9))
d = json.load(open(os.environ["METRICS_JSON"]))

acc = {}
for r in d["MetricDataResults"]:   # CLIのページング分割をIdでマージ
    acc.setdefault(r["Id"], []).extend(zip(r["Timestamps"], r["Values"]))

def smap(mid):
    return dict(acc.get(mid, []))

def series(mid):
    pairs = sorted(acc.get(mid, []))
    return [t for t, _ in pairs], [v for _, v in pairs]

def pctl(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))] if s else float("nan")

# --- リクエスト単価の回帰: 総消費CPU = a×RPS + b ---
tot_m, req_m = smap("total_cpu"), smap("req_ecs")
xs, ys = [], []
for t in sorted(set(tot_m) & set(req_m)):
    rps = req_m[t] / PERIOD
    if rps > 0:
        xs.append(rps)
        ys.append(tot_m[t])
if len(xs) > 10:
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx > 0:
        a = sxy / sxx
        b = my - a * mx
        ss_tot = sum((y - my) ** 2 for y in ys)
        ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
        r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
        unit = [y / x for x, y in zip(xs, ys)]
        print(f"[回帰] 単価a={a:.2f} units/(req/s)  固定消費b={b:.0f} units  R2={r2:.3f}  点数={len(xs)}")
        print(f"       参考: 単純単価(総CPU/RPS) p50={pctl(unit,50):.1f} p95={pctl(unit,95):.1f}")
        print(f"       R2<0.7なら線形仮定を疑う（時間帯でリクエストミックスが違う等）")
else:
    print("[回帰] 有効データ点が不足（TG/期間の指定を確認）")

# --- 全体ピークRPS（100%時の実測需要）---
_, req_all = series("alb_req")
if req_all:
    rps_all = [v / PERIOD for v in req_all]
    print(f"[全体RPS] p95={pctl(rps_all,95):,.0f}  max={max(rps_all):,.0f}")

# --- 総消費CPUサマリ（比率外挿のクロスチェック用）---
tts, tot = series("total_cpu")
if tot:
    print(f"[総消費CPU units] avg={statistics.mean(tot):.0f}  p95={pctl(tot,95):.0f}  max={max(tot):.0f} (1024=1vCPU)")

# --- タスクMEMピーク ---
_, mem = series("mem_task")
if mem:
    print(f"[タスクMEM MB] p95={pctl(mem,95):.0f}  max={max(mem):.0f}")

# --- 8分窓の最大CPU上昇幅（サービスCPU%）---
cts, cpu = series("svc_cpu")
w = max(1, 480 // PERIOD)
if len(cpu) > w:
    rise, idx = max(((cpu[i + w] - cpu[i], i) for i in range(len(cpu) - w)))
    print(f"[8分窓最大上昇] +{rise:.1f}pt  (発生: {cts[idx]})  ※period=60の窓の値を採用する")

# --- 時間帯別カーブ（JST）とピーク/谷比 ---
hod = collections.defaultdict(list)
for t, v in zip(tts, tot):
    hod[datetime.datetime.fromisoformat(t).astimezone(JST).hour].append(v)
if hod:
    hourly = {h: statistics.mean(v) for h, v in sorted(hod.items())}
    peak, valley = max(hourly.values()), min(hourly.values())
    if valley > 0:
        print(f"[ピーク/谷比] {peak/valley:.2f}  (peak={peak:.0f} / valley={valley:.0f} CPU units)")
    for h, v in sorted(hourly.items()):
        print(f"   {h:02d}時 {'#' * int(40 * v / peak)} {v:.0f}")
PY
  echo
done

echo "生データ: $OUTDIR/<label>.json（設計値への変換式は README.md 参照）"
