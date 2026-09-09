#!/bin/bash
# DB とロールだけ作る。テーブルは作らない（STEP 2 でライブ作成する）。
set -euo pipefail

psql -v ON_ERROR_STOP=1 -U postgres -d aicase \
  -v rw_pw="$AICASE_RW_PASSWORD" -v ro_pw="$AICASE_RO_PASSWORD" <<'SQL'
CREATE ROLE aicase_rw LOGIN PASSWORD :'rw_pw';
CREATE ROLE aicase_ro LOGIN PASSWORD :'ro_pw';

GRANT CONNECT ON DATABASE aicase TO aicase_rw, aicase_ro;
GRANT USAGE, CREATE ON SCHEMA public TO aicase_rw;
GRANT USAGE ON SCHEMA public TO aicase_ro;

-- aicase_rw が作るテーブルを aicase_ro が読めるようにする
ALTER DEFAULT PRIVILEGES FOR ROLE aicase_rw IN SCHEMA public
  GRANT SELECT ON TABLES TO aicase_ro;
SQL
