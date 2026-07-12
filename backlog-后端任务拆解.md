# Morphix 后端任务拆解清单

## 1. 文档目标

这份文档是在《`design-MVP研发任务拆解清单.md`》基础上继续下钻，目标是把 MVP 里与后端有关的工作，进一步拆成：

- 可以直接进入迭代排期的任务项
- 可以明确 owner 的任务包
- 可以按依赖顺序推进的交付序列
- 可以作为前后端、设备端联调基线的后端 backlog

一句话说：

**这份文档回答的是：Morphix 后端团队明天上班，到底先做哪几件事。**

---

## 2. 后端范围说明

这里的“后端”不是单个 API 服务，而是三类后端职责：

1. **控制面后端**
   - 给 Web 控制台、运营平台、实施后台使用
   - 负责项目、Bot、WorkflowVersion、会话查询、人工接管、审计查询

2. **运行时后端**
   - 负责入站消息接入、Session Orchestrator、Policy Router、Workflow Runtime、Agent Executor、运行态推进
   - 这是 MVP 主链路核心

3. **设备接入后端**
   - 负责设备鉴权、待执行命令拉取、ACK / complete / fail、心跳与在线状态
   - 是设备边缘面与服务端的桥

为了避免“谁都写一点，最后谁都接不住”，建议这三块明确拆 owner。

---

## 3. 后端研发原则

## 3.1 先闭环，再增强
优先打通：

`入站消息 -> 运行编排 -> 命令下发 -> 设备回执 -> 人工接管 -> 审计查询`

不要先做：
- 复杂路由智能化
- 复杂报表
- 全渠道兼容
- 多模型动态优化

## 3.2 先确定性，再智能化
MVP 中：
- 主调度靠系统状态机
- 路由先用规则版
- Agent 先做结构化调用
- Supervisor Agent 不作为默认主路径依赖

## 3.3 先事实留痕，再讨论体验优化
以下事实对象必须先能留痕：
- 入站消息事实
- 会话运行事实
- 节点执行事实
- 策略决策事实
- Agent 调用事实
- 设备命令事实
- 人工接管事实

这几类事实只要丢一个，后面调试就会非常痛苦。

---

## 4. 任务优先级定义

- **P0**：不做就跑不通主链路
- **P1**：主链路能跑，但没有会严重影响联调、排障、交付
- **P2**：增强项，可排到第二轮

---

## 5. 推荐后端团队分工

## 5.1 控制面后端 owner
负责：
- 项目 / Bot / WorkflowVersion 管理
- 会话查询
- 人工接管
- 审计查询
- 控制面鉴权

## 5.2 运行时后端 owner
负责：
- 入站消息接入
- Session Orchestrator
- Policy Router
- Workflow Runtime
- Agent Executor
- 运行状态推进
- 命令创建

## 5.3 设备接入后端 owner
负责：
- 设备注册与鉴权
- 待执行命令接口
- 回执接口
- 心跳接口
- 设备在线状态维护

## 5.4 公共基础 owner
负责：
- 配置管理
- PostgreSQL / Redis 基础设施
- 日志与 tracing
- OpenAPI 契约维护
- migration 规范

---

## 6. 后端总依赖顺序

推荐按下面顺序推进：

1. 公共底座
2. 数据库主骨架
3. OpenAPI 对齐
4. 运行时入站与会话定位
5. Policy Router（规则版）
6. Workflow Runtime
7. Agent Executor
8. Device Command Gateway
9. 设备回执链路
10. 人工接管
11. 控制面查询接口
12. 审计与调试接口
13. 心跳 / 在线状态 / 灰度增强

一句话：

**先把“系统能动起来”的部分写完，再去写“系统看起来更完整”的部分。**

---

# 7. P0 任务清单：主链路必须项

# 7.1 公共底座任务

## BE-001 配置中心与环境变量校验
- **优先级**：P0
- **Owner**：公共基础
- **目标**：统一读取 DB、Redis、LLM、JWT、内部服务 token、设备 token 等配置
- **依赖**：无
- **落点**：
  - `backend/shared/config/*`
  - `.env.example`
- **验收标准**：
  - 缺少关键配置时服务启动失败
  - 本地 / 测试 / 预发环境配置项清晰分离

## BE-002 PostgreSQL 与 Redis 连接基座
- **优先级**：P0
- **Owner**：公共基础
- **目标**：准备数据库连接池、Redis 客户端、健康检查
- **依赖**：BE-001
- **落点**：
  - `backend/shared/database/*`
  - `backend/shared/redis/*`
- **验收标准**：
  - `/health`、`/ready` 能反映 DB/Redis 状态
  - 连接参数集中配置

## BE-003 统一错误结构与 requestId 中间件
- **优先级**：P0
- **Owner**：公共基础
- **目标**：控制面、运行时、设备面统一响应结构与错误码基础
- **依赖**：BE-001
- **落点**：
  - `backend/shared/http/*`
  - `backend/shared/errors/*`
- **验收标准**：
  - 所有接口返回 `requestId/success/data/error`
  - 所有异常都带 requestId

## BE-004 幂等中间件
- **优先级**：P0
- **Owner**：公共基础
- **目标**：支持 `Idempotency-Key` 与业务键防重
- **依赖**：BE-002
- **落点**：
  - `backend/shared/idempotency/*`
- **验收标准**：
  - 入站消息、命令创建、命令回执、接管动作均可防重

## BE-005 OpenAPI 契约装载与接口骨架生成
- **优先级**：P0
- **Owner**：公共基础
- **目标**：将 `openapi-总控编排与会话运行时.yaml` 纳入后端交付流程
- **依赖**：BE-003
- **落点**：
  - `openapi/`
  - `backend/shared/contracts/*`
- **验收标准**：
  - 接口实现与 OpenAPI 契约可校对
  - Mock / 文档预览可用

---

# 7.2 数据骨架任务

## BE-101 第一批 migration 建立
- **优先级**：P0
- **Owner**：公共基础 + 控制面后端
- **目标**：落地第一批核心表
- **依赖**：BE-002
- **覆盖表**：
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
  - `policy_decision`
  - `agent_invocation`
  - `device_command`
- **验收标准**：
  - migration 可重复执行
  - 索引与唯一约束符合设计稿

## BE-102 种子数据脚本
- **优先级**：P0
- **Owner**：控制面后端
- **目标**：初始化演示项目、Bot、workflow_version、测试设备账号
- **依赖**：BE-101
- **验收标准**：
  - 新环境初始化后可直接跑一条演示主链路

---

# 7.3 运行时主链路任务

## BE-201 入站消息接口实现
- **优先级**：P0
- **Owner**：运行时后端
- **对应接口**：`POST /api/runtime/inbound-events/messages`
- **目标**：接收标准化入站消息并完成基础校验
- **依赖**：BE-003、BE-004、BE-101
- **数据落点**：
  - `message`
  - `conversation`
  - `session_runtime`
- **验收标准**：
  - 同一 `sourceMessageId` 不重复进入链路
  - 非法设备 / 非法账号请求被拒绝

## BE-202 会话定位与创建逻辑
- **优先级**：P0
- **Owner**：运行时后端
- **目标**：根据 `projectId + channelAccountId + sourceConversationId` 定位或创建会话
- **依赖**：BE-201
- **数据落点**：
  - `conversation`
  - `session_runtime`
- **验收标准**：
  - 新会话可自动创建
  - 老会话可准确命中

## BE-203 Session Orchestrator 会话锁与并发控制
- **优先级**：P0
- **Owner**：运行时后端
- **目标**：避免同一会话在并发消息下状态乱写
- **依赖**：BE-202、BE-002
- **技术落点**：
  - Redis 锁 / DB 乐观锁 / 二者组合
- **验收标准**：
  - 高并发下同一会话不会生成冲突 active run

## BE-204 Policy Router（规则版）实现
- **优先级**：P0
- **Owner**：运行时后端
- **对应接口**：`POST /internal/policy-router/evaluate`
- **目标**：输出 botSelection、workflowVersionSelection、interruptDecision 等结构化决策
- **依赖**：BE-202、BE-102
- **数据落点**：
  - `policy_decision`
- **验收标准**：
  - 至少支持默认 Bot 匹配、基础会话状态路由、基础风控阻断
  - 决策可被审计查询看到

## BE-205 Workflow Run 创建与状态推进
- **优先级**：P0
- **Owner**：运行时后端
- **目标**：创建 `workflow_run`，支持 `pending/running/waiting/completed/failed/interrupted`
- **依赖**：BE-204
- **数据落点**：
  - `workflow_run`
- **验收标准**：
  - 主链路能创建 run 并完成状态推进

## BE-206 Node Execution 轨迹记录
- **优先级**：P0
- **Owner**：运行时后端
- **目标**：每个节点执行都有 `node_execution` 记录
- **依赖**：BE-205
- **数据落点**：
  - `node_execution`
- **验收标准**：
  - 可查询单次 run 的节点执行轨迹

## BE-207 Agent Executor MVP
- **优先级**：P0
- **Owner**：运行时后端
- **对应接口**：`POST /internal/agent-executor/invoke`
- **目标**：对接 LLM 能力并产出结构化结果
- **依赖**：BE-205、BE-206
- **数据落点**：
  - `agent_invocation`
- **验收标准**：
  - 至少支持 2~4 类核心 Agent
  - 超时 / 失败 / 结构不合法时有明确降级与错误记录

## BE-208 Device Command 创建能力
- **优先级**：P0
- **Owner**：运行时后端
- **对应接口**：`POST /api/runtime/device-commands`
- **目标**：把运行时意图转成设备命令事实
- **依赖**：BE-205、BE-207
- **数据落点**：
  - `device_command`
- **验收标准**：
  - 可生成 `pending` 状态命令
  - 与 run、conversation、policyDecision 正确关联

---

# 7.4 设备接入主链路任务

## BE-301 设备鉴权与身份校验
- **优先级**：P0
- **Owner**：设备接入后端
- **目标**：确保设备只能访问自己的命令与回执接口
- **依赖**：BE-001、BE-101
- **验收标准**：
  - 未授权设备请求被拒绝
  - deviceId 与 token 可正确映射

## BE-302 设备拉取待执行命令接口
- **优先级**：P0
- **Owner**：设备接入后端
- **对应接口**：`GET /api/device/commands/pending`
- **依赖**：BE-208、BE-301
- **数据落点**：
  - 读取 `device_command`
- **验收标准**：
  - 设备可拉到自己的待执行命令
  - 返回字段符合 OpenAPI

## BE-303 命令 ACK 回执接口
- **优先级**：P0
- **Owner**：设备接入后端
- **对应接口**：`POST /api/device/commands/{commandId}/ack`
- **依赖**：BE-302
- **数据落点**：
  - 更新 `device_command.status`
- **验收标准**：
  - `pending/sent -> acked` 正常流转
  - 幂等重复 ACK 不会写乱状态

## BE-304 命令完成回执接口
- **优先级**：P0
- **Owner**：设备接入后端 + 运行时后端
- **对应接口**：`POST /api/device/commands/{commandId}/complete`
- **依赖**：BE-303
- **数据落点**：
  - `device_command`
  - `session_runtime`
  - `workflow_run`
- **验收标准**：
  - `acked -> done` 流转正常
  - 回执成功后能推进运行时主状态

## BE-305 命令失败回执接口
- **优先级**：P0
- **Owner**：设备接入后端 + 运行时后端
- **对应接口**：`POST /api/device/commands/{commandId}/fail`
- **依赖**：BE-303
- **数据落点**：
  - `device_command`
  - `session_runtime`
  - `policy_decision`（必要时）
- **验收标准**：
  - 失败原因可被记录
  - 至少支持一种后续动作：重试 / 转人工 / 冻结

---

# 7.5 控制面主链路任务

## BE-401 会话列表接口
- **优先级**：P0
- **Owner**：控制面后端
- **对应接口**：`GET /api/control/conversations`
- **依赖**：BE-202、BE-205、BE-208
- **验收标准**：
  - 支持 projectId 查询
  - 支持 sessionState / handoffStatus 基础过滤
  - 支持最近消息预览

## BE-402 会话详情接口
- **优先级**：P0
- **Owner**：控制面后端
- **对应接口**：`GET /api/control/conversations/{conversationId}`
- **依赖**：BE-202
- **验收标准**：
  - 返回 contact / currentBot / currentWorkflowVersion / ownerType / handoffStatus

## BE-403 会话消息流水接口
- **优先级**：P0
- **Owner**：控制面后端
- **对应接口**：`GET /api/control/conversations/{conversationId}/messages`
- **依赖**：BE-201
- **验收标准**：
  - 支持分页回溯
  - 顺序稳定

## BE-404 当前运行态接口
- **优先级**：P0
- **Owner**：控制面后端
- **对应接口**：`GET /api/control/conversations/{conversationId}/runtime`
- **依赖**：BE-205、BE-208、BE-304、BE-305
- **验收标准**：
  - 返回 `sessionRuntimeId`、`sessionState`、`handoffStatus`、`activeRunId`、`currentBotId`

## BE-405 发起人工接管接口
- **优先级**：P0
- **Owner**：控制面后端 + 运行时后端
- **对应接口**：`POST /api/control/conversations/{conversationId}/handoff`
- **依赖**：BE-205、BE-203
- **数据落点**：
  - `session_runtime`
  - `policy_decision`
  - `handoff_record`（如已建）
- **验收标准**：
  - 接管后 AI 停止主动发送
  - active run 被中断或挂起

## BE-406 交还托管接口
- **优先级**：P0
- **Owner**：控制面后端 + 运行时后端
- **对应接口**：`POST /api/control/conversations/{conversationId}/handoff/return`
- **依赖**：BE-405
- **验收标准**：
  - 支持 `idle / continue / replan`
  - 接口结果与运行态保持一致

---

# 8. P1 任务清单：联调与排障关键项

## BE-501 运行实例详情接口
- **优先级**：P1
- **Owner**：控制面后端
- **接口**：`GET /api/control/workflow-runs/{runId}`
- **价值**：前端调试页、排障必需

## BE-502 节点轨迹接口
- **优先级**：P1
- **Owner**：控制面后端
- **接口**：`GET /api/control/workflow-runs/{runId}/node-executions`
- **价值**：定位卡死节点、失败节点

## BE-503 会话策略决策日志接口
- **优先级**：P1
- **Owner**：控制面后端
- **接口**：`GET /api/control/conversations/{conversationId}/policy-decisions`
- **价值**：看为什么转人工、为什么阻断、为什么选这个 Bot

## BE-504 Agent 调用记录接口
- **优先级**：P1
- **Owner**：控制面后端
- **接口**：`GET /api/control/workflow-runs/{runId}/agent-invocations`
- **价值**：看成本、延迟、失败原因

## BE-505 中断 / 恢复 / 取消 run 接口
- **优先级**：P1
- **Owner**：控制面后端 + 运行时后端
- **接口**：
  - `POST /api/control/workflow-runs/{runId}/interrupt`
  - `POST /api/control/workflow-runs/{runId}/resume`
  - `POST /api/control/workflow-runs/{runId}/cancel`
- **价值**：控制面调试与异常处理

## BE-506 设备心跳接口
- **优先级**：P1
- **Owner**：设备接入后端
- **目标**：设备在线状态可见
- **价值**：提高命令派发可靠性与控制面可见性

## BE-507 第二批增强表落地
- **优先级**：P1
- **Owner**：公共基础 + 控制面后端
- **目标**：补 `handoff_record`、`runtime_event_log`、`device_heartbeat` 等
- **价值**：增强审计与运维可见性

---

# 9. P2 任务清单：第二轮增强项

## BE-601 Supervisor Agent 辅助接口实现
- **优先级**：P2
- **接口**：`POST /internal/agent-executor/supervisor`
- **说明**：只在复杂场景灰度打开，不纳入 MVP 主路径强依赖

## BE-602 策略配置中心增强
- **优先级**：P2
- **说明**：把规则从代码常量逐步迁到配置化管理

## BE-603 设备在线质量评分
- **优先级**：P2
- **说明**：用于后续更智能的派发与降级

## BE-604 运行时事件总线化
- **优先级**：P2
- **说明**：当前可先内聚在服务内，后续再拆到 MQ / 事件流

## BE-605 成本与预算治理
- **优先级**：P2
- **说明**：用于模型调用预算控制、Bot 级消耗治理

---

# 10. 推荐开发顺序（后端视角）

建议严格按下面顺序落地：

## Sprint A：底座与主骨架
- BE-001
- BE-002
- BE-003
- BE-004
- BE-005
- BE-101
- BE-102

### 目标
让服务能启动、库能建、契约能看。

---

## Sprint B：主链路核心运行时
- BE-201
- BE-202
- BE-203
- BE-204
- BE-205
- BE-206
- BE-207
- BE-208

### 目标
让“入站消息 -> 运行编排 -> 命令创建”先跑起来。

---

## Sprint C：设备闭环
- BE-301
- BE-302
- BE-303
- BE-304
- BE-305

### 目标
让“命令下发 -> ACK -> complete / fail”形成闭环。

---

## Sprint D：控制面主查询与接管
- BE-401
- BE-402
- BE-403
- BE-404
- BE-405
- BE-406

### 目标
让运营人员能看到、能接管、能恢复。

---

## Sprint E：调试与排障增强
- BE-501
- BE-502
- BE-503
- BE-504
- BE-505
- BE-506
- BE-507

### 目标
让系统从“能跑”升级到“出问题也能查”。

---

# 11. 后端联调顺序建议

## 联调 1：运行时内部联调
顺序：
- 入站消息
- 会话定位
- Policy Router
- Workflow Run
- Agent Executor
- Device Command 创建

### 联调通过标准
- 不接前端、不接真实设备，也能通过接口跑完前半段

---

## 联调 2：设备链路联调
顺序：
- 设备鉴权
- 拉命令
- ACK
- complete
- fail

### 联调通过标准
- 能通过假设备或模拟器完成完整回执链路

---

## 联调 3：控制面联调
顺序：
- 会话列表
- 会话详情
- 消息流水
- 当前运行态
- 人工接管
- 交还托管

### 联调通过标准
- 前端能完成基本运营操作闭环

---

## 联调 4：调试与审计联调
顺序：
- run 详情
- node_execution
- policy_decision
- agent_invocation

### 联调通过标准
- 一次问题排查不需要直接翻数据库原始表

---

# 12. 后端验收门禁

## 12.1 代码门禁
- migration 必须可回放
- OpenAPI 与实现不能明显漂移
- 公共错误码不能各写各的
- 关键写接口必须支持幂等

## 12.2 功能门禁
- 能接收入站消息
- 能正确定位会话
- 能创建并推进 run
- 能创建并闭环设备命令
- 能人工接管与交还
- 能查运行事实

## 12.3 稳定性门禁
- 并发入站不会把状态写乱
- 重复回执不会破坏状态机
- 离线设备能被识别
- LLM 超时不会拖垮主线程

---

# 13. 研发风险提醒

## 风险 1：控制面先写太多，主链路后补
后果：页面很多，但系统核心链路不稳。

## 风险 2：Agent 能力先铺太多
后果：成本高、调试难、主路径不确定。

## 风险 3：设备接口状态机不严
后果：ACK / done / fail 顺序乱掉，运行态被污染。

## 风险 4：会话锁设计太随意
后果：并发消息时状态错乱，现场会非常难看。

## 风险 5：审计留痕不完整
后果：系统一出错就只能猜。

---

# 14. 最终建议

如果只保留一句最实在的后端建议，那就是：

**先把运行时主链路写扎实，再扩展控制面完整度。**

也就是优先级永远是：

1. 入站消息别丢
2. 会话状态别乱
3. run 能推进
4. 命令能闭环
5. 人工能接管
6. 问题能查出来

只要这 6 件事成立，Morphix 的后端 MVP 就不是 PPT 工程，而是真能跑的系统。

---

# 15. 推荐的下一步

这份后端 backlog 之后，最适合继续产出的有三份：

1. `backlog-前端任务拆解.md`
2. `backlog-设备端任务拆解.md`
3. `plan-MVP实施路线图.md`

如果从团队开工价值看，我建议下一步优先做：

**`backlog-前端任务拆解.md`**

因为现在后端主链路和后端任务已经基本站住了，接下来最自然的就是把控制面前端也拆成同样可执行的任务包。