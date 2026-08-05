# 河马客服 A8 守门 · 运行时最小闭环点亮指南

> 目标：把「用户消息 → A4 异议应答(agent) → A8 合规守门(policy) → 发送(send_message)」这条单分支闭环，真正在 Morphix 运行时引擎里跑通一次。
> 配套工件：`docs/hema-sop-runtime-workflow.json`（运行时格式的最小工作流定义）。

## 0. 架构前提（必读）

运行时引擎在 **`morphix-control`**（独立控制面后端，默认端口 8000），不在 `project/backend`（2181）。

引擎 `morphix-control/app/services/orchestration.py` 的 `_step_nodes`：
- 遍历 `WorkflowVersion.definition` 的 `nodes/edges`，从 `start`（或无入边的节点）出发；
- 默认跟 **`nexts[0]`**（即 edges 里 source 命中的**第一条** target）；但 **`switch` 节点**会在本跳覆盖 `nexts[0]`：按 `data.config.switchOn`（`tag` / `last_text`）+ `data.config.cases[{equals, target}]` 选边，命中则 `target_id = case.target`（否则回落 `config.default`），并记录 `switch_branch` AuditLog → 实现**条件分叉**（A0 路由 / 人工在环分支可用）。
- 节点 `type` 认：`start` / `agent`（或 `data.agentType`）/ `device_command`·`send_message`·`send_media`（或 `data.commandType`）/ `policy` / `timer` / `switch` / `end`；
- **`timer` 节点**（养育序列延时触达）：取 `data.config.delaySeconds` + `topic`，把"待触发任务"写入 `AuditLog(event_type="timer_scheduled", detail={scheduled_at, delay_seconds, topic, downstream})`，引擎**同步继续**走到下游（真正的异步触发由外部定时器服务实现，MVP 仅记录意图、可查询）。查询端点：`GET /api/control/conversations/{cid}/timers` 与 `GET /api/control/workflow-runs/{rid}/timers`（支持 `status=pending|fired` 过滤）。
- agent 调用 `agent_svc.invoke_agent(..., model_profile="stub")` —— **MVP 是确定性 stub，不调真实模型**；
- **policy（守门）节点现已真正生效**：当 `data.gate == "compliance"` 时，引擎取下游 `send_*` 节点的 `payload.text`（取不到则回落到上游 agent 输出 `last_text`），调用 `policy_svc.evaluate_compliance()` 做 B1–B8 红线判定：
  - 命中红线 → `publish_policy_decision(decision_type="compliance_gate", decision="blocked", reason_codes=[...])`，**停止推进、不执行下游 send 节点、不落地 DeviceCommand**，run 标记 `completed` + `result_summary="compliance blocked: Bx"`；
  - 未命中 → `decision="allowed"`，正常走 `nexts[0]` 进入 send 节点发出 DeviceCommand。
  - 非 compliance 的 policy 节点仍维持原行为（`decision="continue"` 无条件放行），不影响既有 seed 流程。

> 红线判定逻辑在 `app/services/policy.py::evaluate_compliance()`，按 SOP 的 A8 编辑器节点 B1–B8 实现（确定性规则，非 LLM）。可经内部端点 `POST /internal/policy-router/compliance-check`（`X-Internal-Service-Token`，body `{"text": "..."}`）单独验证。

## 1. 启动运行时服务

```bash
cd /Users/stevenmac/Desktop/工作目录/Morphix/morphix-control
MORPHIX_DEV=1 ./.venv/bin/python -m uvicorn app.main:app --port 8000 --host 127.0.0.1
# 探活
curl http://127.0.0.1:8000/api/health   # -> 200
```
- 依赖已在 `.venv`（Python 3.11）装好；SQLite `data/morphix.db` 启动自动建表+种子。
- `MORPHIX_DEV=1` 下鉴权 stub 接受**任意非空 token**。

## 2. 鉴权与请求体格式（踩坑汇总）

| 面 | 前缀 | 鉴权头 | body 形态 |
|---|---|---|---|
| Management / Control | `/api/control` | `X-Control-Token: <任意>` + `X-Role: owner` | **`{"req": {...}}` 包裹**；写操作还多一个 body 字段 `allowed`（来自 `require_role` 依赖），可传 `"allowed":["owner"]` |
| Runtime 入站 | `/api/runtime` | `X-Runtime-Token: <任意>` | **裸模型**（不包裹，字段用 camelCase） |

- **坑**：`publish` 端点（`POST /api/control/projects/{pid}/workflow-versions/{vid}/publish`）**没有** `req` 业务参数，body 里只有 `allowed` 一个字段 → 必须发**裸数组** `["owner"]`，而不是 `{"allowed":["owner"]}`，否则报 `Input should be a valid set`。
- `policy-decisions` 的 `decisionType` 枚举已扩展，含 `compliance_gate`（A8 守门结果），可正常回读。

- 所有 DTO 走 `app.core.envelope.DTO`（`alias_generator=to_camel`）：**多词字段必须用 camelCase**（`projectId`/`channelAccountId`/`deviceId`/`conversationType`/`sourceConversationId`/`sourceMessageId`；嵌套 `contact.externalUid`/`displayName`/`tags`，`message.messageType`/`contentText`/`sentAt`）。
- `WorkflowVersionCreate` 的 `projectId` **路径和 body 都要给**。
- 入站事件（`POST /api/runtime/inbound-events/messages`）成功返回 `202`，含 `conversationId` / `sessionRuntimeId` / `accepted`；**响应里没有 `runId`**，需再 `GET /api/control/conversations/{conv}/runtime` 取 `activeRunId`。

## 3. 点亮步骤（用 curl / 任意 HTTP 客户端）

```bash
B=http://127.0.0.1:8000
H='-H "Content-Type: application/json" -H "X-Control-Token: dev" -H "X-Runtime-Token: dev"'

# (1) 建 Project  —— 注意 {"req":{...}}
PID=$(curl -s $H -X POST $B/api/control/projects \
  -d '{"req":{"name":"河马客服A8最小闭环POC","description":"start->agent->policy->send"}}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")

# (2) 建 WorkflowVersion(draft) —— definition 取自 hema-sop-runtime-workflow.json 的 nodes/edges
curl -s $H -X POST $B/api/control/projects/$PID/workflow-versions \
  -d "{\"req\":{\"projectId\":\"$PID\",\"name\":\"hema_a8_minloop\",\"definition\":$(cat hema-sop-runtime-workflow.json | python3 -c 'import sys,json;print(json.dumps(json.load(sys.stdin)["nodes"]))' ...)}}"  # 见下附注
#      ↑ 实际请整段传 {"nodes":[...],"edges":[...]}，用脚本拼装更稳（见 artifact 生成器思路）

# (3) 发布
curl -s $H -X POST $B/api/control/projects/$PID/workflow-versions/$VID/publish
#      -> {"data":{"status":"published"}}

# (4) 建 Bot（可选，引擎默认取 project 下首个 bot；不影响 inbound 跑通）
curl -s $H -X POST $B/api/control/projects/$PID/bots \
  -d "{\"req\":{\"projectId\":\"$PID\",\"name\":\"hema_bot\"}}"

# (5) 触发一次入站消息  —— 裸模型 + camelCase，无 {"req"} 包裹！
NOW=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
curl -s $H -X POST $B/api/runtime/inbound-events/messages -H "X-Runtime-Token: dev" \
  -d "{\"projectId\":\"$PID\",\"channelAccountId\":\"ca_demo\",\"deviceId\":\"dev_demo\",\"conversationType\":\"direct\",\"sourceConversationId\":\"sc1\",\"sourceMessageId\":\"sm1\",\"contact\":{\"externalUid\":\"u1\",\"displayName\":\"测试客户\",\"tags\":[\"A\"]},\"message\":{\"messageType\":\"text\",\"contentText\":\"我原来在三甲医院都治疗过，怎么还是没效果？\",\"sentAt\":\"$NOW\"}}"
#      -> 202 {"data":{"conversationId":"conv_xxx","accepted":true,"dispatchMode":"sync_orchestrate"}}

# (6) 取 runId 并核对执行轨迹
RID=$(curl -s $H $B/api/control/conversations/conv_xxx/runtime | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['activeRunId'])")
curl -s $H $B/api/control/workflow-runs/$RID | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('status',d['status'])"
curl -s $H $B/api/control/workflow-runs/$RID/node-executions   # start/agent/policy/send 均 completed
curl -s $H $B/api/control/workflow-runs/$RID/policy-decisions   # 含 bot_selection:proactive_send / rule:device_command_emitted
```

> 附注：步骤 (2) 的 definition 拼装较繁琐，建议用一段 Python（`import json; wf=json.load(open("hema-sop-runtime-workflow.json")); body={"req":{"projectId":pid,"name":"hema_a8_minloop","definition":{"nodes":wf["nodes"],"edges":wf["edges"]}}}`) 再 `urllib` 发出，避免 shell 转义出错。

## 4. 成功判据（已实测满足）

- **放行（合规）路径**：`workflow-runs/{rid}` → `status: completed`；`node-executions` = `start / a4(agent) / a8(policy) / send` 全部 `completed`；`policy-decisions` 含 `compliance_gate: allowed` 且 `send` 节点落地了 `DeviceCommand`。
- **拦截（红线）路径**：入站文本命中 B1–B8 → `node-executions` = `start / a4(agent) / a8(policy)`（**不含 send**）；`policy-decisions` 含 `compliance_gate: blocked`（reasonCodes 如 `rule:compliance_B2`）；`run.result_summary="compliance blocked: Bx"`；**无 DeviceCommand 落地**。

> 自动化验证脚本：`morphix-control/scripts/e2e_compliance_gate_live.py`（对运行中 8000 服务跑 block/allow 双用例并断言）。

## 5. 已知限制 / 下一步

1. **✅ 守门已真正拦截（已实现）**：`policy` 节点 `gate=="compliance"` 时按 B1–B8 评估下游待发文本，命中即停发。若要把"拦截后转人工/RAG 重生成"做成完整回路，需接 `internal.py /policy-router/evaluate`（真实策略路由）并把 block 分支导向 `interruptBefore`/人工节点，而非仅停发。
2. **agent 是 stub**：返回确定性 mock，不调 LLM；接真实模型需在 `agents.py` 替换 `invoke_agent` 实现并注入模型配置。
3. **条件分叉已解锁（Step6）**：`switch` 节点支持按标签/上文做条件分叉（A0 路由、人工在环分支可用）；`timer` 节点支持养育序列的延时触达意图记录（待外部定时器服务真实触发）。编辑器里 `hema_kefu` 的完整多分支画布（A0 路由、人工在环、RAG）现已可在引擎侧跑通拓扑；`multiJudge` 节点类型仍未在引擎实现（仍按 agent stub 兜底）。
4. **✅ 双格式已打通（转换器）**：编辑器格式（`hema_kefu`，2181 已入库）与运行时格式仍是**两套 schema**，但现在由 `scripts/build_runtime_workflow.py` 自动转换并落库为 `WorkflowVersion.definition`，详见下一节。

## 6. 编辑器 → 运行时 定义同步

转换器：`scripts/build_runtime_workflow.py`

```bash
morphix-control/.venv/bin/python3.11 scripts/build_runtime_workflow.py          # 生成 + 三重自检
morphix-control/.venv/bin/python3.11 scripts/build_runtime_workflow.py --seed   # 再落库为 published
```

### 为什么不能机械搬运（三条语义鸿沟）

| # | 差异 | 直接搬运的后果 | 转换器的处理 |
|---|---|---|---|
| 1 | 节点类型：编辑器 `type:"customNode"` + `data.nodeType`；运行时 `type` 即真实类型 | 引擎认不出，全部落 unknown 空步 | `NODE_TYPE_MAP` 映射；`multiJudge` 折叠进 policy gate |
| 2 | **A8 守门位置**：编辑器挂在 `msgOutput` **之后**（旁路 `n_msg` 才是真出口）；引擎要求 `policy(compliance)` 在 send **之前**（它检查下游 send 的 `payload.text`） | **合规守门被完全跳过**——静默失效，最危险 | 拓扑重排成 `… → policy(compliance) → send_message → …`；并有结构不变量校验 |
| 3 | **拓扑形态**：`hema_kefu` 是 `n_user` 扇出 9 Agent + 2 KB 的能力库；引擎只走 `nexts[0]` | 只跑 `n_a0` 就结束 | A0 → `switch`(intent 标签) → 各能力分支 |
| 4 | 会话节奏：引擎一次 run 走到底（guard 256） | 11 步漏斗一次 inbound 连发 11 条 | `stage:*` 标签驱动的 `switch`，一次只推进一步 |

### 产物

| 文件 | project_id | 路由 | 规模 |
|---|---|---|---|
| `docs/hema-sop-runtime-kefu.json` | `prj_hema_kefu` | intent（8 个能力分支） | 31 节点 / 37 边 |
| `docs/hema-sop-runtime-funnel.json` | `prj_hema_funnel` | stage（11 步，一次一步） | 42 节点 / 51 边 |

驱动方式：把 `contact.tags` 里放 `stage:s4` / `intent:百问百答` 之类标签，引擎 `switch` 即选中对应分支；无标签走 `default`。

### 三重自检（转换器内置，不过不落库）

1. **结构校验**：无重复 id、无孤儿边；
2. **守门不变量**：每个 `send_message` 的**所有**前驱都必须是 `policy(gate=compliance)`——杜绝绕过；
3. **A8 合规自检**：所有 send 文本过一遍 `policy.evaluate_compliance`，BLOCK 即退出码 2（`n_s8_send` 纯价格披露为 B8 **WARN 放行**，符合 Step3 价格豁免预期）。

### 验证

`morphix-control/tests/test_runtime_workflow_defs.py`（12 例）加载上述 JSON，用真实 `orchestration._step_nodes` 走图，断言：阶段/意图路由正确、一次 inbound 只发 1 条、守门 BLOCK 时不落 `DeviceCommand`、B8 价格 WARN 放行、timer 分支记录 `timer_scheduled` 且不外发。

> ⚠️ **该测试抓到过一个真 bug**：引擎 `switch` 原用**子串匹配**，`stage:s1` 会抢走 `stage:s10` 的流量（前缀撞车 → 会话静默误路由）。已改为「标签精确匹配 / 自由文本包含匹配」，可用 case 级 `match: "exact"|"contains"` 覆盖；回归用例见 `tests/test_timer_switch.py::test_switch_tag_exact_match_avoids_prefix_collision`。同时修了 `conversation.contact` 为 NULL 时 `.get()` 崩溃。
