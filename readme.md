# Morphix

Morphix 是一个面向多项目、多渠道、多账号、多 Agent 协同的私域运营 AI 协同平台。

## 工程收敛状态（2025-07-18）

本仓库已完成工程收敛，统一为「后端 canonical + 前端 console + 契约参考实现」三件套：

| 目录 | 角色 | 状态 |
| --- | --- | --- |
| `project/backend` | **Canonical 后端**：资源域（裸 SQL：`bots/channels/knowledge/materials/meta/sops/tags/workflows`）+ 契约域（`app/contract`：33 条统一契约路径、Success/Error 封套、5 套鉴权方案）。单进程、双库隔离（`database/morphix_mvp.db` 资源域 / `database/morphix_contract.db` 契约域）。 | 主栈 |
| `morphix-console`（仓库根） | **Canonical 前端控制台**：React 18 + Vite 5 + TypeScript（JS→TS 迁移自 `project/frontend`）+ react-router-dom@6 + lucide-react。已包含 prototype 独有页（渠道账号托管 / 联系人 / 会话托管 / 客户列表 / 数据概览 / 渠道分布）。 | 主栈 |
| `morphix-control` | **统一契约合规参考实现**：保留不改动，其契约测试（`tests/test_smoke.py`）保持绿灯（3 passed），作为契约权威参考。 | 参考（保留） |
| `retired/frontend`、`retired/prototype` | 原 `project/frontend`（JS 前端）与 `prototype`（高保真静态原型）。能力已并入 `morphix-console`，在此归档退役。 | 已退役（归档） |

> 收敛决策（用户拍板）：把 `morphix-control` 的 33 条统一契约路径 + 封套 + 5 套安全方案整体移植进 `project/backend`，使其成为唯一 canonical 后端；`project/frontend` 的 React 代码迁入根级 `morphix-console` 并 JS→TS，`prototype` 独有页面抽入 console 后退役；`morphix-control` 降级为「统一契约合规参考实现」，保留并跑绿其契约测试，不删除。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18 + Vite 5 + TypeScript + react-router-dom@6 + lucide-react |
| 后端 | FastAPI + Pydantic + SQLAlchemy 2.x（契约域）+ 裸 SQL（资源域）+ Alembic |
| 数据库 | MVP 使用 SQLite：`database/morphix_mvp.db`（资源域）、`database/morphix_contract.db`（契约域） |

## 服务端口

| 服务 | 端口 | 地址 |
| --- | --- | --- |
| 前端 Vite Dev | 5173 | http://localhost:5173（代理 `/api` → 127.0.0.1:2181） |
| 后端 FastAPI | 2181 | http://localhost:2181 |

> 端口已按项目规则分配：前端使用 1001-2000 区间，后端使用 2001-3000 区间。

## 启动方式

### 后端（canonical）

```bash
cd project/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 2181
```

启动后资源域与契约域数据表自动初始化（双库隔离）。后端 CORS 已放行 5173。

### 前端（console）

```bash
# 仓库根（package.json name=morphix-console）
npm install
npm run dev        # 开发（5173，代理到 2181）
npm run build      # tsc --noEmit && vite build
npm run typecheck  # tsc --noEmit
```

### 契约参考实现（morphix-control，保留）

```bash
cd morphix-control
./.venv/bin/python -m pytest morphix-control/tests/test_smoke.py -q   # 保持 3 passed
```

## 关键约定

- **Canonical 会话/运行以契约路径为准**：`/api/control/conversations`、`/api/control/workflow-runs` 等。控制台（morphix-console）只调用契约路径。
- **资源域遗留端点**：`/api/conversations`、`/api/workflows/runs` 保留但标注 **Deprecated**（代码注释 + 本文档），P2 清理。
- **封套**：契约域统一返回 `{ requestId, success, data, error }`（camelCase 线格式 + snake_case Python 访问）；前端 `src/api/client.ts` 封套感知，自动解包 `data`。资源域保持裸字典。
- **分页**：契约列表用 `{ items, page, pageSize, total }`；消息流用游标 `{ hasMore, nextBeforeSeq }`。

## 当前开发范围

按收敛后主栈：`morphix-console` 应用壳层、首页概览、AI 机器人（训练/知识/素材）、渠道会话（消息流/运行轨迹/审计决策/接管）、渠道账号托管、渠道联系人、渠道会话托管、客户管理、数据概览、渠道分布。
