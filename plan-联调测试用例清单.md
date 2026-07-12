# Morphix 联调测试用例清单

## 1. 文档目标

这份清单把前面已经收敛出来的架构、OpenAPI、三端 backlog 和里程碑门禁，进一步落成**可直接拿来排联调、写用例、过门禁**的测试基线。

它要解决的不是“功能有没有”，而是：

- 主链路在跨团队联调时是否真的闭环
- 每个失败场景是否都有补偿闭环（回执 / 兜底 / 人工接管）
- 状态机、幂等、审计是否在异常下仍然可信
- M1~M5 与联调 1~5 的每一个门禁是否有可验证证据

一句话：

**这份文档让 Morphix 的联调从“大家各自测接口”变成“围绕同一条主链路验证据”。**

---

## 2. 联调范围

### 2.1 在范围内

围绕主链路：

`入站消息 -> 编排执行 -> 命令下发 -> 设备回执 -> 人工接管 -> 运行态与审计`

覆盖：

- 控制面 API：会话、运行态、工作流运行、人工接管、决策与 Agent 审计
- 执行面 API：设备命令创建
- 设备接入 API：注册绑定、令牌刷新、心跳、拉命令、ACK/complete/fail、入站消息直报、联系人/群同步、诊断上报
- 内部编排 API：Policy Router、Agent Executor、Supervisor Agent
- 异常、边界、幂等、安全鉴权

### 2.2 不在本清单首轮范围

以下建议单独Plan，不混入主链路联调，避免范围发散：

- UI 视觉与交互细节验收
- 性能压测、容量评估
- 安全渗透测试
- 多项目租户隔离的完整压测

---

## 3. 联调原则

1. **每个失败用例必须验证补偿闭环**：不能只测“报错”，要测“报错后系统是否回到可信状态”。
2. **幂等必须实测**：同一 `sourceMessageId`、同一 `commandId` 的重复请求必须验证 no-op。
3. **设备离线必须验证恢复**：命令可重投、回执可补传、状态不能脏。
4. **审计必须可回放**：一条链路至少能串起 `message / session_runtime / workflow_run / policy_decision / device_command / node_execution / agent_invocation`。
5. **requestId 必须贯穿**：所有跨服务调用都要能用一个 requestId 串起来。
6. **控制面与运行时必须一致**：控制台看到的状态必须等于数据库事实。

---

## 4. 接口索引

### 4.1 控制面 / 执行面 / 内部编排

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/runtime/inbound-events/messages` | 上报入站消息 |
| GET | `/api/runtime/inbound-events/{requestId}` | 查询入站事件处理结果 |
| GET | `/api/control/conversations` | 查询会话列表 |
| GET | `/api/control/conversations/{conversationId}` | 查询会话详情 |
| GET | `/api/control/conversations/{conversationId}/messages` | 查询会话消息流水 |
| GET | `/api/control/conversations/{conversationId}/runtime` | 查询当前运行态 |
| POST | `/api/control/conversations/{conversationId}/handoff` | 发起人工接管 |
| POST | `/api/control/conversations/{conversationId}/handoff/return` | 交还托管 |
| GET | `/api/control/conversations/{conversationId}/policy-decisions` | 查询会话决策日志 |
| POST | `/api/control/workflow-runs` | 手动启动工作流运行 |
| GET | `/api/control/workflow-runs/{runId}` | 查询运行实例详情 |
| GET | `/api/control/workflow-runs/{runId}/node-executions` | 查询运行实例节点轨迹 |
| POST | `/api/control/workflow-runs/{runId}/interrupt` | 中断运行实例 |
| POST | `/api/control/workflow-runs/{runId}/resume` | 恢复运行实例 |
| POST | `/api/control/workflow-runs/{runId}/cancel` | 取消运行实例 |
| GET | `/api/control/workflow-runs/{runId}/policy-decisions` | 查询单次运行的策略决策 |
| GET | `/api/control/workflow-runs/{runId}/agent-invocations` | 查询 Agent 调用记录 |
| POST | `/api/runtime/device-commands` | 创建设备命令 |
| GET | `/api/device/commands/pending` | 设备拉取待执行命令 |
| POST | `/api/device/commands/{commandId}/ack` | 上报设备命令 ACK |
| POST | `/api/device/commands/{commandId}/complete` | 上报设备命令完成回执 |
| POST | `/api/device/commands/{commandId}/fail` | 上报设备命令失败回执 |
| POST | `/api/internal/policy/route` | Orchestrator 请求策略路由 |
| POST | `/api/internal/agent/invoke` | Runtime 请求 Agent 执行 |
| POST | `/api/internal/supervisor/invoke` | Runtime 请求 Supervisor Agent 辅助决策 |

### 4.2 设备接入补充契约

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/device/registrations` | 注册并绑定设备 |
| POST | `/api/device/registrations/{deviceId}/refresh-token` | 刷新设备令牌 |
| POST | `/api/device/heartbeats` | 上报设备心跳 |
| POST | `/api/device/inbound-messages` | 设备直接上报入站消息 |
| POST | `/api/device/contact-sync/batches` | 上报联系人同步批次 |
| POST | `/api/device/group-sync/batches` | 上报群聊同步批次 |
| POST | `/api/device/diagnostics/log-batches` | 上报诊断日志批次 |
| POST | `/api/device/diagnostics/snapshots` | 上报设备运行快照 |

---

## 5. 测试用例总览

| 用例ID | 标题 | 分组 | 优先级 | 关联门禁 |
|---|---|---|---|---|
| TC-A01 | 单聊入站消息完整主链路 | A 主链路 | P0 | 联调1、M2、M3 |
| TC-A02 | 群聊入站消息会话定位 | A 主链路 | P0 | M2 |
| TC-A03 | 多轮会话状态持续推进 | A 主链路 | P0 | M2、M3 |
| TC-B01 | 会话列表查询 | B 控制面 | P0 | M4、联调3 |
| TC-B02 | 会话详情与消息流水 | B 控制面 | P0 | M4 |
| TC-B03 | 当前运行态查询 | B 控制面 | P0 | M4 |
| TC-B04 | 工作流运行详情与节点轨迹 | B 控制面 | P0 | M4、联调4 |
| TC-B05 | 会话策略决策日志查询 | B 控制面 | P1 | 联调4 |
| TC-B06 | Agent 调用记录查询 | B 控制面 | P1 | 联调4 |
| TC-B07 | 手动启动工作流运行 | B 控制面 | P1 | M2 |
| TC-B08 | 中断/恢复/取消运行实例 | B 控制面 | P1 | M2 |
| TC-C01 | 设备注册并绑定 | C 设备接入 | P0 | M3 |
| TC-C02 | 设备令牌刷新 | C 设备接入 | P0 | M3 |
| TC-C03 | 设备心跳上报 | C 设备接入 | P0 | M3 |
| TC-C04 | 设备拉取待执行命令 | C 设备接入 | P0 | 联调2、M3 |
| TC-C05 | 命令 ACK 回执 | C 设备接入 | P0 | 联调2、M3 |
| TC-C06 | 命令 complete 驱动状态推进 | C 设备接入 | P0 | 联调2、M3 |
| TC-C07 | 命令 fail 结构化失败 | C 设备接入 | P0 | M3、M5 |
| TC-C08 | 设备直接上报入站消息 | C 设备接入 | P0 | M2 |
| TC-C09 | 联系人同步批次上报 | C 设备接入 | P1 | M5 |
| TC-C10 | 群聊同步批次上报 | C 设备接入 | P1 | M5 |
| TC-C11 | 诊断日志与运行快照上报 | C 设备接入 | P1 | M3、M5 |
| TC-D01 | 发起人工接管 | D 接管 | P0 | M3、M4 |
| TC-D02 | 人工接管后设备停止主动动作 | D 接管 | P0 | M3、P0阻塞项5 |
| TC-D03 | 交还托管恢复自动运行 | D 接管 | P0 | M4 |
| TC-D04 | 接管期间新消息不触发自动发送 | D 接管 | P0 | P0阻塞项5 |
| TC-E01 | 入站消息重复提交幂等 | E 异常 | P0 | M2、P0阻塞项1 |
| TC-E02 | 设备命令重复 ACK/complete/fail | E 异常 | P0 | M3、P0阻塞项4 |
| TC-E03 | 设备离线后命令重投 | E 异常 | P0 | M3、M5 |
| TC-E04 | 设备断网恢复后回执补传 | E 异常 | P0 | M3、P0阻塞项4 |
| TC-E05 | LLM / Agent 超时兜底 | E 异常 | P0 | M5 |
| TC-E06 | 知识库 / 外部依赖超时 | E 异常 | P1 | M5 |
| TC-E07 | 命令执行失败进入人工兜底 | E 异常 | P0 | M5、P0阻塞项5 |
| TC-E08 | 运行中新消息打断策略 | E 异常 | P1 | M2 |
| TC-E09 | 并发人工接管冲突 | E 异常 | P0 | M4 |
| TC-F01 | 未带鉴权访问被拒 | F 安全 | P0 | M1 |
| TC-F02 | 设备令牌无效被拒 | F 安全 | P0 | M3 |
| TC-F03 | 越权访问他人会话被拒 | F 安全 | P0 | M4 |
| TC-F04 | 幂等 Header 正确使用 | F 安全 | P1 | M1 |
| TC-G01 | M1 开发基线冻结验收 | G 门禁 | P0 | M1 |
| TC-G02 | M2 运行时命令可生成验收 | G 门禁 | P0 | M2 |
| TC-G03 | M3 设备回执闭环验收 | G 门禁 | P0 | M3 |
| TC-G04 | M4 控制台可操作验收 | G 门禁 | P0 | M4 |
| TC-G05 | M5 小流量灰度就绪验收 | G 门禁 | P0 | M5 |

---

## 6. 详细用例

### A. 主链路 E2E

#### TC-A01 单聊入站消息完整主链路

- **目标**：验证一条单聊入站消息能从上报走到设备命令回执，并形成完整审计链。
- **接口**：
  - `POST /api/runtime/inbound-events/messages`
  - `POST /api/runtime/device-commands`
  - `GET /api/device/commands/pending`
  - `POST /api/device/commands/{commandId}/ack`
  - `POST /api/device/commands/{commandId}/complete`
  - `GET /api/control/conversations/{conversationId}/runtime`
- **前置**：
  - 已存在项目、渠道账号、绑定 Bot、WorkflowVersion。
  - 设备已完成注册绑定并在线。
  - Policy Router 有可用路由规则。
- **步骤**：
  1. 设备通过 `POST /api/device/inbound-messages` 或上游通道上报一条客户单聊消息。
  2. 服务端定位 / 创建 `conversation` 与 `session_runtime`。
  3. Policy Router 输出决策，运行时创建 `workflow_run`。
  4. 运行时节点产生一条发消息动作，服务端创建 `device_command`。
  5. 设备拉取 pending 命令并 ACK。
  6. 设备执行完成并上报 complete。
  7. 查询会话运行态。
- **期望**：
  - `device_command` 状态经历 `created -> acked -> completed`。
  - `session_runtime` 与 `workflow_run` 状态推进到完成态。
  - 同一 `requestId` 可串联 message、session_runtime、workflow_run、policy_decision、device_command。
  - 控制台运行态与数据库事实一致。

#### TC-A02 群聊入站消息会话定位

- **目标**：验证群聊消息能正确定位群会话，而不是错误并入单聊。
- **接口**：`POST /api/runtime/inbound-events/messages`，`GET /api/control/conversations`
- **前置**：群会话已存在或可被创建。
- **步骤**：
  1. 上报一条带群 ID 的入站消息。
  2. 查询会话列表，过滤群类型会话。
- **期望**：
  - 消息进入正确的群 `conversation`。
  - 不污染同账号下的单聊会话。
  - 会话类型、群 ID、渠道账号映射正确。

#### TC-A03 多轮会话状态持续推进

- **目标**：验证同一会话多轮消息不会重复创建脏 run，且状态持续向前。
- **接口**：`POST /api/runtime/inbound-events/messages`，`GET /api/control/conversations/{conversationId}/runtime`
- **前置**：TC-A01 已通过。
- **步骤**：
  1. 同一会话连续上报 3 条客户消息。
  2. 每条消息触发编排后查询运行态。
- **期望**：
  - 会话状态按业务定义推进，不出现重复 run 或状态回退。
  - 每轮消息都有独立可追踪事实，但会话主线清晰。

---

### B. 控制面

#### TC-B01 会话列表查询

- **目标**：验证控制台可按项目、账号、状态查询会话。
- **接口**：`GET /api/control/conversations`
- **步骤**：
  1. 使用项目 ID、渠道账号 ID、状态过滤查询。
  2. 翻页查询。
- **期望**：
  - 返回结果与过滤条件一致。
  - 分页参数生效。
  - 空态、错误态有统一结构。

#### TC-B02 会话详情与消息流水

- **目标**：验证会话详情和消息流水可被运营查看。
- **接口**：`GET /api/control/conversations/{conversationId}`，`GET .../messages`
- **期望**：消息时间序正确，客户消息与系统动作可区分。

#### TC-B03 当前运行态查询

- **目标**：验证运营能实时看到当前运行态。
- **接口**：`GET /api/control/conversations/{conversationId}/runtime`
- **期望**：运行态字段完整，且与数据库一致。

#### TC-B04 工作流运行详情与节点轨迹

- **目标**：验证排障时能查看 run 和节点轨迹。
- **接口**：`GET /api/control/workflow-runs/{runId}`，`GET .../node-executions`
- **期望**：节点顺序、输入、输出、耗时、状态可见。

#### TC-B05 会话策略决策日志查询

- **目标**：验证 Policy Router 决策可审计。
- **接口**：`GET /api/control/conversations/{conversationId}/policy-decisions`
- **期望**：每次路由决策可还原，包含触发条件与结果。

#### TC-B06 Agent 调用记录查询

- **目标**：验证 Agent 调用可审计。
- **接口**：`GET /api/control/workflow-runs/{runId}/agent-invocations`
- **期望**：Agent 类型、输入、输出、耗时、状态可见。

#### TC-B07 手动启动工作流运行

- **目标**：验证运营可手动触发工作流。
- **接口**：`POST /api/control/workflow-runs`
- **期望**：run 创建成功，状态推进符合定义。

#### TC-B08 中断 / 恢复 / 取消运行实例

- **目标**：验证运行实例三种控制动作均生效。
- **接口**：`POST .../interrupt`，`POST .../resume`，`POST .../cancel`
- **期望**：
  - 中断后不再继续自动动作。
  - 恢复后从断点继续。
  - 取消后进入终态且可审计。

---

### C. 设备接入

#### TC-C01 设备注册并绑定

- **目标**：验证设备进入系统并拿到有效身份。
- **接口**：`POST /api/device/registrations`
- **前置**：设备已有渠道账号绑定关系。
- **步骤**：
  1. 提交设备注册请求，包含设备指纹、渠道账号、绑定凭证。
  2. 服务端返回设备 ID 与初始令牌。
- **期望**：
  - 设备状态为已绑定 / 待在线。
  - 返回令牌可用于后续心跳与命令拉取。

#### TC-C02 设备令牌刷新

- **目标**：验证令牌过期后可刷新。
- **接口**：`POST /api/device/registrations/{deviceId}/refresh-token`
- **步骤**：
  1. 使用旧令牌刷新。
  2. 使用新令牌访问受保护接口。
- **期望**：旧令牌失效，新令牌可用。

#### TC-C03 设备心跳上报

- **目标**：验证设备在线状态可感知。
- **接口**：`POST /api/device/heartbeats`
- **步骤**：定时上报心跳。
- **期望**：设备在线状态、最近心跳时间更新。

#### TC-C04 设备拉取待执行命令

- **目标**：验证设备只拉到属于自己的命令。
- **接口**：`GET /api/device/commands/pending`
- **步骤**：设备上报心跳后拉命令。
- **期望**：只返回绑定该设备的 pending 命令，状态变为已下发。

#### TC-C05 命令 ACK 回执

- **目标**：验证设备收到命令后 ACK。
- **接口**：`POST /api/device/commands/{commandId}/ack`
- **期望**：命令状态进入 `acked`，不影响最终业务状态。

#### TC-C06 命令 complete 驱动状态推进

- **目标**：验证设备执行完成后，run / session 状态推进。
- **接口**：`POST /api/device/commands/{commandId}/complete`
- **前置**：TC-C05 已通过。
- **期望**：
  - 命令进入 `completed`。
  - 关联 `workflow_run` / `session_runtime` 状态向前推进。
  - 如为最后节点，会话进入预期终态。

#### TC-C07 命令 fail 结构化失败

- **目标**：验证设备失败回执可记录并触发兜底。
- **接口**：`POST /api/device/commands/{commandId}/fail`
- **期望**：
  - 命令进入 `failed`，失败原因结构化落库。
  - 运行时进入兜底路径，不卡死。

#### TC-C08 设备直接上报入站消息

- **目标**：验证设备可作为入站消息来源。
- **接口**：`POST /api/device/inbound-messages`
- **期望**：消息进入与 `POST /api/runtime/inbound-events/messages` 相同主链路。

#### TC-C09 联系人同步批次上报

- **目标**：验证联系人同步不阻塞主链路。
- **接口**：`POST /api/device/contact-sync/batches`
- **期望**：批次接受成功，联系人增量入库，错误行可定位。

#### TC-C10 群聊同步批次上报

- **目标**：验证群同步不阻塞主链路。
- **接口**：`POST /api/device/group-sync/batches`
- **期望**：群与成员关系增量更新。

#### TC-C11 诊断日志与运行快照上报

- **目标**：验证设备可辅助排障。
- **接口**：`POST /api/device/diagnostics/log-batches`，`POST /api/device/diagnostics/snapshots`
- **期望**：最近心跳、最近错误、运行快照可在诊断视图查看。

---

### D. 人工接管与交还

#### TC-D01 发起人工接管

- **目标**：验证运营可接管会话。
- **接口**：`POST /api/control/conversations/{conversationId}/handoff`
- **期望**：会话进入人工接管态，后续自动动作受控。

#### TC-D02 人工接管后设备停止主动动作

- **目标**：验证接管后系统不再自动发送。
- **接口**：接管后观察 `GET /api/device/commands/pending`
- **期望**：不产生新的主动发消息命令。
- **关联**：P0 阻塞项 5。

#### TC-D03 交还托管恢复自动运行

- **目标**：验证交还后系统恢复自动运行。
- **接口**：`POST .../handoff/return`
- **期望**：会话回到自动托管态，新消息可触发编排。

#### TC-D04 接管期间新消息不触发自动发送

- **目标**：验证接管边界严格。
- **步骤**：接管后上报新客户消息。
- **期望**：仅进入人工处理队列，不自动回复、不自动主动动作。

#### TC-D05 并发人工接管冲突

- **目标**：验证两个运营同时接管不出现双写。
- **步骤**：并发调用 handoff。
- **期望**：只有一个成功接管，另一个得到明确冲突结果；状态机不脏。

---

### E. 异常与边界

#### TC-E01 入站消息重复提交幂等

- **目标**：同一 `sourceMessageId` 重复提交不重复入链。
- **步骤**：同一消息提交两次。
- **期望**：第二次返回已处理结果或 no-op，不创建第二个 run。
- **关联**：P0 阻塞项 1、M2。

#### TC-E02 设备命令重复 ACK/complete/fail

- **目标**：重复回执不破坏状态机。
- **步骤**：同一 commandId 重复提交 ACK、complete、fail。
- **期望**：第二次及之后为 no-op，状态只前进一次。
- **关联**：P0 阻塞项 4、M3。

#### TC-E03 设备离线后命令重投

- **目标**：设备离线时命令不下发或可被重投。
- **步骤**：设备离线后创建命令，恢复后拉命令。
- **期望**：恢复后设备能拉到未完成命令，不丢失。

#### TC-E04 设备断网恢复后回执补传

- **目标**：断网期间产生的回执恢复后可补传。
- **步骤**：设备先断网执行，再恢复上报 ACK/complete。
- **期望**：回执成功，状态正确推进，无脏数据。
- **关联**：P0 阻塞项 4。

#### TC-E05 LLM / Agent 超时兜底

- **目标**：Agent 调用超时不影响主链路崩溃。
- **步骤**：Mock Agent 超时。
- **期望**：运行时进入兜底，记录失败，可转人工。
- **关联**：M5。

#### TC-E06 知识库 / 外部依赖超时

- **目标**：外部依赖超时不影响系统稳定。
- **步骤**：Mock 知识库超时。
- **期望**：使用降级内容或兜底话术，错误可追溯。

#### TC-E07 命令执行失败进入人工兜底

- **目标**：设备 fail 后系统可切人工。
- **步骤**：设备上报 fail。
- **期望**：运行时进入人工兜底路径，运营可见待处理项。
- **关联**：P0 阻塞项 5、M5。

#### TC-E08 运行中新消息打断策略

- **目标**：运行状态下的新消息按策略处理。
- **步骤**：run 进行中上报新消息。
- **期望**：按 `MERGE_WINDOW` / `INTERRUPT_AND_REPLAN` 规则处理，不脏状态。

#### TC-E09 并发人工接管冲突

- 同 TC-D05，纳入异常组以强调状态机一致性。

---

### F. 安全与鉴权

#### TC-F01 未带鉴权访问被拒

- **目标**：未带 token 访问受保护接口返回 401。
- **步骤**：无 Header 调用 `GET /api/control/conversations`。
- **期望**：401，不泄露内部错误。

#### TC-F02 设备令牌无效被拒

- **目标**：无效设备令牌不能拉命令。
- **步骤**：使用伪造令牌访问 `GET /api/device/commands/pending`。
- **期望**：401 / 403，设备不进入正常链路。

#### TC-F03 越权访问他人会话被拒

- **目标**：跨项目 / 跨账号访问被拒。
- **步骤**：A 项目运营访问 B 项目会话。
- **期望**：403，不返回数据。

#### TC-F04 幂等 Header 正确使用

- **目标**：客户端幂等 Header 被服务端识别。
- **步骤**：同一请求带相同幂等 Key 提交两次。
- **期望**：第二次返回首次结果或 no-op。

---

### G. 里程碑验收用例

#### TC-G01 M1 开发基线冻结验收

- **检查项**：
  - 三端工程骨架已入库。
  - `.env.example`、本地运行方式、依赖说明完整。
  - PostgreSQL / Redis 可拉起。
  - 两份 OpenAPI 可预览、可校验。
  - requestId、统一错误结构、幂等等基础约定冻结。

#### TC-G02 M2 运行时命令可生成验收

- **检查项**：
  - `POST /api/runtime/inbound-events/messages` 可接收校验。
  - 同 `sourceMessageId` 不重复入链。
  - 会话定位 / 创建成立。
  - `session_runtime`、`workflow_run`、`device_command` 可创建并落库。
  - 关键事实对象可追溯。

#### TC-G03 M3 设备回执闭环验收

- **检查项**：
  - 设备注册绑定、心跳、拉命令、ACK、complete、fail 全部实测通过。
  - 重复回执 no-op。
  - 断网恢复后回执可补传。
  - 人工接管后设备不继续主动动作。

#### TC-G04 M4 控制台可操作验收

- **检查项**：
  - 会话列表、详情、消息流水、运行态可见。
  - 人工接管 / 交还可驱动真实状态变化。
  - run / 节点 / 决策 / Agent 调用可查。
  - 关键错误有统一反馈。
  - 控制台与数据库事实一致。

#### TC-G05 M5 小流量灰度就绪验收

- **检查项**：
  - 真实样本链路跑通。
  - 至少一轮错误演练：设备离线、回执失败、人工接管、命令失败。
  - 关键指标可看：入站处理成功率、ACK 成功率、complete/fail 比率、设备在线率、人工接管触发率。
  - 至少 4 个控制开关：停用 Bot、冻结设备、限制会话范围、强制转人工。
  - 回滚方案与停止灰度方案明确。

---

## 7. 用例模板

后续新增用例建议统一字段：

| 字段 | 说明 |
|---|---|
| 用例ID | 如 TC-A01 |
| 标题 | 一句话说明测什么 |
| 分组 | A/B/C/D/E/F/G |
| 优先级 | P0 / P1 |
| 接口 | 涉及的主要 API |
| 前置 | 需要什么数据 / 状态 |
| 步骤 | 操作序列 |
| 期望 | 可验证结果 |
| 关联门禁 | M1~M5 / 联调1~5 / P0阻塞项 |
| 类型 | 功能 / 异常 / 安全 / 验收 |

---

## 8. 联调顺序建议

1. **联调1 后端内部主链路门**：TC-A01、TC-B07、TC-E01
2. **联调2 设备闭环门**：TC-C01~TC-C08、TC-E02、TC-E03、TC-E04
3. **联调3 控制台查询门**：TC-B01~TC-B06、TC-D01~TC-D04
4. **联调4 调试审计门**：TC-B04、TC-B05、TC-B06、TC-E05
5. **联调5 真实业务样本门**：TC-G05、TC-E07、TC-F03

建议先打通联调1 和联调2，再开联调3 与联调4；联调5 只在 M4 通过后才做。

---

## 9. 缺陷定级建议

直接复用《plan-里程碑与验收门禁.md》的 P0 阻塞项作为联调缺陷红线：

1. 同一入站消息无法稳定去重
2. `workflow_run` 无法创建或状态不可信
3. `device_command` 能创建但设备无法稳定拉取
4. ACK / complete / fail 回执会破坏状态机
5. 人工接管后系统仍继续自动主动发送
6. 控制台无法定位运行态或审计事实缺失
7. 灰度时没有停用 Bot / 冻结设备 / 转人工开关
8. 关键错误无 requestId、无日志、无可追踪事实

出现以上任一情况，联调不得宣布通过，必须回到对应失败用例补齐补偿闭环。

---

## 10. 后续建议

这份清单落地后，建议下一步补两份可直接执行的产物：

1. **Postman / Bruno 集合**：把 P0 用例参数化，联调时一键跑。
2. **自动化联调脚本**：用一份种子数据驱动 TC-A01、TC-C04~TC-C07、TC-D01~TC-D03，作为每日联调回归。
