# 河马大健康客户机器人 — live 跑通 + 前端新增

## 一、8000 运行时引擎 live 跑通

启动：`cd morphix-control && MORPHIX_DEV=1 MORPHIX_DB=$(pwd)/data/morphix.db .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（后台启动**不要**加 `&`）。

触发：`POST /api/control/workflow-runs`
```json
{ "project_id":"prj_hema_funnel", "conversation_id":"conv_hema_live_1",
  "workflow_version_id":"wfv_prj_hema_funnel_1", "trigger_type":"manual" }
```

结果：run 状态 `completed`，节点链
`n_start → n_stage_router(switch) → n_s1_agent → n_s1_gate(policy/compliance) → n_s1_send → n_end`，
落 1 条 `device_commands`(send_message, pending)，内容为步骤 1 耳部健康询问话术：
> 您好，我是河马健康的线上健康顾问。接下来我会先了解一下您耳部的基本情况，方便药师团队评估。全程不推销、不报价，您可以放心沟通。

→ 证明此前 seed 的 `WorkflowVersion.definition` 能真实驱动引擎端到端执行（含 A8 合规守门在 send 之前）。

## 二、前端新增「河马大健康客户」机器人（botId = `hema`）

### 前端 mock 注册（与 野风秋/梵芙尼 同模式）
- `src/pages/Bots/BotDetail.tsx` — `MOCK_BOTS.hema`
- `src/pages/Bots/Logs.tsx` — `ROBOTS` 增加名称 + `河马大健康客户 → hema` 的 botId 映射
- `src/types/operations.ts` — `HOSTING_ACTION_OPTIONS` 增加 `hema`
- `src/pages/Operations/components/FlowConfigPanel.tsx` — 3 处 `<option>`
- `src/pages/DataPanel/DataPanel.tsx` — 筛选器 option
- `src/pages/Bots/__tests__/Logs.test.tsx` — 断言同步更新

### 2181 后端 bots 表（活跃库 = 仓库根 `database/morphix_mvp.db`）
- 直接 INSERT `hema`(online)，验证：`GET /api/bots` 现 7 个含 hema；`/api/channels/accounts/available-bots` 渠道默认机器人也含 hema
- `project/backend/app/schema.py` 的 `dashboard_seed()` 已加入 hema，便于重建

### 校验
- `npm run typecheck` → 0 error
- `vitest run src/pages/Bots/__tests__/Logs.test.tsx` → 9/9 通过

## 三、范围说明
前端 bot 的 `workflow` 字段仅为展示文案。当前架构：前端/2181 后端走控制面，运行时引擎独立在 8000，二者尚无转发链路——hema 漏斗的实际执行仍由 8000 引擎按 `WorkflowVersion` 跑，未与 2181 的 `hema` bot 记录关联。如需「前端选 bot → 引擎跑对应流程」，需新增 2181→8000 的 workflow 触发转发。
