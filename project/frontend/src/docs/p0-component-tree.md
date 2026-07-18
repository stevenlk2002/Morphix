# P0 会话控制台 —— 页面组件树草案

> 适用范围：Sprint A（会话列表 / 详情 / 消息 / 接管）+ Sprint B（会话工作台 + Bot 绑定 + Run 调试 + 审计）。
> 本文件为**纯结构草案**，不落地组件代码；每层标注主要数据来源（morphix-control 端点 / schema），供后续组件 props 设计。
> 类型定义见 `src/types/control.ts`，端点映射见该文件顶部注释。

## 组件树

```
AppShell
├─ Sidebar                          # 项目导航（ProjectData）
│
├─ ConversationListView             # GET /control/conversations?projectId&state&handoff&q&page&pageSize
│  └─ ConversationRow               # ConversationListItem
│       · channel_account_id, conversation_type, subject
│       · session_state (SessionState badge)
│       · handoff_status (HandoffStatus badge)
│       · current_bot: BotSummary | null
│       · last_message_preview / last_message_at
│  └─ ConversationFilters           # state / handoff / q 控件
│  └─ Pager                         # page / pageSize / total
│
├─ ConversationWorkbench            # 工作台主区（Sprint B 核心）
│  ├─ ConversationHeader            # ConversationDetail
│  │    · subject, owner_type (ai|human), handoff_status
│  │    · current_bot, current_workflow_version_id
│  │    · latest_handoff: HandoffSnapshot
│  │    · contact: ContactRef
│  │    └─ HandoffControls
│  │         ├─ TakeoverButton     # POST /control/conversations/{id}/handoff  (HandoffRequest)
│  │         └─ ReturnButton       # POST /control/conversations/{id}/return   (HandoffReturnRequest, ResumeMode)
│  │
│  ├─ MessageThread                 # GET /control/conversations/{id}/messages?beforeSeq&limit
│  │    └─ MessageBubble           # ConversationMessage
│  │         · sender_type (customer|ai|human|system|device)
│  │         · message_type (MessageType)
│  │         · content_text, sent_at, seq_no
│  │    └─ ThreadPager             # has_more / next_before_seq
│  │
│  ├─ SessionRuntimePanel           # GET /control/conversations/{id}/runtime
│  │    · hosting_status (HostingStatus)
│  │    · session_state (SessionState)
│  │    · interrupt_policy (InterruptPolicy)
│  │    · active_run_id, waiting_node_id, current_bot_id
│  │    · locked_until, last_policy_decision_id, updated_at
│  │
│  ├─ BotBindingSection             # BotSummary + 绑定交互（Sprint B: Bot 绑定）
│  │    · 当前 Bot 展示 / 切换（依赖 management CRUD，contract-TBD，P0 暂只读 + 占位按钮）
│  │
│  ├─ RunDebugPanel                 # Sprint B: Run 调试
│  │    ├─ RunLauncher             # POST /control/workflow-runs  (CreateWorkflowRunRequest)
│  │    │    · trigger_type, workflow_version_id, input_context
│  │    ├─ RunDetailView          # GET /control/workflow-runs/{run_id}  (WorkflowRunDetail)
│  │    │    · status (WorkflowRunStatus), current_node_id
│  │    │    · started_at/ended_at, error_code/error_message
│  │    │    · parent_run_id/root_run_id（重跑/子树）
│  │    │    └─ RunControls
│  │    │         ├─ InterruptBtn  # POST .../interrupt (InterruptWorkflowRunRequest)
│  │    │         ├─ ResumeBtn     # POST .../resume    (ResumeWorkflowRunRequest, ResumeMode)
│  │    │         └─ CancelBtn     # POST .../cancel     (CancelWorkflowRunRequest)
│  │    ├─ NodeExecutionTimeline   # GET .../node-executions (NodeExecutionListData)
│  │    │    · node_id, node_type, status (NodeStatus)
│  │    │    · attempt_no, duration_ms, error_code, executor_type
│  │    ├─ PolicyDecisionTable     # GET .../policy-decisions (PolicyDecisionListData)
│  │    │    · decision_type (DecisionType), decision, reason_codes[], model_profile
│  │    └─ AgentInvocationList     # GET .../agent-invocations (AgentInvocationListData)
│  │         · agent_type (AgentType), model_name, latency_ms
│  │         · estimated_cost, status (AgentStatus), confidence
│  │
│  └─ AuditDrawer (optional)        # 统一聚合 policy-decisions 两种端点
│
└─ Toast / ErrorBoundary            # 统一处理 ApiEnvelope(code, message) 与 ApiError
```

## 数据来源速查（组件 → 类型 → 端点）

| 组件 | 类型 | 端点 |
| --- | --- | --- |
| ConversationListView / Row | `ConversationListData` / `ConversationListItem` | `GET /control/conversations` |
| ConversationHeader | `ConversationDetail` | `GET /control/conversations/{id}` |
| MessageThread / Bubble | `ConversationMessageListData` / `ConversationMessage` | `GET /control/conversations/{id}/messages` |
| SessionRuntimePanel | `ConversationRuntime` | `GET /control/conversations/{id}/runtime` |
| HandoffControls | `HandoffRequest` / `HandoffReturnRequest` / `HandoffResponseData` | `POST /control/conversations/{id}/handoff`、`/return` |
| BotBindingSection | `BotSummary` | 只读（management CRUD 未就绪） |
| RunLauncher / RunDetailView | `CreateWorkflowRunRequest` / `CreateWorkflowRunResponseData` / `WorkflowRunDetail` | `POST /control/workflow-runs`、`GET /control/workflow-runs/{run_id}` |
| RunControls | `InterruptWorkflowRunRequest` / `ResumeWorkflowRunRequest` / `CancelWorkflowRunRequest` / `WorkflowRunStateMutationData` | `POST .../interrupt`、`/resume`、`/cancel` |
| NodeExecutionTimeline | `NodeExecutionListData` / `NodeExecution` | `GET /control/workflow-runs/{run_id}/node-executions` |
| PolicyDecisionTable | `PolicyDecisionListData` / `PolicyDecision` | `GET /control/workflow-runs/{run_id}/policy-decisions` |
| AgentInvocationList | `AgentInvocationListData` / `AgentInvocation` | `GET /control/workflow-runs/{run_id}/agent-invocations` |

## 待拍板 / 边界风险

1. **Bot 绑定交互**：`BotSummary` 只读；真正切换/绑定 Bot 依赖 management CRUD（`BotUpdate` / `WorkflowVersionCreate` 等），control 端点中这些仍是 `contract-TBD`，**P0 只能展示 + 占位按钮，不能写**。
2. **operator_id 来源**：接管 / Return / Run 控制请求体都需 `operator_id`，但 control 端点当前无 auth。P0 先写死占位 `operator_id`，待用户态接入后替换。
3. **前端技术栈**：当前 `src/` 为 `.jsx`（JS），本类型草案按 `src/types/control.ts`（TS）给出，与仓库根 `tsconfig.json`（strict 开启）一致；组件落地时需配合 TS 化或保持 JS 引用类型声明。
4. **目录约定**：本草案沿用现有 `src/pages/Sessions` + `src/components` 扁平结构；若后续引入 `features/` 分层，再调整组件归属。
