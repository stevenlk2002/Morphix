# Morphix 总控编排层详细设计

## 1. 设计目标

这份设计文档用于回答一个核心问题：

**在 Morphix 的多项目、多渠道、多机器人、多Agent、多工作流体系里，到底由谁来“总控”？**

结论先说：

- 系统**必须有总控能力**
- 但不建议把总控默认实现成一个每轮必经、自由决策的“总控Agent”
- 更合理的方案是：**确定性编排内核 + 策略路由层 + 可选 Supervisor Agent**

也就是：

**总控能力主要由运行时系统承担，Agent 负责能力执行，Supervisor Agent 只在复杂场景下参与。**

---

## 2. 设计原则

### 2.1 确定性优先
能用规则、状态机、配置、版本引用解决的，不优先交给 LLM 自由判断。

### 2.2 可回放优先
所有关键决策都应可追踪：
- 为什么选这个 Bot
- 为什么调用这个 Agent
- 为什么转人工
- 为什么中断旧流程
- 为什么触发某个运营任务

### 2.3 总控与能力解耦
- 总控负责“谁先做、何时做、做到哪一步”
- Agent 负责“具体怎么做”

### 2.4 风控前置
高风险动作应由策略层、审批、频控、白名单和幂等机制控制，而不是事后兜底。

### 2.5 复杂决策按需升级
不是所有会话都需要 Supervisor Agent。绝大多数链路应由普通工作流和策略路由完成。

---

## 3. 架构结论

我建议采用如下结构：

1. **Session Orchestrator**：总控主调度器
2. **Policy Router**：策略路由器
3. **Workflow Runtime**：工作流运行时
4. **Agent Executor**：Agent 执行器
5. **Supervisor Agent**：复杂场景策略辅助器（可选）
6. **Human Handoff Coordinator**：人工接管协调器
7. **Device Command Gateway**：设备执行网关
8. **Async Event Bus / Job Worker**：异步事件与任务体系

可以把它理解成：

- **Session Orchestrator 是交通警察**
- **Policy Router 是规则裁判**
- **Workflow Runtime 是流水线引擎**
- **Agent Executor 是能力调用层**
- **Supervisor Agent 是专家会诊，不是前台总机**

---

## 4. 核心组件与职责划分

## 4.1 Session Orchestrator

这是系统的一号总控组件，但它不是 Agent。

### 核心职责
- 接受入站会话事件
- 解析当前 `project_id / channel_account_id / conversation_id`
- 查找当前会话绑定的 Bot、WorkflowVersion、托管状态
- 驱动会话状态机推进
- 决定走同步回复、异步分析、人工接管、运营任务或终止流程
- 处理中断、超时、重试和恢复

### 负责的关键问题
- 这条消息该不该进入 AI 托管
- 应该继续旧流程还是新建流程
- 新消息是否打断旧运行
- 当前是否允许继续自动回复
- 设备侧回执失败后是否重试、降级或转人工

### 不应承担的职责
- 不直接生成客户回复内容
- 不承担知识问答细节
- 不做业务规则之外的自由推理

---

## 4.2 Policy Router

这是系统的策略总控层。

### 核心职责
- 根据上下文做路由判断
- 决定允许调用哪些 Agent / 节点 / 渠道动作
- 决定模型等级、超时阈值、成本档位
- 执行风控、频控、黑白名单、灰度策略
- 判断是否需要升级到 Supervisor Agent

### 输入
- 项目配置
- 机器人策略
- 渠道类型
- 客户标签 / 客户阶段
- 当前会话状态
- 最近触达记录
- 风险等级
- 预算与模型策略

### 输出
- `bot_selection`
- `workflow_version_selection`
- `allowed_agent_set`
- `model_profile`
- `risk_policy`
- `handoff_decision`
- `interrupt_decision`
- `supervisor_needed`

### 推荐实现方式
优先采用：
- 规则引擎 + 配置表
- 少量评分模型
- 必要时才引入 LLM 辅助判断

不建议让它从第一天就完全依赖自然语言推理。

---

## 4.3 Workflow Runtime

这是执行面真正的运行内核。

### 核心职责
- 加载 `WorkflowVersion`
- 解析节点输入输出和全局变量
- 维护 `run_context`
- 调度节点执行顺序
- 执行分支判断、循环、等待、子流程
- 管理 node-level retry / timeout / fallback
- 产出结构化执行日志和调试回放数据

### 关键约束
- Workflow Runtime 只关心“流程如何执行”
- Bot、会话、设备、运营等上层语义由 Orchestrator 和 Policy Router 决定

---

## 4.4 Agent Executor

这是 Agent 能力的统一执行层。

### 核心职责
- 根据 Agent 类型构建调用上下文
- 执行 Prompt 装配
- 选择模型 / 工具 / 知识源
- 产出结构化结果
- 报告 token、耗时、置信度、异常信息

### 推荐输出结构
```json
{
  "agent_type": "sales_progress",
  "status": "success",
  "summary": "客户对报价有兴趣，但需进一步确认交付周期",
  "structured_output": {
    "intent": "pricing_followup",
    "stage": "consideration",
    "next_action": "send_case_then_followup_tomorrow"
  },
  "cost": {
    "prompt_tokens": 1200,
    "completion_tokens": 340
  },
  "confidence": 0.81
}
```

### 关键边界
Agent Executor 只负责“调用并返回结果”，不负责决定整体流程下一步。

---

## 4.5 Supervisor Agent（可选）

它不是默认总控，而是复杂决策辅助器。

### 适合介入的场景
- 高价值客户的多步推进策略
- 多个执行方案之间的权衡
- 复杂会话阶段判断不明确
- 多Agent结果冲突需要综合裁决
- 异常恢复需要策略建议

### 不适合介入的场景
- 每条普通消息
- 简单 FAQ
- 固定 SOP
- 可被规则明确覆盖的路由判断

### 设计建议
- 只接受结构化上下文输入
- 输出结构化建议，而不是直接接管整个会话
- 最终是否采纳其建议，仍由 Policy Router / Orchestrator 决定

---

## 4.6 Human Handoff Coordinator

### 核心职责
- 控制转人工、人工接管、人工交还
- 管理自动托管冻结窗口
- 防止 AI 与人工并发回复冲突
- 记录人工接管原因、开始时间、结束时间

### 关键规则
- 人工接管期间，AI 不得继续主动发言
- 人工交还后，应恢复到明确状态，而不是让旧运行盲目续跑
- 接管与交还都应形成审计事件

---

## 4.7 Device Command Gateway

### 核心职责
- 统一封装设备侧执行指令
- 保证命令幂等与回执追踪
- 对接不同渠道/设备能力差异
- 支持失败重试、补偿、超时回滚

### 指令示例
- `send_message`
- `send_image`
- `fetch_contacts`
- `sync_group_members`
- `set_conversation_tag`
- `pause_hosting`

---

## 5. 建议的数据与对象模型

## 5.1 SessionRuntime
描述某个会话当前的实时运行状态。

建议字段：
- `conversation_id`
- `project_id`
- `channel_account_id`
- `current_bot_id`
- `current_workflow_version_id`
- `hosting_status`
- `session_state`
- `active_run_id`
- `waiting_node_id`
- `last_message_at`
- `interruption_policy`
- `handoff_status`

## 5.2 WorkflowRun
描述一次工作流执行实例。

建议字段：
- `run_id`
- `workflow_version_id`
- `trigger_type`（message / campaign / manual / system）
- `status`
- `started_at`
- `ended_at`
- `parent_run_id`
- `conversation_id`
- `context_snapshot`
- `result_summary`

## 5.3 NodeExecution
描述单个节点执行记录。

建议字段：
- `node_execution_id`
- `run_id`
- `node_id`
- `node_type`
- `status`
- `input_snapshot`
- `output_snapshot`
- `retry_count`
- `duration_ms`
- `error_code`

## 5.4 PolicyDecision
描述一次策略决策。

建议字段：
- `decision_id`
- `conversation_id`
- `decision_type`
- `decision_source`（rule / model / supervisor / human）
- `decision_payload`
- `reason_codes`
- `created_at`

## 5.5 AgentInvocation
描述一次 Agent 调用。

建议字段：
- `invocation_id`
- `run_id`
- `agent_type`
- `model_name`
- `input_digest`
- `output_digest`
- `confidence`
- `latency_ms`
- `token_cost`
- `status`

## 5.6 DeviceCommand
描述一次设备执行命令。

建议字段：
- `command_id`
- `device_id`
- `channel_account_id`
- `command_type`
- `payload`
- `idempotency_key`
- `status`
- `issued_at`
- `ack_at`
- `done_at`
- `failure_reason`

---

## 6. 会话状态机设计

建议把“会话状态”和“工作流运行状态”拆开，绝对不要揉成一个字段。

## 6.1 会话状态（Session State）

建议状态：
- `IDLE`：空闲，无运行中托管动作
- `AUTO_HOSTING`：AI 托管中
- `WAITING_USER`：等待用户输入
- `WAITING_TIMER`：等待定时器/触发器
- `WAITING_DEVICE_ACK`：等待设备执行回执
- `HUMAN_HANDOFF`：人工接管中
- `PAUSED_BY_POLICY`：被策略冻结
- `ERROR_REVIEW`：异常待处理
- `CLOSED`：会话关闭或归档

## 6.2 工作流运行状态（Run State）

建议状态：
- `PENDING`
- `RUNNING`
- `WAITING`
- `INTERRUPTED`
- `FAILED`
- `CANCELLED`
- `COMPLETED`

## 6.3 关键原则
- 一个会话在任一时刻最多只有一个 `active_run`
- 新消息到来时，是否打断旧运行由 `interrupt_policy` 决定
- `HUMAN_HANDOFF` 不等于 `RUNNING=false`，而是会话主控制权发生切换
- `WAITING_DEVICE_ACK` 只表示动作未完成，不代表回复内容还未生成

---

## 7. 决策流设计

建议把总控链路收敛为固定决策流：

1. 接收到事件
2. 标准化事件模型
3. 加载 SessionRuntime
4. Policy Router 做准入与路由判断
5. Session Orchestrator 决定是否新建/续跑/中断 run
6. Workflow Runtime 执行节点
7. 遇到 Agent 节点时调用 Agent Executor
8. 遇到高复杂度场景时再调用 Supervisor Agent
9. 输出渠道动作后交给 Device Command Gateway
10. 接收回执，更新状态并决定后续动作

### 7.1 什么时候必须经过 Policy Router
- 每次新会话开始
- 每次新消息进入且可能改变意图
- 每次主动运营任务发起前
- 每次准备调用高成本模型前
- 每次准备执行高风险渠道动作前

### 7.2 什么时候可以跳过 Supervisor Agent
- FAQ 类回复
- 固定话术补全
- 普通阶段推进
- 标签抽取
- 规则已足够清晰的运营动作

### 7.3 什么时候触发 Supervisor Agent
满足任意一条即可考虑触发：
- `policy_complexity_score >= threshold`
- 多个 Agent 输出冲突
- 客户价值等级高
- 风险与收益同时较高
- 当前流程连续失败，需要恢复策略

---

## 8. Bot、Workflow、Agent 三者关系

建议明确这三个对象的边界：

## 8.1 Bot
面向业务交付。

定义内容：
- 业务角色
- 默认话术风格
- 默认工作流版本引用
- 可用知识资产
- 渠道适配配置
- 风险与审批策略

## 8.2 WorkflowVersion
面向流程执行。

定义内容：
- 节点图
- 输入输出约束
- 子流程引用
- 发布版本
- 默认中断策略
- 运行时变量需求

## 8.3 Agent
面向能力编排。

定义内容：
- 能力类型
- Prompt 模板
- 模型选择策略
- 输入输出结构
- 工具/知识源依赖
- 观测指标

### 一句话边界
- **Bot 决定对外交付什么能力**
- **WorkflowVersion 决定流程怎么跑**
- **Agent 决定某个能力节点怎么做**

---

## 9. 成本与性能控制策略

这是总控层必须承担的职责之一。

## 9.1 模型分层
建议至少分三档：
- `economy`：常规分类、抽取、标准问答
- `standard`：普通销售推进、多轮回复
- `premium`：复杂策略分析、Supervisor Agent、关键高价值客户

## 9.2 调用削峰
- 同一会话短时间内多消息合并
- 离线标签分析异步化
- 高耗时节点支持降级
- 大模型失败时允许 fallback 到轻模型或规则模板

## 9.3 预算约束
Policy Router 应能读取：
- 项目预算上限
- Bot 每日 token 配额
- 单会话最大成本
- 单客户高价值豁免策略

---

## 10. 风控与治理要求

## 10.1 风控不能只靠提示词
必须有系统级约束：
- 每账号触达频率限制
- 每客户触达冷却时间
- 高风险动作审批或二次确认
- 敏感词与敏感场景拦截
- 设备离线或异常时强制暂停自动托管

## 10.2 审计要求
每次关键决策都要落审计：
- 为什么选这个 Bot
- 为什么触发这个 Agent
- 为什么切换人工
- 为什么调用高档模型
- 为什么中断旧流程

## 10.3 可观测性要求
至少记录：
- 会话级耗时
- 节点级耗时
- Agent 调用耗时与成本
- 设备回执成功率
- 人工接管率
- 中断率
- Supervisor Agent 触发率

---

## 11. MVP 落地建议

MVP 阶段不要一步做满。

## 11.1 第一阶段必须做的
- Session Orchestrator
- Policy Router（规则版）
- Workflow Runtime
- Agent Executor
- Human Handoff Coordinator
- Device Command Gateway
- 会话状态机 + 运行状态机
- 调试回放与审计日志

## 11.2 第一阶段可以不做满的
- Supervisor Agent
- 动态多模型预算优化
- 自动策略评分器
- 自学习路由
- 多层级审批流

## 11.3 MVP 推荐策略
- 先用**规则驱动总控**跑通核心链路
- Agent 先做成强约束、结构化输入输出
- Supervisor Agent 只在人工指定或高价值会话里灰度开启

---

## 12. Phase 2 演进方向

当系统从 1000 账号继续往上走时，再逐步增强：
- 更细粒度的 Policy Router
- 项目级与 Bot 级预算系统
- Supervisor Agent 作为复杂策略中枢
- 多区域设备调度
- 自适应中断策略
- 更强的实验与 A/B 路由框架

---

## 13. 最终建议

如果只保留一句架构建议，那就是：

**Morphix 需要总控，但应该优先建设“总控编排层”，而不是直接押注“总控Agent”。**

更具体一点：

- **Session Orchestrator** 负责会话级主调度
- **Policy Router** 负责策略、风控、预算、路由
- **Workflow Runtime** 负责确定性流程执行
- **Agent Executor** 负责能力节点调用
- **Supervisor Agent** 只在复杂场景中作为增强器参与

这样做的收益是：
- 架构更稳
- 成本更可控
- 调试更容易
- 风控更可靠
- 后续也更容易从 1000 账号阶段演进到更大规模
