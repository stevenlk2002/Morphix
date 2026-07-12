# Morphix 接口设计-总控编排与会话运行时

## 1. 文档目标

这份文档是在以下设计基础上继续下钻：

- `design-总控编排层详细设计.md`
- `design-总控编排时序与状态图.md`
- `design-核心数据模型设计.md`
- `design-数据库表结构设计.md`

目标是把已经收敛的对象模型与表结构，进一步落成一套**可实施的控制面 / 执行面接口基线**，重点覆盖：

1. 会话入口与消息入站
2. 会话列表与运行态查询
3. 工作流运行控制
4. 设备命令下发与回执
5. 人工接管与交还
6. 策略决策与 Agent 调用审计

一句话说：

**这份文档回答的是：Morphix 的总控编排层，到底通过哪些 API 对外协作。**

---

## 2. 接口分层原则

建议把接口按三层来理解：

### 2.1 控制面 API
给 Web 管理后台、运营平台、实施人员使用。

典型能力：
- 查会话
- 看运行态
- 转人工
- 恢复托管
- 查运行记录
- 查决策日志

### 2.2 执行面 API
给渠道接入、设备网关、运行时服务使用。

典型能力：
- 入站消息上报
- 设备回执上报
- 运行实例启动 / 中断 / 恢复
- 下发设备命令

### 2.3 内部编排 API
给 Session Orchestrator、Policy Router、Workflow Runtime、Agent Executor 之间调用。

这类接口可以先以内网 REST 为主，后续再按性能需求逐步内聚为事件流或 RPC。

---

## 3. 基本约定

## 3.1 URL 风格
统一建议：

- 控制面：`/api/control/...`
- 执行面：`/api/runtime/...`
- 设备回调：`/api/device/...`
- 内部服务：`/internal/...`

## 3.2 返回体结构
推荐统一包裹：

```json
{
  "requestId": "01J...",
  "success": true,
  "data": {},
  "error": null
}
```

失败时：

```json
{
  "requestId": "01J...",
  "success": false,
  "data": null,
  "error": {
    "code": "RUNTIME_CONFLICT",
    "message": "Conversation is currently locked by another run"
  }
}
```

## 3.3 幂等要求
以下接口建议强制支持幂等：

- 入站消息上报
- 设备命令创建
- 设备回执上报
- 转人工 / 交还托管
- 工作流启动请求

可通过 Header：
- `Idempotency-Key`

或业务键：
- `sourceMessageId`
- `commandId`
- `handoffRequestId`

## 3.4 鉴权建议

### 控制面 API
- JWT / Session 登录态
- 必须带项目级权限

### 执行面 API
- 设备签名 / 渠道签名 / 内部服务 Token

### 内部 API
- 服务间鉴权 + 来源白名单

---

## 4. 会话入口与消息入站接口

这是整个总控编排层最核心的入口。

---

## 4.1 入站消息上报

### 接口
`POST /api/runtime/inbound-events/messages`

### 用途
渠道接入层或设备网关把客户新消息标准化后上报给总控编排层。

### 请求体

```json
{
  "projectId": "01JPROJECT",
  "channelAccountId": "01JACCOUNT",
  "deviceId": "01JDEVICE",
  "conversationType": "direct",
  "sourceConversationId": "wx_conv_9981",
  "sourceMessageId": "wx_msg_abc_001",
  "contact": {
    "externalUid": "wx_user_7788",
    "displayName": "张三"
  },
  "message": {
    "messageType": "text",
    "contentText": "我想了解下报价",
    "sentAt": "2026-07-12T16:30:00+08:00"
  },
  "metadata": {
    "channelType": "wechat",
    "roomTopic": null,
    "rawPayloadDigest": "sha256:xxxx"
  }
}
```

### 返回体

```json
{
  "requestId": "01JREQ001",
  "success": true,
  "data": {
    "conversationId": "01JCONV001",
    "messageId": "01JMSG001",
    "sessionRuntimeId": "01JSR001",
    "accepted": true,
    "dispatchMode": "sync_orchestrate"
  },
  "error": null
}
```

### 关键规则
- 使用 `sourceMessageId` 去重
- 只接受标准化后的事件，不直接让上层处理渠道差异
- 入站成功不等于已经回复，只代表进入编排链路

### 可能错误
- `PROJECT_NOT_FOUND`
- `CHANNEL_ACCOUNT_NOT_FOUND`
- `DUPLICATE_MESSAGE`
- `DEVICE_UNAUTHORIZED`
- `PAYLOAD_INVALID`

---

## 4.2 入站事件处理结果查询

### 接口
`GET /api/runtime/inbound-events/{requestId}`

### 用途
如果入站处理改成异步或半异步，可用于查询分发结果。

### 返回体示例

```json
{
  "requestId": "01JREQ001",
  "success": true,
  "data": {
    "status": "processed",
    "conversationId": "01JCONV001",
    "runId": "01JRUN001",
    "dispatchResult": "workflow_started"
  },
  "error": null
}
```

---

## 5. 会话与运行态查询接口

这些接口主要给控制面和运营端使用。

---

## 5.1 会话列表查询

### 接口
`GET /api/control/conversations`

### 查询参数
- `projectId` 必填
- `channelAccountId` 可选
- `botId` 可选
- `sessionState` 可选
- `handoffStatus` 可选
- `keyword` 可选
- `updatedAfter` 可选
- `page` / `pageSize`

### 返回体示例

```json
{
  "requestId": "01JREQ002",
  "success": true,
  "data": {
    "items": [
      {
        "conversationId": "01JCONV001",
        "channelAccountId": "01JACCOUNT",
        "conversationType": "direct",
        "subject": "张三",
        "sessionState": "AUTO_HOSTING",
        "handoffStatus": "none",
        "currentBot": {
          "id": "01JBOT001",
          "name": "销售转化机器人"
        },
        "lastMessageAt": "2026-07-12T16:30:00+08:00",
        "lastMessagePreview": "我想了解下报价"
      }
    ],
    "page": 1,
    "pageSize": 20,
    "total": 138
  },
  "error": null
}
```

---

## 5.2 会话详情查询

### 接口
`GET /api/control/conversations/{conversationId}`

### 用途
返回会话基础信息、客户信息、当前托管状态。

### 返回重点字段
- 会话基本信息
- 联系人 / 群信息
- 当前 owner（AI / human）
- 当前 Bot
- 当前 WorkflowVersion
- 最近一次人工接管信息

---

## 5.3 会话消息流水查询

### 接口
`GET /api/control/conversations/{conversationId}/messages`

### 查询参数
- `beforeSeq`
- `afterSeq`
- `limit`

### 用途
消息分页拉取。

### 设计建议
- 默认按 `seq_no desc` 查询
- 支持回溯加载
- 后期可支持按 `senderType` / `messageType` 过滤

---

## 5.4 当前运行态查询

### 接口
`GET /api/control/conversations/{conversationId}/runtime`

### 返回体示例

```json
{
  "requestId": "01JREQ003",
  "success": true,
  "data": {
    "sessionRuntimeId": "01JSR001",
    "hostingStatus": "enabled",
    "sessionState": "AUTO_HOSTING",
    "handoffStatus": "none",
    "interruptPolicy": "MERGE_WINDOW",
    "currentBotId": "01JBOT001",
    "currentWorkflowVersionId": "01JWVF001",
    "activeRunId": "01JRUN001",
    "waitingNodeId": null,
    "lockedUntil": null,
    "lastPolicyDecisionId": "01JPD001",
    "updatedAt": "2026-07-12T16:31:12+08:00"
  },
  "error": null
}
```

### 用途
这是运营端最关键的观察窗口之一。

---

## 6. 工作流运行控制接口

这部分接口用于总控编排和调试控制。

---

## 6.1 手动启动工作流运行

### 接口
`POST /api/control/workflow-runs`

### 用途
人工触发某个会话或某个任务的工作流执行。

### 请求体

```json
{
  "projectId": "01JPROJECT",
  "conversationId": "01JCONV001",
  "workflowVersionId": "01JWVF001",
  "triggerType": "manual",
  "inputContext": {
    "manualReason": "运营人员强制重试"
  }
}
```

### 返回体

```json
{
  "requestId": "01JREQ004",
  "success": true,
  "data": {
    "runId": "01JRUN002",
    "status": "pending"
  },
  "error": null
}
```

---

## 6.2 运行实例详情查询

### 接口
`GET /api/control/workflow-runs/{runId}`

### 返回重点字段
- 基本状态
- triggerType
- currentNodeId
- startedAt / endedAt
- errorCode / errorMessage
- resultSummary
- parentRunId / rootRunId

---

## 6.3 运行实例节点轨迹查询

### 接口
`GET /api/control/workflow-runs/{runId}/node-executions`

### 用途
用于调试回放、运行链路排障。

### 返回重点字段
- nodeId
- nodeType
- status
- attemptNo
- durationMs
- errorCode
- executorType

---

## 6.4 中断运行实例

### 接口
`POST /api/control/workflow-runs/{runId}/interrupt`

### 请求体

```json
{
  "reason": "manual_handoff",
  "operatorId": "01JUSER001"
}
```

### 用途
人工接管、运营干预、策略冻结时使用。

### 关键规则
- 只能中断 `pending / running / waiting`
- 已完成或已取消的 run 不可再中断

---

## 6.5 恢复运行实例

### 接口
`POST /api/control/workflow-runs/{runId}/resume`

### 请求体

```json
{
  "resumeMode": "continue",
  "operatorId": "01JUSER001"
}
```

### `resumeMode` 建议值
- `continue`：沿原状态继续
- `replan`：从当前上下文重新规划
- `restart_from_node`：从指定节点重启

---

## 6.6 取消运行实例

### 接口
`POST /api/control/workflow-runs/{runId}/cancel`

### 用途
彻底取消当前执行，不再尝试恢复。

---

## 7. 设备命令下发与回执接口

这是执行面和设备边缘面闭环的关键。

---

## 7.1 创建设备命令

### 接口
`POST /api/runtime/device-commands`

### 用途
总控编排层或 Workflow Runtime 创建一条待执行设备命令。

### 请求体

```json
{
  "projectId": "01JPROJECT",
  "deviceId": "01JDEVICE",
  "channelAccountId": "01JACCOUNT",
  "conversationId": "01JCONV001",
  "runId": "01JRUN001",
  "commandType": "send_message",
  "payload": {
    "messageType": "text",
    "contentText": "您好，这边把报价单发您参考下。"
  },
  "policyDecisionId": "01JPD010"
}
```

### 返回体

```json
{
  "requestId": "01JREQ005",
  "success": true,
  "data": {
    "commandId": "01JCMD001",
    "status": "pending"
  },
  "error": null
}
```

### 说明
这一步是“下发意图”创建，不一定意味着设备已经收到。

---

## 7.2 设备拉取待执行命令

### 接口
`GET /api/device/commands/pending`

### 查询参数
- `deviceId`
- `limit`

### 用途
如果设备采用轮询模式，可用此接口获取待执行命令。

### 返回体字段
- commandId
- commandType
- payload
- issuedAt
- idempotencyKey

### 说明
如果后续改成 MQ / 推送模型，这个接口仍可作为兜底。

---

## 7.3 设备命令 ACK 回执

### 接口
`POST /api/device/commands/{commandId}/ack`

### 请求体

```json
{
  "deviceId": "01JDEVICE",
  "ackedAt": "2026-07-12T16:32:01+08:00"
}
```

### 用途
设备确认“收到命令”。

### 状态变化
- `pending -> acked`
- 或 `sent -> acked`

---

## 7.4 设备命令完成回执

### 接口
`POST /api/device/commands/{commandId}/complete`

### 请求体

```json
{
  "deviceId": "01JDEVICE",
  "doneAt": "2026-07-12T16:32:05+08:00",
  "result": {
    "platformMessageId": "wx_sent_9911"
  }
}
```

### 用途
设备确认命令真正执行完成。

### 状态变化
- `acked -> done`

### 关键规则
完成回执进入后，应反向更新：
- `device_command`
- `session_runtime.session_state`
- 如有需要，推进 `workflow_run`

---

## 7.5 设备命令失败回执

### 接口
`POST /api/device/commands/{commandId}/fail`

### 请求体

```json
{
  "deviceId": "01JDEVICE",
  "failedAt": "2026-07-12T16:32:05+08:00",
  "failureReason": "wechat_send_blocked",
  "retryable": true
}
```

### 用途
设备执行失败时上报。

### 后续动作
由总控层决定：
- 重试
- 降级
- 转人工
- 冻结托管

---

## 8. 人工接管与交还接口

---

## 8.1 发起人工接管

### 接口
`POST /api/control/conversations/{conversationId}/handoff`

### 请求体

```json
{
  "projectId": "01JPROJECT",
  "operatorId": "01JUSER001",
  "reason": "customer_asks_for_human"
}
```

### 返回体

```json
{
  "requestId": "01JREQ006",
  "success": true,
  "data": {
    "handoffStatus": "active",
    "sessionState": "HUMAN_HANDOFF"
  },
  "error": null
}
```

### 关键规则
- 接管成功后，AI 必须停止主动发言
- 如有 active run，应先中断或挂起
- 必须生成审计记录与必要的 `policy_decision`

---

## 8.2 交还托管

### 接口
`POST /api/control/conversations/{conversationId}/handoff/return`

### 请求体

```json
{
  "projectId": "01JPROJECT",
  "operatorId": "01JUSER001",
  "resumeMode": "replan"
}
```

### `resumeMode` 建议值
- `idle`：回到空闲，不自动继续
- `continue`：恢复原 run
- `replan`：基于最新上下文重新规划

### 说明
推荐默认值：`replan`

因为真实会话场景里，人工接管期间上下文往往已经变了。

---

## 9. 策略决策与审计查询接口

---

## 9.1 查询会话决策日志

### 接口
`GET /api/control/conversations/{conversationId}/policy-decisions`

### 用途
查看某个会话的 Bot 选择、中断、转人工、模型选择、风险阻断等决策记录。

### 查询参数
- `decisionType`
- `page`
- `pageSize`

---

## 9.2 查询单次运行的策略决策

### 接口
`GET /api/control/workflow-runs/{runId}/policy-decisions`

### 用途
排查一次执行为什么走到这一步。

---

## 9.3 查询 Agent 调用记录

### 接口
`GET /api/control/workflow-runs/{runId}/agent-invocations`

### 返回重点字段
- agentType
- modelName
- latencyMs
- estimatedCost
- status
- confidence

### 价值
这是后续做：
- 成本分析
- 误判分析
- Supervisor Agent 使用治理

的基础接口。

---

## 10. 内部编排接口建议

这部分可以先实现成内网 REST，后续再按压力演进。

---

## 10.1 Orchestrator 请求策略路由

### 接口
`POST /internal/policy-router/evaluate`

### 用途
Session Orchestrator 请求 Policy Router 进行路由判断。

### 请求体

```json
{
  "projectId": "01JPROJECT",
  "conversationId": "01JCONV001",
  "sessionRuntimeId": "01JSR001",
  "eventType": "inbound_message",
  "eventPayload": {
    "messageType": "text",
    "contentText": "我想了解下报价"
  },
  "context": {
    "currentBotId": "01JBOT001",
    "sessionState": "WAITING_USER",
    "customerStage": "lead"
  }
}
```

### 返回体

```json
{
  "botSelection": "01JBOT001",
  "workflowVersionSelection": "01JWVF001",
  "allowedAgentSet": ["qa", "sales_progress"],
  "modelProfile": "standard",
  "interruptDecision": "INTERRUPT_AND_REPLAN",
  "handoffDecision": "stay_ai",
  "supervisorNeeded": false,
  "reasonCodes": ["DEFAULT_BOT_MATCH", "LEAD_STAGE_STANDARD_FLOW"]
}
```

---

## 10.2 Runtime 请求 Agent 执行

### 接口
`POST /internal/agent-executor/invoke`

### 用途
Workflow Runtime 调用能力节点。

### 请求体关键字段
- `runId`
- `nodeExecutionId`
- `agentType`
- `modelProfile`
- `structuredInput`
- `knowledgeContext`
- `toolScope`

### 返回体关键字段
- `structuredOutput`
- `summary`
- `confidence`
- `latencyMs`
- `estimatedCost`

---

## 10.3 Runtime 请求 Supervisor Agent

### 接口
`POST /internal/agent-executor/supervisor`

### 用途
仅在复杂场景触发 Supervisor Agent。

### 说明
必须要求：
- 输入结构化
- 输出结构化建议
- 不允许直接越权改写会话状态

---

## 11. 错误码建议

建议先统一一版核心错误码。

### 通用类
- `INVALID_REQUEST`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `CONFLICT`
- `IDEMPOTENCY_CONFLICT`

### 会话运行类
- `SESSION_RUNTIME_LOCKED`
- `RUN_STATE_INVALID`
- `RUN_ALREADY_COMPLETED`
- `RUN_INTERRUPT_NOT_ALLOWED`
- `HANDOFF_STATE_INVALID`

### 设备类
- `DEVICE_OFFLINE`
- `DEVICE_UNAUTHORIZED`
- `COMMAND_ALREADY_ACKED`
- `COMMAND_ALREADY_DONE`
- `COMMAND_STATUS_INVALID`

### 策略类
- `RISK_POLICY_BLOCKED`
- `MODEL_PROFILE_NOT_ALLOWED`
- `SUPERVISOR_NOT_ALLOWED`
- `BOT_SELECTION_FAILED`

### 数据类
- `DUPLICATE_MESSAGE`
- `CONVERSATION_NOT_FOUND`
- `WORKFLOW_VERSION_NOT_FOUND`

---

## 12. MVP 接口优先级建议

建议不要一口气把所有 API 做满，而是先保核心闭环。

## 第一批：必须先做
1. `POST /api/runtime/inbound-events/messages`
2. `GET /api/control/conversations`
3. `GET /api/control/conversations/{conversationId}/runtime`
4. `POST /api/runtime/device-commands`
5. `POST /api/device/commands/{commandId}/ack`
6. `POST /api/device/commands/{commandId}/complete`
7. `POST /api/device/commands/{commandId}/fail`
8. `POST /api/control/conversations/{conversationId}/handoff`
9. `POST /api/control/conversations/{conversationId}/handoff/return`
10. `GET /api/control/workflow-runs/{runId}`
11. `GET /api/control/workflow-runs/{runId}/node-executions`

## 第二批：增强接口
12. `POST /api/control/workflow-runs`
13. `POST /api/control/workflow-runs/{runId}/interrupt`
14. `POST /api/control/workflow-runs/{runId}/resume`
15. `GET /api/control/conversations/{conversationId}/messages`
16. `GET /api/control/conversations/{conversationId}/policy-decisions`
17. `GET /api/control/workflow-runs/{runId}/agent-invocations`

## 第三批：内部治理增强
18. `/internal/policy-router/evaluate`
19. `/internal/agent-executor/invoke`
20. `/internal/agent-executor/supervisor`

---

## 13. 推荐的下一步

现在对象模型、表结构、接口基线都已经基本成型，下一步最值钱的是：

1. **ER 图 / 关系图**
2. **接口时序图**
3. **MVP 开发拆解清单**
4. **OpenAPI 初稿**

如果要直接进入研发对齐，我建议下一步优先做：

- `design-ER图与领域关系说明.md`
- 或 `openapi-总控编排与会话运行时.yaml`

---

## 14. 最终结论

如果只保留一句话：

**Morphix 的接口设计核心，不是“做几个聊天 API”，而是把“会话入口 -> 总控编排 -> 工作流执行 -> Agent 调用 -> 设备动作 -> 回执闭环 -> 人工接管 -> 审计查询”这整条链路定义成稳定、可控、可回放的系统接口。**

这条链路一旦清晰，后面无论是前端开发、后端开发、设备端开发，还是测试联调，都会顺很多。