# Morphix 数据库表结构设计

## 1. 文档目标

这份文档是在以下几份设计基础上继续下钻：

- `report-原型驱动需求理解与初步架构建议.md`
- `design-总控编排层详细设计.md`
- `design-总控编排时序与状态图.md`
- `design-核心数据模型设计.md`

目标不是把所有实现细节一次性写死，而是先产出一份**可实施、可落库、可继续演进**的数据库表结构基线，重点回答：

1. MVP 阶段到底先建哪些表
2. 每张核心表建议有哪些字段与类型
3. 主外键、唯一约束、索引和状态字段应该怎么收口
4. 哪些表未来会变成大表，需要提前考虑分区与归档

---

## 2. 数据库选型建议

## 2.1 主存储：PostgreSQL

建议主数据库采用 **PostgreSQL**，原因很直接：

- 关系建模能力强，适合项目、Bot、Workflow、会话、运行态等复杂关联
- 事务能力成熟，适合总控编排层的状态推进与审计留痕
- JSONB 支持足够好，适合承载图结构快照、策略配置、节点输入输出快照
- 后续可扩展分区、只读副本、逻辑复制和 `pgvector`

## 2.2 辅助存储

- **Redis**：会话热状态缓存、幂等键、短窗口消息合并、分布式锁
- **对象存储**：图片、语音、视频、文件
- **向量检索**：初期可 `pgvector`，后续按压力考虑独立向量库

## 2.3 为什么不建议核心业务长期停留在 SQLite

SQLite 可以支撑原型期，但对于 Morphix 这类场景，后续会遇到：

- 并发写入受限
- 会话状态与运行态竞争明显
- 大表归档与分区能力不足
- 审计、回放、运营任务、设备回执一起进来后，单文件数据库很快吃不消

所以：

- **本地原型可以 SQLite**
- **正式架构基线应按 PostgreSQL 设计**

---

## 3. 建表总原则

## 3.1 所有核心业务表默认带 `project_id`

除了极少数全局字典表，以下领域表都建议带 `project_id`：

- Bot / Workflow
- Channel / Device
- Conversation / CRM
- Campaign / SOP
- Run / Audit / Agent Invocation / Policy Decision

这是租户隔离、索引设计、缓存命名空间和后续分区策略的基础。

## 3.2 状态字段强枚举，不要自由文本

重点对象：

- `conversation.status`
- `session_runtime.session_state`
- `workflow_run.status`
- `device_command.status`
- `campaign_task.status`

建议统一：
- 数据库存 `varchar(32)` 或 `smallint + code map`
- 服务层强校验
- 状态流转受状态机控制

## 3.3 关系靠列，灵活靠 JSONB

适合 JSONB 的：
- 工作流图结构
- 节点输入输出快照
- 策略参数
- 审计上下文

不适合 JSONB 的：
- 高频过滤字段
- 关键关系字段
- 唯一约束字段

## 3.4 大表和热表要分开思考

- `conversation` 是业务容器表
- `session_runtime` 是热写状态表
- `message` 是大事实表
- `node_execution`、`agent_invocation`、`audit_log` 是高增长观测表

别把这些角色混在一起。

---

## 4. 命名与通用字段规范

## 4.1 主键建议

建议统一使用：
- `char(26)` 存 ULID

原因：
- 可排序
- 分布式生成友好
- 日志可读性比 UUID 略好

如果团队已有统一 UUID 规范，也可以坚持 UUID，不是生死线；关键是**全局统一**。

## 4.2 通用字段建议

大多数业务表建议带：

- `id char(26) primary key`
- `project_id char(26) not null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

按需再加：

- `created_by char(26)`
- `updated_by char(26)`
- `deleted_at timestamptz`
- `status varchar(32)`
- `remark text`

## 4.3 审计风格建议

对于关键状态对象，建议加：
- `version int not null default 1` 用于乐观锁
- 或在服务层使用 `updated_at` + compare-and-swap 方案

特别是：
- `session_runtime`
- `workflow_run`
- `device_command`

---

## 5. MVP 核心表结构设计

以下是建议的第一批核心表。

---

## 5.1 `project`

### 用途
项目/租户边界。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 项目ID |
| name | varchar(128) | not null | 项目名称 |
| code | varchar(64) | not null unique | 项目标识码 |
| status | varchar(32) | not null | active/paused/archived |
| owner_user_id | char(26) | null | 项目负责人 |
| default_timezone | varchar(64) | not null default 'Asia/Shanghai' | 默认时区 |
| default_locale | varchar(32) | not null default 'zh-CN' | 默认语言 |
| plan_tier | varchar(32) | not null default 'standard' | 套餐档位 |
| token_budget_daily | numeric(18,4) | null | 每日预算 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 索引建议
- `uk_project_code(code)`
- `idx_project_status(status)`

---

## 5.2 `bot`

### 用途
面向业务交付的机器人定义。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | Bot ID |
| project_id | char(26) | not null FK | 所属项目 |
| name | varchar(128) | not null | 名称 |
| code | varchar(64) | not null | 项目内编码 |
| status | varchar(32) | not null | draft/active/paused/archived |
| description | text | null | 描述 |
| persona_summary | text | null | 角色摘要 |
| default_workflow_version_id | char(26) | null FK | 默认工作流版本 |
| default_model_profile | varchar(32) | null | economy/standard/premium |
| knowledge_strategy | varchar(32) | null | default/strict/hybrid |
| risk_policy_profile_id | char(26) | null | 风险策略配置 |
| handoff_policy_profile_id | char(26) | null | 转人工策略 |
| interrupt_policy | varchar(32) | not null default 'MERGE_WINDOW' | 中断策略 |
| created_by | char(26) | null | 创建人 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `unique(project_id, code)`
- `default_workflow_version_id` 必须指向已发布版本

### 索引建议
- `idx_bot_project_status(project_id, status)`
- `idx_bot_project_workflow(project_id, default_workflow_version_id)`

---

## 5.3 `workflow`

### 用途
工作流逻辑身份，不直接执行。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | Workflow ID |
| project_id | char(26) | not null FK | 所属项目 |
| name | varchar(128) | not null | 名称 |
| code | varchar(64) | not null | 项目内编码 |
| category | varchar(32) | null | chat/campaign/tool/subflow |
| status | varchar(32) | not null | active/paused/archived |
| latest_published_version_id | char(26) | null FK | 最新发布版本 |
| created_by | char(26) | null | 创建人 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `unique(project_id, code)`

### 索引建议
- `idx_workflow_project_status(project_id, status)`

---

## 5.4 `workflow_version`

### 用途
可执行的工作流发布版本。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 版本ID |
| project_id | char(26) | not null FK | 所属项目 |
| workflow_id | char(26) | not null FK | 工作流ID |
| version_no | int | not null | 版本号 |
| status | varchar(32) | not null | published/deprecated/rolled_back |
| graph_schema_json | jsonb | not null | 图结构快照 |
| input_schema_json | jsonb | null | 输入定义 |
| output_schema_json | jsonb | null | 输出定义 |
| default_runtime_policy_json | jsonb | null | 默认运行时策略 |
| published_by | char(26) | null | 发布人 |
| published_at | timestamptz | not null | 发布时间 |
| source_draft_id | char(26) | null | 来源草稿 |
| checksum | varchar(128) | not null | 内容校验值 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `unique(workflow_id, version_no)`
- 发布后禁止原地修改 `graph_schema_json`

### 索引建议
- `idx_workflow_version_project_workflow(project_id, workflow_id)`
- `idx_workflow_version_status(project_id, status)`

---

## 5.5 `channel_account`

### 用途
真实业务渠道账号。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 渠道账号ID |
| project_id | char(26) | not null FK | 所属项目 |
| channel_type | varchar(32) | not null | wechat/wecom/whatsapp/... |
| account_uid | varchar(128) | not null | 渠道原生账号标识 |
| display_name | varchar(128) | null | 展示名 |
| account_status | varchar(32) | not null | active/offline/banned/paused |
| hosting_mode | varchar(32) | not null default 'bot_default' | 托管模式 |
| default_bot_id | char(26) | null FK | 默认Bot |
| bound_device_id | char(26) | null FK | 当前绑定设备 |
| last_sync_at | timestamptz | null | 最近同步时间 |
| risk_level | varchar(32) | null | low/medium/high |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `unique(project_id, channel_type, account_uid)`

### 索引建议
- `idx_channel_account_project_status(project_id, account_status)`
- `idx_channel_account_project_bot(project_id, default_bot_id)`
- `idx_channel_account_device(bound_device_id)`

---

## 5.6 `device`

### 用途
边缘执行节点。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 设备ID |
| project_id | char(26) | not null FK | 所属项目 |
| device_code | varchar(64) | not null unique | 设备编码 |
| device_type | varchar(32) | not null | android_phone/emulator/other |
| brand | varchar(64) | null | 品牌 |
| model | varchar(64) | null | 型号 |
| os_version | varchar(64) | null | 系统版本 |
| app_version | varchar(64) | null | App版本 |
| status | varchar(32) | not null | online/offline/degraded/retired |
| network_status | varchar(32) | null | wifi/4g/5g/offline |
| last_heartbeat_at | timestamptz | null | 最近心跳 |
| risk_status | varchar(32) | null | normal/warn/frozen |
| owner_team | varchar(64) | null | 所属团队 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 索引建议
- `idx_device_project_status(project_id, status)`
- `idx_device_last_heartbeat(last_heartbeat_at)`

---

## 5.7 `conversation`

### 用途
会话身份容器。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 会话ID |
| project_id | char(26) | not null FK | 所属项目 |
| channel_account_id | char(26) | not null FK | 渠道账号 |
| conversation_type | varchar(16) | not null | direct/group |
| contact_id | char(26) | null FK | 单聊联系人 |
| group_chat_id | char(26) | null FK | 群聊对象 |
| subject | varchar(256) | null | 会话标题 |
| status | varchar(32) | not null | open/muted/archived/blocked |
| current_owner_type | varchar(16) | not null default 'ai' | ai/human/system |
| last_message_at | timestamptz | null | 最近消息时间 |
| last_inbound_message_at | timestamptz | null | 最近入站 |
| last_outbound_message_at | timestamptz | null | 最近出站 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `check((conversation_type='direct' and contact_id is not null and group_chat_id is null) or (conversation_type='group' and group_chat_id is not null))`

### 索引建议
- `idx_conversation_project_account_time(project_id, channel_account_id, last_message_at desc)`
- `idx_conversation_project_contact(project_id, contact_id)`
- `idx_conversation_project_group(project_id, group_chat_id)`

---

## 5.8 `session_runtime`

### 用途
会话当前热运行态，强并发核心表。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 运行态ID |
| project_id | char(26) | not null FK | 所属项目 |
| conversation_id | char(26) | not null unique FK | 会话ID |
| channel_account_id | char(26) | not null FK | 渠道账号 |
| current_bot_id | char(26) | null FK | 当前Bot |
| current_workflow_version_id | char(26) | null FK | 当前工作流版本 |
| hosting_status | varchar(32) | not null | enabled/paused/disabled |
| session_state | varchar(32) | not null | IDLE/AUTO_HOSTING/... |
| active_run_id | char(26) | null FK | 当前运行实例 |
| waiting_node_id | varchar(128) | null | 等待节点ID |
| handoff_status | varchar(32) | not null default 'none' | none/requested/active/returning |
| interrupt_policy | varchar(32) | not null | DROP_NEW/INTERRUPT_AND_REPLAN/... |
| last_policy_decision_id | char(26) | null FK | 最近策略决策 |
| last_message_seq | bigint | null | 最近消息序号 |
| runtime_context_digest | varchar(128) | null | 当前上下文摘要 |
| locked_until | timestamptz | null | 分布式抢锁保护 |
| version | int | not null default 1 | 乐观锁版本 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `conversation_id` 唯一
- 任一会话只允许一个活跃运行态

### 索引建议
- `idx_session_runtime_project_state(project_id, session_state)`
- `idx_session_runtime_project_bot(project_id, current_bot_id)`
- `idx_session_runtime_project_run(project_id, active_run_id)`
- `idx_session_runtime_locked_until(locked_until)`

### 特别说明
这张表必须支持高频更新，尽量保持“短、平、热”。

---

## 5.9 `message`

### 用途
消息事实表，大表。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 消息ID |
| project_id | char(26) | not null FK | 所属项目 |
| conversation_id | char(26) | not null FK | 会话ID |
| channel_account_id | char(26) | not null FK | 渠道账号 |
| direction | varchar(16) | not null | inbound/outbound/system |
| sender_type | varchar(16) | not null | customer/ai/human/device/system |
| message_type | varchar(32) | not null | text/image/file/voice/card/event |
| content_text | text | null | 纯文本内容 |
| content_payload_json | jsonb | null | 富媒体载荷 |
| seq_no | bigint | not null | 会话内序号 |
| source_message_id | varchar(128) | null | 渠道原生消息ID |
| reply_to_message_id | char(26) | null FK | 回复链 |
| sent_at | timestamptz | null | 发送时间 |
| received_at | timestamptz | null | 接收时间 |
| created_at | timestamptz | not null | 落库时间 |

### 约束建议
- `unique(project_id, conversation_id, seq_no)`
- `unique(project_id, channel_account_id, source_message_id)` 可按渠道情况决定是否启用部分唯一索引

### 索引建议
- `idx_message_project_conversation_time(project_id, conversation_id, created_at desc)`
- `idx_message_project_source(project_id, source_message_id)`
- `idx_message_project_account_time(project_id, channel_account_id, created_at desc)`

### 分区建议
优先候选：
- 按月分区 `created_at`
- 或按月分区 + 项目逻辑路由

---

## 5.10 `workflow_run`

### 用途
一次工作流执行实例。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | Run ID |
| project_id | char(26) | not null FK | 所属项目 |
| workflow_version_id | char(26) | not null FK | 工作流版本 |
| conversation_id | char(26) | null FK | 关联会话 |
| session_runtime_id | char(26) | null FK | 关联运行态 |
| trigger_type | varchar(32) | not null | message/campaign/manual/schedule/system |
| trigger_ref_id | char(26) | null | 触发来源对象 |
| status | varchar(32) | not null | pending/running/waiting/interrupted/failed/cancelled/completed |
| started_at | timestamptz | null | 开始时间 |
| ended_at | timestamptz | null | 结束时间 |
| parent_run_id | char(26) | null FK | 父运行 |
| root_run_id | char(26) | null | 根运行 |
| current_node_id | varchar(128) | null | 当前节点 |
| input_context_json | jsonb | null | 输入快照 |
| output_context_json | jsonb | null | 输出快照 |
| result_summary | text | null | 结果摘要 |
| error_code | varchar(64) | null | 错误码 |
| error_message | text | null | 错误信息 |
| retry_count | int | not null default 0 | 重试次数 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 索引建议
- `idx_workflow_run_project_conversation(project_id, conversation_id, started_at desc)`
- `idx_workflow_run_project_status(project_id, status, started_at desc)`
- `idx_workflow_run_root(root_run_id)`
- `idx_workflow_run_workflow_version(workflow_version_id, started_at desc)`

---

## 5.11 `node_execution`

### 用途
节点级执行记录。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 记录ID |
| project_id | char(26) | not null FK | 所属项目 |
| run_id | char(26) | not null FK | 运行实例 |
| node_id | varchar(128) | not null | 节点ID |
| node_type | varchar(64) | not null | 节点类型 |
| node_name | varchar(128) | null | 节点名称 |
| status | varchar(32) | not null | success/failed/waiting/skipped |
| attempt_no | int | not null default 1 | 尝试次数 |
| input_snapshot_json | jsonb | null | 输入快照 |
| output_snapshot_json | jsonb | null | 输出快照 |
| started_at | timestamptz | null | 开始时间 |
| ended_at | timestamptz | null | 结束时间 |
| duration_ms | int | null | 耗时 |
| error_code | varchar(64) | null | 错误码 |
| error_message | text | null | 错误信息 |
| executor_type | varchar(32) | not null | runtime/agent/device/async_worker |
| created_at | timestamptz | not null | 创建时间 |

### 约束建议
- `unique(run_id, node_id, attempt_no)`

### 索引建议
- `idx_node_execution_run(run_id, started_at)`
- `idx_node_execution_project_type(project_id, node_type, created_at desc)`

### 分区建议
这是高增长表，建议尽早预留时间分区能力。

---

## 5.12 `agent_invocation`

### 用途
Agent 调用留痕表。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 调用ID |
| project_id | char(26) | not null FK | 所属项目 |
| run_id | char(26) | not null FK | 运行实例 |
| node_execution_id | char(26) | null FK | 节点执行 |
| conversation_id | char(26) | null FK | 会话ID |
| agent_type | varchar(64) | not null | sales_progress/qa/supervisor/... |
| agent_name | varchar(128) | null | 名称 |
| invocation_role | varchar(32) | not null | online/offline/campaign/supervisor |
| model_provider | varchar(64) | not null | openai/anthropic/... |
| model_name | varchar(128) | not null | 模型名 |
| prompt_template_version | varchar(64) | null | Prompt版本 |
| input_digest | varchar(128) | null | 输入摘要 |
| output_digest | varchar(128) | null | 输出摘要 |
| structured_output_json | jsonb | null | 结构化结果 |
| confidence | numeric(5,4) | null | 置信度 |
| status | varchar(32) | not null | success/failed/timeout/fallback |
| latency_ms | int | null | 耗时 |
| prompt_tokens | int | null | 输入tokens |
| completion_tokens | int | null | 输出tokens |
| estimated_cost | numeric(18,6) | null | 预估成本 |
| started_at | timestamptz | null | 开始时间 |
| ended_at | timestamptz | null | 结束时间 |
| created_at | timestamptz | not null | 创建时间 |

### 索引建议
- `idx_agent_invocation_run(run_id)`
- `idx_agent_invocation_project_agent(project_id, agent_type, started_at desc)`
- `idx_agent_invocation_project_model(project_id, model_name, started_at desc)`

---

## 5.13 `policy_decision`

### 用途
策略决策与可解释性基石表。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 决策ID |
| project_id | char(26) | not null FK | 所属项目 |
| conversation_id | char(26) | null FK | 会话ID |
| session_runtime_id | char(26) | null FK | 运行态 |
| run_id | char(26) | null FK | 运行实例 |
| decision_type | varchar(64) | not null | bot_select/interrupt/... |
| decision_source | varchar(32) | not null | rule/model/supervisor/human/fallback |
| decision_payload_json | jsonb | not null | 决策结果 |
| reason_codes_json | jsonb | null | 原因代码数组 |
| confidence | numeric(5,4) | null | 置信度 |
| policy_version | varchar(64) | null | 策略版本 |
| created_at | timestamptz | not null | 决策时间 |

### 索引建议
- `idx_policy_decision_project_conversation(project_id, conversation_id, created_at desc)`
- `idx_policy_decision_project_type(project_id, decision_type, created_at desc)`

### 说明
高风险设备动作前，应能追溯到对应 `policy_decision`。

---

## 5.14 `device_command`

### 用途
下发到设备的执行命令。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 命令ID |
| project_id | char(26) | not null FK | 所属项目 |
| device_id | char(26) | not null FK | 设备ID |
| channel_account_id | char(26) | not null FK | 渠道账号 |
| conversation_id | char(26) | null FK | 会话ID |
| run_id | char(26) | null FK | 运行实例 |
| command_type | varchar(64) | not null | send_message/sync_contacts/... |
| payload_json | jsonb | not null | 命令载荷 |
| idempotency_key | varchar(128) | not null | 幂等键 |
| status | varchar(32) | not null | pending/sent/acked/done/failed/expired/cancelled |
| issued_at | timestamptz | not null | 发令时间 |
| sent_at | timestamptz | null | 发送时间 |
| ack_at | timestamptz | null | ACK时间 |
| done_at | timestamptz | null | 完成时间 |
| failure_reason | text | null | 失败原因 |
| retry_count | int | not null default 0 | 重试次数 |
| policy_decision_id | char(26) | null FK | 关联策略决策 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `unique(idempotency_key)`

### 索引建议
- `idx_device_command_project_device_status(project_id, device_id, status, issued_at desc)`
- `idx_device_command_project_run(project_id, run_id)`
- `idx_device_command_project_conversation(project_id, conversation_id, issued_at desc)`

---

## 5.15 `contact`

### 用途
联系人/外部客户基础身份表。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 联系人ID |
| project_id | char(26) | not null FK | 所属项目 |
| external_uid | varchar(128) | not null | 外部ID |
| display_name | varchar(128) | null | 展示名 |
| avatar_url | text | null | 头像 |
| gender | varchar(16) | null | 性别 |
| source_channel_type | varchar(32) | not null | 来源渠道 |
| source_account_id | char(26) | null FK | 来源账号 |
| first_seen_at | timestamptz | null | 首次出现 |
| last_seen_at | timestamptz | null | 最近出现 |
| status | varchar(32) | not null default 'active' | active/hidden/blocked |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- MVP 可先 `unique(project_id, source_channel_type, external_uid)`

### 索引建议
- `idx_contact_project_name(project_id, display_name)`
- `idx_contact_project_account(project_id, source_account_id)`

---

## 5.16 `customer_profile`

### 用途
长期客户画像聚合对象。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 客户画像ID |
| project_id | char(26) | not null FK | 所属项目 |
| primary_contact_id | char(26) | null FK | 主联系人 |
| customer_code | varchar(64) | not null | 客户编码 |
| stage_code | varchar(64) | null | 阶段编码 |
| owner_user_id | char(26) | null | 负责人 |
| source_type | varchar(32) | null | import/manual/agent/merged |
| summary_text | text | null | AI总结 |
| preference_json | jsonb | null | 偏好信息 |
| risk_flag_json | jsonb | null | 风险标记 |
| last_ai_summary_at | timestamptz | null | 最近总结时间 |
| created_at | timestamptz | not null | 创建时间 |
| updated_at | timestamptz | not null | 更新时间 |

### 约束建议
- `unique(project_id, customer_code)`

### 索引建议
- `idx_customer_profile_project_stage(project_id, stage_code)`
- `idx_customer_profile_project_owner(project_id, owner_user_id)`

---

## 5.17 `customer_tag`

### 用途
客户标签结果表。

### 建议结构

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | char(26) | PK | 标签记录ID |
| project_id | char(26) | not null FK | 所属项目 |
| customer_profile_id | char(26) | not null FK | 客户画像 |
| tag_code | varchar(64) | not null | 标签编码 |
| tag_value | varchar(256) | null | 标签值 |
| source_type | varchar(32) | not null | rule/agent/human/import |
| source_ref_id | char(26) | null | 来源对象 |
| confidence | numeric(5,4) | null | 置信度 |
| effective_at | timestamptz | null | 生效时间 |
| expired_at | timestamptz | null | 失效时间 |
| created_at | timestamptz | not null | 创建时间 |

### 索引建议
- `idx_customer_tag_project_customer(project_id, customer_profile_id)`
- `idx_customer_tag_project_tag(project_id, tag_code)`

---

## 6. 第二批增强表建议

MVP 跑通后，建议补以下表。

### 6.1 `group_chat`
用于群聊身份与元数据

### 6.2 `campaign`
运营活动定义

### 6.3 `campaign_task`
运营任务执行实例

### 6.4 `audit_log`
统一审计日志表

### 6.5 `debug_session`
调试运行与回放会话

### 6.6 `device_event`
设备上报的细粒度事件表

### 6.7 `bot_version`
Bot 配置版本化增强

### 6.8 `device_account_binding`
账号与设备绑定关系历史表

---

## 7. 外键策略建议

## 7.1 核心关系建议保留真实外键
MVP 阶段建议保留外键的表：

- `bot.project_id -> project.id`
- `workflow.project_id -> project.id`
- `workflow_version.workflow_id -> workflow.id`
- `conversation.channel_account_id -> channel_account.id`
- `session_runtime.conversation_id -> conversation.id`
- `workflow_run.workflow_version_id -> workflow_version.id`
- `node_execution.run_id -> workflow_run.id`
- `agent_invocation.run_id -> workflow_run.id`
- `device_command.device_id -> device.id`

原因：
- 模型还在快速收敛阶段
- 真实外键能尽早暴露设计错误

## 7.2 大表外键可做审慎取舍
像 `message.reply_to_message_id`、超大审计表等，后期可以根据性能做权衡。

原则是：
- **一致性优先于过早优化**
- 等量上来再做约束瘦身，不要一开始就全裸奔

---

## 8. 分区、归档与冷热分层建议

## 8.1 优先考虑分区的大表

- `message`
- `node_execution`
- `agent_invocation`
- `device_event`
- `audit_log`

## 8.2 推荐策略

### 方案 A：按时间分区（推荐起步）
例如：
- 月分区 `2026_07`
- 月分区 `2026_08`

适用：
- 写入量随时间增长
- 历史数据查询比例低
- 归档和冷热迁移清晰

### 方案 B：时间分区 + 项目路由
适合未来项目数量与流量差异较大时。

## 8.3 冷热分层建议

- 热数据：近 30~90 天消息与执行日志
- 温数据：近 6~12 个月
- 冷数据：归档到对象存储 / 数据仓 / 低频库

---

## 9. 索引总体策略

## 9.1 索引设计原则

- 优先围绕**最常见查询路径**建索引
- 复合索引遵循“过滤列在前，排序列在后”
- 热写表不要堆过多索引
- 大 JSONB 不要幻想 GIN 能兜底一切，先把结构化列设计好

## 9.2 MVP 重点查询路径

### 路径 1：会话列表
按项目、账号、最后消息时间排序

### 路径 2：会话详情
按 `conversation_id` 拉消息流水

### 路径 3：当前运行态
按 `conversation_id` 查 `session_runtime`

### 路径 4：运行调试
按 `run_id` 查 `workflow_run -> node_execution -> agent_invocation`

### 路径 5：设备执行监控
按 `device_id + status` 查未完成命令

### 路径 6：策略审计
按 `conversation_id` / `decision_type` 查 `policy_decision`

---

## 10. MVP 建表顺序建议

建议不要一次性把全部表都建满，按下面顺序更稳。

## 第一批：主骨架表
1. `project`
2. `bot`
3. `workflow`
4. `workflow_version`
5. `channel_account`
6. `device`
7. `conversation`
8. `session_runtime`

## 第二批：执行链路表
9. `message`
10. `workflow_run`
11. `node_execution`
12. `agent_invocation`
13. `policy_decision`
14. `device_command`

## 第三批：CRM 基础表
15. `contact`
16. `customer_profile`
17. `customer_tag`

## 第四批：增强治理表
18. `group_chat`
19. `campaign`
20. `campaign_task`
21. `audit_log`
22. `device_event`
23. `debug_session`

---

## 11. 几个关键权衡

## 11.1 `session_runtime` 是否缓存化而不落库？
不建议。

原因：
- 运行态不仅是缓存，也是恢复点
- 需要审计与抢锁依据
- Redis 可做加速，但不能替代主存储事实

## 11.2 `message` 是否拆文本表与载荷表？
MVP 阶段不必过早拆。

可先：
- `content_text`
- `content_payload_json`

后续如果语音、图片、富卡片极多，再做垂直拆分。

## 11.3 `agent_invocation` 是否保存完整 Prompt？
建议分层：
- 主表保摘要、版本、成本、结果
- 敏感的完整 Prompt / Completion 可选落明细表或日志仓

不建议默认把全部大文本都塞在主表里。

## 11.4 `policy_decision.reason_codes_json` 为什么要结构化？
因为后面你会统计：
- 哪类原因最常触发转人工
- 哪类原因最常导致中断
- 哪类风险规则拦截最多

如果只留自然语言，后面分析很难做。

---

## 12. 推荐的下一步输出

在这份表结构基线之上，最顺的下一步有两个：

1. **ER 图 / 领域关系图**
   - 让结构一眼能看懂
2. **接口设计文档**
   - 把会话、运行态、设备命令、回执、运营任务 API 全部落下来

如果要直接进入开发准备，我建议优先做：

- `database schema ER图`
- `接口设计-总控编排与会话运行时.md`

---

## 13. 最终结论

如果只保留一句话：

**Morphix 的数据库不是围绕“消息表”展开的，而是围绕 `Project -> Bot -> WorkflowVersion -> Conversation -> SessionRuntime -> WorkflowRun -> DeviceCommand / PolicyDecision / AgentInvocation` 这条主执行骨架展开的。**

这条骨架一旦立稳，后面的 CRM、运营任务、分析报表、灰度策略、设备治理，都只是往两侧长；
这条骨架如果一开始就歪了，后面再补什么都像在歪楼上加阳台。