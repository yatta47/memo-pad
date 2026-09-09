#!/bin/bash
# Postgres MCP Pro を .env の DATABASE_URL で起動する（Claude Code / Cursor 共用）
# postgres-mcp は MCP Python SDK 1.x 前提なので mcp<2 を固定する
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
exec uvx --with "mcp<2" postgres-mcp --access-mode="${POSTGRES_MCP_ACCESS_MODE:-unrestricted}" "$DATABASE_URL"
