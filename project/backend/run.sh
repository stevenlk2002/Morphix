#!/usr/bin/env bash
# Morphix 后端启动脚本
# 监听 2181，与前端 vite.config.js 的代理目标（127.0.0.1:2181）对齐。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${MORPHIX_HOST:-127.0.0.1}"
PORT="${MORPHIX_PORT:-2181}"
WORKERS="${MORPHIX_WORKERS:-1}"

echo ">>> 启动 Morphix 后端: http://${HOST}:${PORT}  (API 前缀 /api)"
echo ">>> 数据库: ${MORPHIX_DB_PATH:-database/morphix_mvp.db}"
echo ">>> 健康检查: http://${HOST}:${PORT}/api/health"

exec python3 -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS" \
  --reload
