# 河马编排（Hema Workflow）使用指南

> 适用对象：`prj_hema_funnel`（11 步成交漏斗，42 节点）与 `prj_hema_kefu`（河马客服能力库，31 节点）
> 运行时引擎：morphix-control，端口 **8000**
> 最后验证：2026-08-04 live 跑通（入站消息 → 自动建会话 → 跑漏斗 → 落 send_message 指令）

---

## 0. 先搞清楚三套系统（别混）

| 系统 | 端口 | 职责 | 河马相关内容 |
|---|---|---|---|
| 编辑器后端 / 前端控制台 | 2181 | 画流程图、看 bot 列表、渠道配置 | `河马大健康客户` bot 在此登记（bots 表） |
| **运行时引擎** | **8000** | **真正执行工作流、发 device_command** | `prj_hema_funnel` / `prj_hema_kefu` 的 published 版本在此 |
| 转换器脚本 | — | 编辑器格式 → 运行时 `WorkflowVersion.definition` | `scripts/build_runtime_workflow.py` |

**关键认知**：前端「河马大健康客户」机器人目前只是 2181 的**登记条目**（名字+展示用 workflow 字段），
**并没有自动调用 8000 引擎**。要让它"活"起来，需要 2181 在收到客户消息时转发给 8000（见第 5 节）。

---

## 1. 启动运行时引擎（必须先做）

```bash
cd /Users/stevenmac/Desktop/工作目录/Morphix/morphix-control
MORPHIX_DEV=1 MORPHIX_DB="$(pwd)/data/morphix.db" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

⚠️ **后台启动不要用 `&`**：`run_in_background` 托管的进程会在 shell 退出时被回收，curl 会得 502。
用工具/终端自带的后台机制拉起即可。

健康检查：
```bash
curl -s -m 5 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/health   # 期望 200
```

---

## 2. 方式 A：入站消息触发（= 真正的"结合"路径）

这是生产形态——一条客户消息进来，引擎自动选 published 工作流并跑完。

```bash
curl -s -X POST http://127.0.0.1:8000/api/runtime/inbound-events/messages \
  -H "Content-Type: application/json" \
  -H "X-Runtime-Token: dev" \          # dev 模式接受任意非空 token
  -d '{
    "project_id": "prj_hema_funnel",   # 漏斗走这个；客服能力库用 prj_hema_kefu
    "channel_account_id": "ca_hema_demo",
    "device_id": "dev_hema_1",
    "conversation_type": "direct",
    "source_conversation_id": "wxconv_zhang_001",
    "source_message_id": "wxmsg_唯一不重复值",   # 幂等键，重复会返回已存在会话
    "contact": {
      "external_uid": "wxuser_zhang",
      "display_name": "河马会员-张女士",
      "tags": ["stage:s1"]              # funnel 用 stage:* 标签驱动"一次推进一步"
    },
    "message": {
      "message_type": "text",
      "content_text": "你好，我想了解一下耳部护理",
      "sent_at": "2026-08-04T12:00:00Z"
    }
  }'
```

返回 `accepted:true` 即成功。引擎会：
1. 自动建 `Conversation`（`current_workflow_version_id` = 该项目最新 published 版本）
2. 建 `SessionRuntime`
3. 立即 `_step_nodes` 走图，到 `send_message` 节点落一条 `device_commands`（状态 pending）
4. 发出 `workflow_selection` 策略决策 + 审计日志

**已验证证据**（2026-08-04）：该调用发出后，DB 中出现
`device_commands[send_message/pending] = "您好，我是河马健康的线上健康顾问…全程不推销、不报价…"`

查发出的消息：
```bash
cd morphix-control
.venv/bin/python - <<'PY'
import sqlite3, json
con = sqlite3.connect('data/morphix.db'); con.row_factory = sqlite3.Row
for r in con.execute("SELECT command_type,status,payload FROM device_commands ORDER BY id DESC LIMIT 5"):
    p = r['payload'] if isinstance(r['payload'],dict) else json.loads(r['payload'] or '{}')
    print(r['command_type'], r['status'], '::', p.get('text') or p.get('content_text'))
con.close()
PY
```

---

## 3. 方式 B：手动触发（仅测试用）

需要先有一个 `conversation`（注意 `conversations` 表 `subject`/`created_at` 在 DB 层 NOT NULL，裸 INSERT 要带齐）：

```sql
INSERT INTO conversations
 (id, project_id, channel_account_id, conversation_type, subject, owner_type,
  handoff_status, contact, created_at, updated_at)
VALUES ('conv_test_1','prj_hema_funnel','ca_hema_demo','direct','测试会话','ai','none',
 '{"display_name":"测试"}','2026-08-04T12:00:00Z','2026-08-04T12:00:00Z');
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/control/workflow-runs \
  -H "Content-Type: application/json" -H "X-Control-Token: dev" \
  -d '{"project_id":"prj_hema_funnel","conversation_id":"conv_test_1",
       "workflow_version_id":"wfv_prj_hema_funnel_1","trigger_type":"manual"}'
```

---

## 4. 修改 SOP 后重新同步

流程图的"真相"在编辑器（2181），运行时（8000）只是它的编译产物。
改完流程图后重新生成并落库：

```bash
cd /Users/stevenmac/Desktop/工作目录/Morphix
python scripts/build_runtime_workflow.py --seed     # 生成 docs/hema-sop-runtime-*.json 并落库为 published
```

转换器自带三重自检（结构不变量 / 守门不变量 / A8 合规），任一不过会非零退出。
跑测试回归：
```bash
cd morphix-control && MORPHIX_DEV=1 .venv/bin/python -m pytest \
  tests/test_runtime_workflow_defs.py tests/test_timer_switch.py -q
```

---

## 5. 怎么和「河马大健康客户」前端 bot 结合（待接的桥）

现状：2181 的 `河马大健康客户` bot 与 8000 引擎**尚无转发链路**。
引擎侧入口已就绪（`/api/runtime/inbound-events/messages`），缺的是 2181 → 8000 的调用。

**要做的一件事**：在 2181 后端收到 iPad / 渠道入站消息、且命中 `河马大健康客户` bot 时，
按下面映射转发给引擎：

| 前端 bot | 引擎 project_id | 说明 |
|---|---|---|
| 河马大健康客户（成交） | `prj_hema_funnel` | 11 步漏斗，stage 标签驱动 |
| 河马大健康客户（客服） | `prj_hema_kefu` | intent 路由能力库 |

转发时把 2181 的 `source_message_id` 透传为幂等键，避免重复建会话。

> 注：引擎内部的 `Bot` 概念是独立的（引擎 DB 的 `bots` 表，与 2181 的 `bots` 表不是同一份）。
> 引擎跑流程只认 `project_id` 下最新 published 的 `WorkflowVersion`，不需要 bot 记录存在。

---

## 6. ✅ agent 节点已接真实 LLM（DeepSeek / OpenAI 兼容）

`app/services/agents.py` 的 `invoke_agent()` 现在会调用真实 LLM（默认 DeepSeek），
**仅在未配置 key 或调用失败时回落到罐头话术**，保证流水线永不崩。

**配置（环境变量，dev 模式即可）：**
```bash
export MORPHIX_AI_API_KEY="sk-xxxx"                  # 必填，否则自动回落 stub
export MORPHIX_AI_BASE_URL="https://api.deepseek.com/v1"   # 默认即此
export MORPHIX_AI_MODEL="deepseek-chat"             # 默认即此（也可换 gpt-4o / qwen 等）
# 可选：MORPHIX_AI_TEMPERATURE=0.7  MORPHIX_AI_TIMEOUT=30
```
- 调用走 OpenAI 兼容 `/v1/chat/completions`（与 2181 后端 `llm_model_configs` 约定一致）。
- system prompt = agent 类型角色定义 + 节点自带 `prompt`（SOP 指令）+ qa 类附合规提醒；
  user prompt = 客户最新消息 + 最近 6 条对话历史 + 客户标签（由 `orchestration._step_nodes` 从 `Message` 表捞出）。
- `agent_invocations` 表会记录 `model_name`（真模型名 / `stub`）、`confidence`、`executor_type`(llm/stub)。

**`{{agentReply}}` 模板变量（让客户收到 AI 生成的话）：**
- 默认 `send_message` 节点仍发 SOP 预写文本（合规可控）。
- 想让某节点改用 agent 的真实回复，在 `scripts/build_runtime_workflow.py` 的 `n_send(..., use_agent_reply=True)` 即可（占位符 `{{agentReply}}`）。
- 漏斗里 **s3/s6/s7/s9** 已翻成 `{{agentReply}}`（对话型 qa 阶段）；s1/s4/s8 保留预写 SOP（对应测试精确断言）。
- **关键不变量**：`{{agentReply}}` 的替换在 agent 节点执行后立即 in-place 改写下游 send 节点的文本，确保 **A8 合规守门读到的就是真实 LLM 文本**——否则守门只会看到字面占位符、合规校验形同虚设。

---

## 速查

| 想做 | 命令 / 端点 |
|---|---|
| 起引擎 | `uvicorn app.main:app --port 8000`（带 MORPHIX_DEV=1 / MORPHIX_DB） |
| 健康 | `GET /api/health` |
| 客户消息触发 | `POST /api/runtime/inbound-events/messages`（带 `X-Runtime-Token`） |
| 手动触发 | `POST /api/control/workflow-runs`（带 `X-Control-Token`） |
| 看发出的消息 | 查 `device_commands` 表（command_type=send_message） |
| 看 agent 调用 | 查 `agent_invocations` 表（model_name=stub 表示未配 key 回落） |
| 启用真 LLM | 设 `MORPHIX_AI_API_KEY`（+ 可选 BASE_URL/MODEL）后重启引擎 |
| 重新同步 SOP | `python scripts/build_runtime_workflow.py --seed` |
| 测试回归 | `pytest tests/test_llm_client.py tests/test_runtime_workflow_defs.py tests/test_timer_switch.py` |
