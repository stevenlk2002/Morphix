#!/bin/bash
# ============================================================================
# Morphix 前后端一键启动（花生壳仅用于后端回调，前端走本地/局域网）
#
# 用途：
#   花生壳仅用于【后端回调】——让 iPad 协议实时回调经公网可达本机；
#   前端走本地/局域网访问，不再经花生壳暴露。
#   1) 重启前端 (Vite, 端口 5183，本地/局域网访问，不经花生壳)
#   2) 重启后端 (FastAPI, 端口 2181) 并注入 IPAD_CALLBACK_PUBLIC_URL，
#      使 iPad 协议实时回调能经公网转发回本机，从而 1:1 私聊消息能收进来
#
# 前提（需在花生壳 GUI 客户端完成）：
#   - 后端映射：内网 127.0.0.1:2181，类型必须 HTTPS 动态端口
#               （iPad 协议 SetCallbackUrl 要求 https + 有效证书域名）
#   建好后端映射后，花生壳会分配一个「动态端口」，例如 48721
#
# 用法：
#   PEANUT_HTTPS_PORT=48721 bash start_with_peanuthsell.sh
#   （如需换域名：PEANUT_DOMAIN=xxx.vicp.fun PEANUT_HTTPS_PORT=xxxx bash ...）
# ============================================================================
set -e

ROOT="/Users/stevenmac/Desktop/工作目录/Morphix"
NODE="/Users/stevenmac/.workbuddy/binaries/node/versions/22.22.2/bin/npm"

PEANUT_DOMAIN="${PEANUT_DOMAIN:-123wx9061na45.vicp.fun}"
PEANUT_HTTPS_PORT="${PEANUT_HTTPS_PORT:?❌ 请设置花生壳【后端 HTTPS 动态端口】，例如: PEANUT_HTTPS_PORT=48721 bash $0}"

CALLBACK_URL="https://${PEANUT_DOMAIN}:${PEANUT_HTTPS_PORT}/wxwork/callback"
echo ">>> iPad 回调地址将设为: $CALLBACK_URL"

# ---------- 前端 ----------
# 前端在本地 5183 运行，局域网用 http://192.168.2.111:5183 访问，不经花生壳暴露
echo ">>> 重启前端 (5183) ..."
pkill -f "node_modules/.bin/vite" 2>/dev/null || true
sleep 1
cd "$ROOT"
nohup "$NODE" run dev > /tmp/morphix-frontend-5183.log 2>&1 &

# ---------- 后端 ----------
echo ">>> 重启后端 (2181) 并注入回调 URL ..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2
cd "$ROOT/project/backend"
IPAD_CALLBACK_PUBLIC_URL="$CALLBACK_URL" \
MORPHIX_DEV=1 \
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 2181 > /tmp/morphix-backend-2181.log 2>&1 &

# ---------- 健康检查 ----------
sleep 6
echo ">>> 健康检查:"
curl -s -o /dev/null -w "   后端 2181 -> HTTP %{http_code}\n" --max-time 5 http://127.0.0.1:2181/api/health || echo "   后端未就绪(看日志 /tmp/morphix-backend-2181.log)"
curl -s -o /dev/null -w "   前端 5183 -> HTTP %{http_code}\n" --max-time 5 http://localhost:5183 || echo "   前端未就绪(看日志 /tmp/morphix-frontend-5183.log)"
echo ">>> 完成。前端本地/局域网访问: http://localhost:5183 或 http://192.168.2.111:5183（不经花生壳）；后端回调走花生壳公网地址"
