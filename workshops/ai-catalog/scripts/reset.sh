#!/bin/bash
# リハーサル前に環境を初期状態へ戻す。
#   1. aicase DB の public スキーマのテーブルを全部落とす
#   2. 当日AIが作る4部品のディレクトリを消す
#   3. catalog/ を事前準備分（catalog/SEED.txt に列挙）だけに戻す
#   4. Jira AICASE の Issue を全件削除する（scripts/jira_reset.py がある場合）
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

echo "[1/4] drop tables in aicase.public"
docker exec -i aicase-db psql -v ON_ERROR_STOP=1 -U postgres -d aicase <<'SQL'
DO $$ DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END $$;
SQL

echo "[2/4] remove generated components"
rm -rf .claude/skills .cursor/skills app sync mcp

echo "[3/4] remove non-seed files from catalog/ (keep those listed in catalog/SEED.txt)"
for f in catalog/*.json; do
  grep -qx "$(basename "$f")" catalog/SEED.txt || { echo "  rm $f"; rm -f "$f"; }
done

echo "[4/4] reset Jira"
if [ -f scripts/jira_reset.py ]; then
  uv run python scripts/jira_reset.py
else
  echo "  (scripts/jira_reset.py not found; skipped)"
fi
echo "done"
