# Morphix Control（控制面后端地基 · MVP）

Morphix 私域运营 AI 协同平台的控制面后端 MVP（FastAPI + SQLAlchemy 2.x + Pydantic v2 + SQLite）。
按 `openapi-morphix-unified.yaml` 统一契约实现控制面 / 运行时 / 设备接入三类接口，可被
`bruno/Morphix P0 主链路` 与 `postman/Morphix-P0` 联调集合直接跑通。

> 说明：本服务是**控制面后端地基**，不包含前端控制台与设备端 APP。LLM 多 Agent 调用在 MVP
> 中以**可插拔 stub**（确定性 mock 回复）实现，真实模型接入为 TODO。

## 技术栈

- Python 3.13（managed runtime）
- FastAPI 0.116 / Uvicorn / SQLAlchemy 2.0 / Pydantic 2.11
- SQLite（文件 `data/morphix.db`，启动自动建表 + 种子数据）

## 启动

```bash
# 1) 建本地 venv（Python 3.11，依赖已装好则跳过 pip install）
python3.11 -m venv .venv
./.venv/bin/pip install fastapi uvicorn sqlalchemy pydantic pyyaml httpx python-multipart pytest

# 2) 启动（从 morphix-control/ 目录）
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 健康检查
curl http://localhost:8000/api/health
```

环境变量（均可选，有默认值）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MORPHIX_DB` | `data/morphix.db` | SQLite 文件路径 |
| `MORPHIX_DEV` | `1` | Dev 模式：鉴权 stub 接受任意非空令牌 |
| `DEVICE_PROVISIONING_KEY` | `dev-provisioning-key` | 设备注册预配置密钥 |
| `TOKEN_TTL_SEC` | `2592000` | 设备令牌有效期（秒） |

## 接口面（对齐统一契约）

- **设备接入**：`POST /api/device/registrations`（签发 deviceToken）、`refresh-token`、`heartbeats`、
  `inbound-messages`、`contact-sync/batches`、`group-sync/batches`、`diagnostics/*`
- **设备回执**：`GET /api/device/commands/pending`、`.../{id}/ack|complete|fail`
- **运行时编排**：`POST /api/runtime/inbound-events/messages`、`GET .../{requestId}`、
  `POST /api/runtime/device-commands`
- **控制面**：会话查询/运行态/消息流水、人工接管与交还、工作流运行（创建/详情/节点轨迹/中断/恢复/取消）、决策与 Agent 调用审计
- **内部管理（contract-TBD）**：Project / Bot / WorkflowVersion CRUD + 发布
- **内部编排**：`/internal/policy-router/evaluate`、`/internal/agent-executor/invoke|supervisor`
- **鉴权引导（契约缺口补齐）**：`POST /api/auth/dev-bootstrap` 签发 control/runtime/internal/provisioning 令牌

统一响应封套：`{ requestId, success, data, error }`；错误码见 `ErrorObject.code` 枚举。

## 鉴权（MVP stub）

| Scheme | Header | MVP 行为 |
|---|---|---|
| DeviceProvisioningAuth | `X-Device-Provisioning-Key` | Dev 模式接受任意非空值 |
| RuntimeAuth | `X-Runtime-Token` | 任意非空 |
| DeviceAuth | `X-Device-Token` | 校验设备存在且未删除 |
| InternalServiceAuth | `X-Internal-Service-Token` | 任意非空 |
| ControlAuth | `Authorization: Bearer` / `X-Control-Token` | 控制面端点契约未要求鉴权 |

> 真实部署须替换为签名 JWT 校验（见 `app/core/security.py`）。

## 与 Bruno / Postman 联调

Bruno 集合根 `bruno/Morphix P0 主链路/bruno.json` 已含 `baseUrl=http://localhost:8000`、
`projectId=01JPROJECT`、`bindCode=BIND-20260712-8F2KQ`。后端种子已建好 `01JPROJECT` 项目与
已发布工作流 `wf_v1`，因此：

1. 启动本服务（端口 8000）。
2. 在 `bruno.json` 填写 `provisioningKey`（任意值，如 `dev-provisioning-key`）、
   `runtimeToken`/`internalToken`（任意值）。
3. Bruno 桌面端打开集合 → 选环境 → 按顺序运行；`deviceToken` 等由响应自动写入环境变量。

## 测试

```bash
VENV/bin/python -m pytest tests/test_smoke.py -q
```

覆盖 P0 主链路：设备注册/心跳/令牌刷新 → 入站消息编排 → 会话查询 → 命令拉取/ACK/complete
（含重复回执 no-op）→ 运行详情/节点轨迹/审计 → 人工接管/交还（接管期间停发）→ 内部端点
→ 重复消息幂等 → 鉴权反例。

## 已知缺口（来自设计阶段，已实现补齐/标注）

- ✅ 统一契约原本缺 Project/Bot/WorkflowVersion 管理接口 → 已在 `/api/control/...` 以 contract-TBD 实现。
- ✅ 契约未定义 token 签发端点 → 已实现 `/api/auth/dev-bootstrap`。
- ✅ 契约 403 FORBIDDEN 仅出现在枚举、未挂在写操作 → 管理类写操作已按 RBAC 返回 403。
- ⏳ 真实多 Agent LLM、Policy Router 学习、设备端 APP 为后续迭代。
