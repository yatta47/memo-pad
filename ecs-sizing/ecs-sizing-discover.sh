#!/usr/bin/env bash
# ecs-sizing-discover.sh — ecs-sizing-metrics.sh の環境設定値を調べるための探索ツール
#
# 段階的に絞り込み、最後に CLUSTER/SERVICE/ALB/TG_ECS をコピペ可能な形で出力する。
# 要: aws cli v2（aws-vault は任意）。Bash 3.2 互換。
#
# 使い方:
#   ./ecs-sizing-discover.sh -p <profile>                          # 1) クラスタ一覧
#   ./ecs-sizing-discover.sh -p <profile> -c <cluster>             # 2) サービス一覧
#   ./ecs-sizing-discover.sh -p <profile> -c <cluster> -s <service> # 3) ALB/TG解決
#   -p 省略時は AWS_VAULT_PROFILE 環境変数、それも無ければ素の aws で実行
set -euo pipefail

PROFILE="${AWS_VAULT_PROFILE:-}"
CLUSTER=""
SERVICE=""
while getopts "p:c:s:h" opt; do
  case "$opt" in
    p) PROFILE="$OPTARG" ;;
    c) CLUSTER="$OPTARG" ;;
    s) SERVICE="$OPTARG" ;;
    h) sed -n '2,12p' "$0"; exit 0 ;;
    *) exit 1 ;;
  esac
done

awscli() {
  if [ -n "$PROFILE" ]; then
    aws-vault exec "$PROFILE" -- aws "$@"
  else
    aws "$@"
  fi
}

# --- 1) クラスタ一覧 ---
if [ -z "$CLUSTER" ]; then
  echo "# ECSクラスタ一覧（次: -c <クラスタ名> でサービス一覧）"
  awscli ecs list-clusters --query 'clusterArns[]' --output text | tr '\t' '\n' | sed 's|.*/||' | sort
  exit 0
fi

# --- 2) サービス一覧 ---
if [ -z "$SERVICE" ]; then
  echo "# クラスタ ${CLUSTER} のサービス一覧（次: -c ${CLUSTER} -s <サービス名> でALB/TG解決）"
  awscli ecs list-services --cluster "$CLUSTER" --query 'serviceArns[]' --output text | tr '\t' '\n' | sed 's|.*/||' | sort
  exit 0
fi

# --- 3) サービスに紐づく TG / ALB の解決 ---
echo "# ${CLUSTER} / ${SERVICE} のロードバランサ構成"
echo

TG_ARNS=$(awscli ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
  --query 'services[0].loadBalancers[].targetGroupArn' --output text | tr '\t' '\n')

if [ -z "$TG_ARNS" ] || [ "$TG_ARNS" = "None" ]; then
  echo "このサービスにはロードバランサが紐づいていません（loadBalancers が空）"
  exit 1
fi

# コンテナ名/ポートも添えて表示
awscli ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
  --query 'services[0].loadBalancers[].[containerName,containerPort,targetGroupArn]' --output text |
  while IFS=$'\t' read -r CNAME CPORT TGARN; do
    echo "## TG: ${TGARN##*:targetgroup/}  (container: ${CNAME}:${CPORT})"
  done
echo

FIRST=1
for TGARN in $TG_ARNS; do
  TG_SUFFIX="targetgroup/${TGARN##*:targetgroup/}"
  LB_ARN=$(awscli elbv2 describe-target-groups --target-group-arns "$TGARN" \
    --query 'TargetGroups[0].LoadBalancerArns[0]' --output text)
  if [ "$LB_ARN" = "None" ] || [ -z "$LB_ARN" ]; then
    echo "# 注意: ${TG_SUFFIX} はどのLBにも未接続（B/Gの待機側TGの可能性）"
    echo
    continue
  fi
  LB_SUFFIX="${LB_ARN##*:loadbalancer/}"

  if [ "$FIRST" = "1" ]; then
    echo "# ecs-sizing-metrics.sh にそのまま貼る値:"
  else
    echo "# 別のTG/LBペア（B/G構成の場合、ALBリスナーが現在向いている側を使う）:"
  fi
  echo "CLUSTER=\"${CLUSTER}\""
  echo "SERVICE=\"${SERVICE}\""
  echo "ALB=\"${LB_SUFFIX}\""
  echo "TG_ECS=\"${TG_SUFFIX}\""
  echo
  FIRST=0
done

echo "# 検算: 上記TGにトラフィックが来ているか（直近3時間のRequestCount合計）"
echo "#   aws elbv2 の値が0なら、B/Gのもう片方のTGが現用です"
for TGARN in $TG_ARNS; do
  TG_SUFFIX="targetgroup/${TGARN##*:targetgroup/}"
  LB_ARN=$(awscli elbv2 describe-target-groups --target-group-arns "$TGARN" \
    --query 'TargetGroups[0].LoadBalancerArns[0]' --output text)
  [ "$LB_ARN" = "None" ] || [ -z "$LB_ARN" ] && continue
  LB_SUFFIX="${LB_ARN##*:loadbalancer/}"
  SUM=$(awscli cloudwatch get-metric-statistics --namespace AWS/ApplicationELB \
    --metric-name RequestCount \
    --dimensions Name=TargetGroup,Value="$TG_SUFFIX" Name=LoadBalancer,Value="$LB_SUFFIX" \
    --start-time "$(date -u -d '3 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-3H +%Y-%m-%dT%H:%M:%SZ)" \
    --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --period 10800 --statistics Sum \
    --query 'Datapoints[0].Sum' --output text)
  echo "  ${TG_SUFFIX}: ${SUM} req"
done
