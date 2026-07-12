# Morphix 核心数据模型设计

## 1. 文档目标

这份文档是在《`design-总控编排层详细设计.md`》和《`design-总控编排时序与状态图.md`》基础上，继续把系统的核心数据对象定下来。

目标不是一次性把所有表都设计完，而是先把 **真正决定系统骨架的关键实体、关系边界、约束和演进策略** 明确下来。

一句话说，本设计要回答：

**Morphix 里到底有哪些核心对象，它们分别归谁管、如何关联、哪些状态必须拆开、哪些字段必须从第一天就设计对。**

---

## 2. 设计原则

## 2.1 先按领域边界建模，不按页面建模
不要因为原型里有“AI机器人页”“渠道会话页”“客户管理页”就直接按页面建表。

真正应该按领域拆：
- Project / Tenant
- Bot Studio
- Workflow Orchestration
- Channel & Device
- Conversation & CRM
- Campaign / SOP
- Insight & Governance

## 2.2 会话态、运行态、客户态必须分离
这是整个系统里最重要的原则之一。

- **会话态**：当前这轮对话谁在控制、卡在哪一步
- **运行态**：当前 WorkflowRun 执行到了哪一节点
- **客户态**：长期标签、阶段、画像、偏好

这三者揉在一个表里，后面一定炸。

## 2.3 Bot 与 WorkflowVersion 解耦
Bot 是业务交付对象，WorkflowVersion 是流程执行对象。

- Bot 可切换到新 WorkflowVersion
- Workflow 可发布多个版本
- 草稿修改不应直接影响线上 Bot

## 2.4 渠道账号与设备分离
一个账号不一定永远绑定同一台设备，一台设备也可能经历重装、换绑、退役。

所以：
- `channel_account` 管业务账号
- `device` 管物理执行节点
- `device_binding` 或绑定字段管两者关系

## 2.5 所有核心业务表默认带 `project_id`
Morphix 的“项目”本质上是一级租户。

建议从第一天起就把以下原则做死：
- 核心业务数据都带 `project_id`
- 查询、索引、缓存命名空间、审计范围都以 `project_id` 为核心隔离维度

---

## 3. 建议的领域上下文与核心实体

## 3.1 Tenant / Project Context
核心实体：
- `project`
- `project_member`
- `project_role_binding`
- `project_setting`

## 3.2 Bot Studio Context
核心实体：
- `bot`
- `bot_version`（可选，若 Bot 配置变化频繁建议引入）
- `bot_workflow_binding`
- `bot_knowledge_binding`
- `bot_channel_policy`

## 3.3 Workflow Orchestration Context
核心实体：
- `workflow`
- `workflow_version`
- `workflow_draft`
- `workflow_node_definition`
- `workflow_edge_definition`
- `workflow_run`
- `node_execution`
- `debug_session`

## 3.4 Channel & Device Context
核心实体：
- `channel_account`
- `device`
- `device_account_binding`
- `device_command`
- `device_event`
- `channel_capability_profile`

## 3.5 Conversation & CRM Context
核心实体：
- `conversation`
- `session_runtime`
- `message`
- `contact`
- `group_chat`
- `customer_profile`
- `customer_tag`
- `customer_stage`
- `contact_channel_relation`

## 3.6 Campaign / SOP Context
核心实体：
- `campaign`
- `campaign_task`
- `campaign_audience_snapshot`
- `campaign_execution`
- `campaign_touch_record`

## 3.7 Insight & Governance Context
核心实体：
- `policy_decision`
- `agent_invocation`
- `audit_log`
- `metric_fact_*`
- `alert_event`

---

## 4. 核心实体详细设计

下面重点定那些“骨架级”对象。

---

## 4.1 `project`

### 职责
表示一个业务项目/租户边界。

### 建议字段
- `id`
- `name`
- `code`
- `status`（active / paused / archived）
- `owner_user_id`
- `default_timezone`
- `default_locale`
- `plan_tier`
- `token_budget_daily`
- `created_at`
- `updated_at`

### 关键约束
- `code` 唯一
- 删除项目建议只做软删除或归档
- 所有核心业务对象必须能追溯到 `project_id`

---

## 4.2 `bot`

### 职责
表示一个面向业务交付的机器人定义。

### 建议字段
- `id`
- `project_id`
- `name`
- `code`
- `status`（draft / active / paused / archived）
- `description`
- `persona_summary`
- `default_workflow_version_id`
- `default_model_profile`
- `knowledge_strategy`
- `risk_policy_profile_id`
- `handoff_policy_profile_id`
- `interrupt_policy`
- `created_by`
- `created_at`
- `updated_at`

### 关键约束
- `default_workflow_version_id` 必须指向已发布版本，不可指向 draft
- `project_id + code` 唯一
- Bot 不能直接内嵌大段工作流 JSON，当版本开始增多时会越来越乱

### 设计建议
如果后续 Bot 配置变更很多，可考虑加 `bot_version`：
- 方便审计
- 支持灰度
- 支持回滚

---

## 4.3 `workflow`

### 职责
表示一个工作流逻辑的“逻辑身份”，不直接代表具体可执行版本。

### 建议字段
- `id`
- `project_id`
- `name`
- `code`
- `category`
- `status`
- `latest_published_version_id`
- `created_by`
- `created_at`
- `updated_at`

### 关键约束
- `workflow` 是“壳”，`workflow_version` 才是执行体
- 一个 `workflow` 可以有多个版本、一个草稿

---

## 4.4 `workflow_version`

### 职责
表示一个可执行的工作流发布版本。

### 建议字段
- `id`
- `project_id`
- `workflow_id`
- `version_no`
- `status`（published / deprecated / rolled_back）
- `graph_schema_json`
- `input_schema_json`
- `output_schema_json`
- `default_runtime_policy_json`
- `published_by`
- `published_at`
- `source_draft_id`
- `checksum`

### 关键约束
- `workflow_id + version_no` 唯一
- 发布后的 `graph_schema_json` 应视为不可变
- `checksum` 可用于防止发布污染和快速比对版本差异

### 为什么必须不可变
因为：
- Bot 引用的是某个确定版本
- Run 回放需要拿到当时的版本快照
- 调试和审计必须可重复

---

## 4.5 `conversation`

### 职责
表示一个渠道会话容器，是“与谁聊”的对象，不是“当前怎么跑”的对象。

### 建议字段
- `id`
- `project_id`
- `channel_account_id`
- `conversation_type`（direct / group）
- `contact_id`（单聊时）
- `group_chat_id`（群聊时）
- `subject`
- `status`（open / muted / archived / blocked）
- `current_owner_type`（ai / human / system）
- `last_message_at`
- `last_inbound_message_at`
- `last_outbound_message_at`
- `created_at`
- `updated_at`

### 关键约束
- 单聊：`contact_id` 必填，`group_chat_id` 为空
- 群聊：`group_chat_id` 必填，`contact_id` 可为空
- `conversation` 不直接存工作流运行细节，那是 `session_runtime` 的事

---

## 4.6 `session_runtime`

### 职责
表示某个会话当前的实时托管与控制状态，是总控编排层最关键的运行态对象之一。

### 建议字段
- `id`
- `project_id`
- `conversation_id`
- `channel_account_id`
- `current_bot_id`
- `current_workflow_version_id`
- `hosting_status`（enabled / paused / disabled）
- `session_state`（IDLE / AUTO_HOSTING / WAITING_USER / WAITING_TIMER / WAITING_DEVICE_ACK / HUMAN_HANDOFF / PAUSED_BY_POLICY / ERROR_REVIEW / CLOSED）
- `active_run_id`
- `waiting_node_id`
- `handoff_status`（none / requested / active / returning）
- `interrupt_policy`
- `last_policy_decision_id`
- `last_message_seq`
- `runtime_context_digest`
- `locked_until`
- `created_at`
- `updated_at`

### 关键约束
- `conversation_id` 唯一，一般一会话一运行态
- 任一时刻最多一个 `active_run_id`
- `session_state` 与 `handoff_status` 应可组合，但要限制非法组合

### 为什么它必须独立成表
因为它是：
- 高频读写对象
- 当前态对象
- 强并发对象
- 恢复与抢锁对象

把它跟会话主表混在一起，后面热写会拖累大量基础查询。

---

## 4.7 `workflow_run`

### 职责
表示一次工作流执行实例。

### 建议字段
- `id`
- `project_id`
- `workflow_version_id`
- `conversation_id`
- `session_runtime_id`
- `trigger_type`（message / campaign / manual / schedule / system）
- `trigger_ref_id`
- `status`（pending / running / waiting / interrupted / failed / cancelled / completed）
- `started_at`
- `ended_at`
- `parent_run_id`
- `root_run_id`
- `current_node_id`
- `input_context_json`
- `output_context_json`
- `result_summary`
- `error_code`
- `error_message`
- `retry_count`
- `created_at`
- `updated_at`

### 关键约束
- 支持子流程时，`parent_run_id` 必须保留
- `root_run_id` 用于整棵执行树聚合
- `status` 状态流转需受状态机约束

### 设计建议
`input_context_json` / `output_context_json` 不要无限膨胀：
- 大对象建议做快照表
- 热路径只保留摘要和关键上下文引用

---

## 4.8 `node_execution`

### 职责
表示单个节点的一次执行记录。

### 建议字段
- `id`
- `project_id`
- `run_id`
- `node_id`
- `node_type`
- `node_name`
- `status`
- `attempt_no`
- `input_snapshot_json`
- `output_snapshot_json`
- `started_at`
- `ended_at`
- `duration_ms`
- `error_code`
- `error_message`
- `executor_type`（runtime / agent / device / async_worker）

### 关键约束
- `run_id + node_id + attempt_no` 唯一
- 输入输出快照应可裁剪，避免日志爆炸

### 价值
这张表是：
- 调试回放基石
- 性能分析基石
- 节点级 SLA 基石

---

## 4.9 `agent_invocation`

### 职责
表示一次 Agent 调用记录。

### 建议字段
- `id`
- `project_id`
- `run_id`
- `node_execution_id`
- `conversation_id`
- `agent_type`
- `agent_name`
- `invocation_role`（online / offline / campaign / supervisor）
- `model_provider`
- `model_name`
- `prompt_template_version`
- `input_digest`
- `output_digest`
- `structured_output_json`
- `confidence`
- `status`
- `latency_ms`
- `prompt_tokens`
- `completion_tokens`
- `estimated_cost`
- `started_at`
- `ended_at`

### 关键约束
- `structured_output_json` 应按 Agent 类型保持稳定结构
- 对 Supervisor Agent 要特别标记来源和采纳结果

### 为什么要独立存
因为后面你一定会问：
- 哪类 Agent 最贵
- 哪类 Agent 最慢
- 哪类 Agent 经常误判
- 哪类 Agent 触发了最多人工接管

不单列，这些问题后面都很难答。

---

## 4.10 `policy_decision`

### 职责
记录总控层的重要策略判断，是审计与可解释性的核心表。

### 建议字段
- `id`
- `project_id`
- `conversation_id`
- `session_runtime_id`
- `run_id`
- `decision_type`（bot_select / workflow_select / handoff / interrupt / supervisor / model_select / risk_block / campaign_allow 等）
- `decision_source`（rule / model / supervisor / human / fallback）
- `decision_payload_json`
- `reason_codes_json`
- `confidence`
- `policy_version`
- `created_at`

### 关键约束
- 高风险动作前必须留有对应 `policy_decision`
- `reason_codes_json` 最好采用枚举代码，而不是只有自然语言描述

### 示例 reason code
- `CUSTOMER_HIGH_VALUE`
- `DEVICE_OFFLINE`
- `RISK_LIMIT_REACHED`
- `NEW_MESSAGE_INTERRUPTS_OLD_RUN`
- `SUPERVISOR_ESCALATION_REQUIRED`

---

## 4.11 `device`

### 职责
表示边缘设备执行节点。

### 建议字段
- `id`
- `project_id`（若设备池跨项目可为空或挂到组织层，但当前建议先保留项目归属）
- `device_code`
- `device_type`（android_phone / emulator / other）
- `brand`
- `model`
- `os_version`
- `app_version`
- `status`（online / offline / degraded / retired）
- `network_status`
- `last_heartbeat_at`
- `risk_status`
- `owner_team`
- `created_at`
- `updated_at`

### 关键约束
- `device_code` 唯一
- `last_heartbeat_at` 应支撑在线判定和健康检查

---

## 4.12 `channel_account`

### 职责
表示真实业务渠道账号，例如某个微信号、企业微信号、WhatsApp 号。

### 建议字段
- `id`
- `project_id`
- `channel_type`
- `account_uid`
- `display_name`
- `account_status`
- `hosting_mode`
- `default_bot_id`
- `bound_device_id`
- `last_sync_at`
- `risk_level`
- `created_at`
- `updated_at`

### 关键约束
- `project_id + channel_type + account_uid` 唯一
- `default_bot_id` 可为空，但为空时需有渠道级兜底策略

### 注意
`bound_device_id` 可先放在这里满足 MVP，但长期更建议独立 `device_account_binding`。

---

## 4.13 `device_command`

### 职责
表示一次下发给设备的执行命令。

### 建议字段
- `id`
- `project_id`
- `device_id`
- `channel_account_id`
- `conversation_id`
- `run_id`
- `command_type`
- `payload_json`
- `idempotency_key`
- `status`（pending / sent / acked / done / failed / expired / cancelled）
- `issued_at`
- `sent_at`
- `ack_at`
- `done_at`
- `failure_reason`
- `retry_count`
- `policy_decision_id`

### 关键约束
- `idempotency_key` 唯一
- 高风险指令必须可追溯到 `policy_decision_id`
- 命令状态流转应受限，防止乱跳

### 为什么它重要
因为真正的业务动作不在服务器里完成，而在设备上完成。

所以这张表本质上是：
- 服务器意图
- 设备执行事实
- 结果回执证据

之间的桥梁。

---

## 4.14 `contact`

### 职责
表示客户/好友/外部联系人的基础身份。

### 建议字段
- `id`
- `project_id`
- `external_uid`
- `display_name`
- `avatar_url`
- `gender`
- `source_channel_type`
- `source_account_id`
- `first_seen_at`
- `last_seen_at`
- `status`
- `created_at`
- `updated_at`

### 关键约束
- 联系人身份统一要考虑跨账号重复识别，但 MVP 可先按“项目内、账号内来源”管理
- 后续若做统一客户视图，可引入 `customer_profile` 聚合多渠道 contact

---

## 4.15 `customer_profile`

### 职责
表示长期客户画像，是 CRM 核心对象。

### 建议字段
- `id`
- `project_id`
- `primary_contact_id`
- `customer_code`
- `stage_code`
- `owner_user_id`
- `source_type`
- `summary_text`
- `preference_json`
- `risk_flag_json`
- `last_ai_summary_at`
- `created_at`
- `updated_at`

### 关键约束
- `stage_code` 应与阶段字典表配合，而不是随便写字符串
- `summary_text` 可以是 AI 总结，但不能替代结构化标签

---

## 4.16 `customer_tag`

### 职责
表示客户标签结果。

### 建议字段
- `id`
- `project_id`
- `customer_profile_id`
- `tag_code`
- `tag_value`
- `source_type`（rule / agent / human / import）
- `source_ref_id`
- `confidence`
- `effective_at`
- `expired_at`
- `created_at`

### 关键约束
- 不同标签是否允许多值，需要按标签字典定义
- AI 标签必须保留 `source_type` 与 `confidence`

---

## 4.17 `message`

### 职责
表示单条消息事件，是会话历史事实表。

### 建议字段
- `id`
- `project_id`
- `conversation_id`
- `channel_account_id`
- `direction`（inbound / outbound / system）
- `sender_type`（customer / ai / human / device / system）
- `message_type`（text / image / file / voice / card / event）
- `content_text`
- `content_payload_json`
- `seq_no`
- `source_message_id`
- `reply_to_message_id`
- `sent_at`
- `received_at`
- `created_at`

### 关键约束
- `conversation_id + seq_no` 唯一
- `source_message_id` 用于对接渠道原生消息 ID 去重

### 设计注意
消息表是大表，尽早按：
- `project_id`
- `conversation_id`
- 时间

设计索引和归档策略。

---

## 4.18 `campaign` 与 `campaign_task`

### `campaign` 职责
表示一个运营活动或 SOP 定义。

### `campaign` 建议字段
- `id`
- `project_id`
- `name`
- `type`（broadcast / nurture / followup / moments / reengagement）
- `status`
- `workflow_version_id`
- `audience_rule_json`
- `schedule_rule_json`
- `risk_policy_profile_id`
- `created_by`
- `created_at`
- `updated_at`

### `campaign_task` 职责
表示某次实际投放/执行任务。

### `campaign_task` 建议字段
- `id`
- `project_id`
- `campaign_id`
- `status`
- `planned_at`
- `started_at`
- `ended_at`
- `audience_snapshot_id`
- `execution_summary_json`
- `success_count`
- `failed_count`
- `created_at`

### 关键约束
- `campaign` 是定义
- `campaign_task` 是执行实例
- 不要混成一张表，不然后续调度和复盘都会乱

---

## 5. 关键关系图（文字版）

可以先把核心关系理解成下面这张“文字 ER 图”：

- 一个 `project` 有多个 `bot`
- 一个 `project` 有多个 `workflow`
- 一个 `workflow` 有多个 `workflow_version`
- 一个 `bot` 引用一个默认 `workflow_version`
- 一个 `project` 有多个 `channel_account`
- 一个 `channel_account` 绑定一个默认 `bot`
- 一个 `channel_account` 下有多个 `conversation`
- 一个 `conversation` 对应一个 `session_runtime`
- 一个 `conversation` 有多条 `message`
- 一个 `session_runtime` 当前最多有一个 `active workflow_run`
- 一个 `workflow_run` 有多个 `node_execution`
- 一个 `node_execution` 可触发零次或一次 `agent_invocation`
- 一个 `workflow_run` 可产生多个 `policy_decision`
- 一个 `workflow_run` 可产生多个 `device_command`
- 一个 `conversation` 关联一个 `contact` 或一个 `group_chat`
- 多个 `contact` 最终可归并到一个 `customer_profile`
- 一个 `customer_profile` 有多个 `customer_tag`
- 一个 `campaign` 有多个 `campaign_task`

---

## 6. 必须从第一天做对的约束

## 6.1 主键风格统一
建议统一使用：
- `UUID` 或 `ULID`

推荐 `ULID` 的理由：
- 可排序
- 分布式生成友好
- 对日志和调试也更友好

## 6.2 状态字段不要乱写自由文本
所有关键状态都建议：
- 有明确枚举
- 有状态机约束
- 不允许业务层随意写脏值

重点对象：
- `session_runtime.session_state`
- `workflow_run.status`
- `device_command.status`
- `conversation.status`
- `campaign_task.status`

## 6.3 JSON 字段可以有，但不能滥用
适合 JSON 的：
- 版本化图结构
- 节点入出参快照
- 审计上下文
- 配置型策略

不适合全塞 JSON 的：
- 核心查询维度
- 频繁过滤字段
- 关键关系字段

### 原则
- **关系靠列，灵活靠 JSON**
- 别把“还没想清楚”伪装成“先用 JSON 灵活一点”

## 6.4 审计链要能串起来
以下链路必须能追溯：

`message -> session_runtime -> workflow_run -> node_execution -> agent_invocation / policy_decision / device_command`

以后查问题时，基本就顺着这条链一路往下挖。

---

## 7. 索引建议（MVP 级）

这里先不给完整 SQL，只给方向。

## 7.1 高频索引对象

### `conversation`
建议索引：
- `(project_id, channel_account_id, last_message_at desc)`
- `(project_id, contact_id)`
- `(project_id, group_chat_id)`

### `session_runtime`
建议索引：
- `(project_id, conversation_id)` unique
- `(project_id, current_bot_id)`
- `(project_id, session_state)`
- `(project_id, active_run_id)`

### `workflow_run`
建议索引：
- `(project_id, conversation_id, started_at desc)`
- `(project_id, status, started_at desc)`
- `(workflow_version_id, started_at desc)`

### `message`
建议索引：
- `(project_id, conversation_id, seq_no)` unique
- `(project_id, conversation_id, created_at desc)`
- `(project_id, source_message_id)`

### `device_command`
建议索引：
- `(project_id, device_id, status, issued_at desc)`
- `(project_id, run_id)`
- `(idempotency_key)` unique

### `agent_invocation`
建议索引：
- `(project_id, run_id)`
- `(project_id, agent_type, started_at desc)`
- `(project_id, model_name, started_at desc)`

### `policy_decision`
建议索引：
- `(project_id, conversation_id, created_at desc)`
- `(project_id, decision_type, created_at desc)`

---

## 8. 分库分表与扩展演进建议

当前阶段目标是约 1000 渠道账号，不建议一开始过度分片，但有些表从第一天就要按“将来会很大”来设计。

## 8.1 初期可单库的表
- `project`
- `bot`
- `workflow`
- `workflow_version`
- `campaign`
- `policy_profile_*`

这些表相对低频、体量可控。

## 8.2 初期单库但要预留扩展的表
- `conversation`
- `session_runtime`
- `workflow_run`
- `device_command`
- `agent_invocation`
- `policy_decision`

建议：
- 先 PostgreSQL 单库
- 通过 `project_id` 和时间维度做索引
- 表结构不要强绑定单机假设

## 8.3 优先考虑归档/分区的大表
- `message`
- `node_execution`
- `audit_log`
- `device_event`

这些表后面增长会非常快。

### 推荐思路
- 按时间分区
- 必要时叠加 `project_id` 逻辑分桶
- 热数据和历史数据分层存储

---

## 9. 事件模型建议

除了关系模型，还建议同步定义统一事件模型。至少包括：

- `InboundMessageReceived`
- `ConversationHostingStarted`
- `WorkflowRunStarted`
- `WorkflowRunInterrupted`
- `NodeExecutionCompleted`
- `AgentInvocationCompleted`
- `PolicyDecisionMade`
- `DeviceCommandIssued`
- `DeviceCommandFailed`
- `HumanHandoffActivated`
- `HumanHandoffReleased`
- `CampaignTaskStarted`

这些事件不一定都要先上事件总线，但命名和语义最好统一。

---

## 10. MVP 建表优先级建议

## 第一批必须建
- `project`
- `bot`
- `workflow`
- `workflow_version`
- `channel_account`
- `device`
- `conversation`
- `session_runtime`
- `message`
- `workflow_run`
- `node_execution`
- `device_command`
- `policy_decision`
- `agent_invocation`
- `contact`
- `customer_profile`
- `customer_tag`

## 第二批增强建
- `bot_version`
- `device_account_binding`
- `group_chat`
- `campaign`
- `campaign_task`
- `audit_log`
- `debug_session`
- `alert_event`

## 第三批优化建
- 统计宽表 / 指标事实表
- 实验与灰度表
- 预算与成本账本表
- 多设备调度与设备池表

---

## 11. 几个容易踩坑的地方

## 11.1 把 `conversation` 当运行态表
错。

`conversation` 是会话身份容器，不是当前运行寄存器。
真正高频变化的是 `session_runtime`。

## 11.2 把 Bot 与 Workflow 混成一张大表
错。

这样后面版本、回滚、灰度、审计都会很痛苦。

## 11.3 用消息表反推所有业务状态
错。

消息是事实日志，不适合承担当前控制状态。

## 11.4 用一个 JSON 存所有策略
错。

策略可以配置化，但核心决策结果必须结构化、可索引、可审计。

## 11.5 把 Supervisor Agent 决策直接写死为最终结论
错。

Supervisor Agent 的结果应进入 `agent_invocation` 或 `policy_decision`，但最终采纳必须有系统决策链承接。

---

## 12. 最终建议

如果只保留一句话：

**Morphix 的数据模型核心，不是“聊天记录表”或“机器人表”，而是围绕 `Project -> Bot -> WorkflowVersion -> Conversation -> SessionRuntime -> WorkflowRun -> DeviceCommand / PolicyDecision / AgentInvocation` 这条主骨架展开。**

再压缩成三个判断：

1. **Bot、WorkflowVersion、SessionRuntime 必须拆开**
2. **会话态、运行态、客户态必须拆开**
3. **设备执行事实、策略决策事实、Agent 调用事实必须可审计地独立留痕**

只要这三条守住，后面从 1000 账号演进到更大规模时，系统不会轻易长歪。