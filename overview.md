# 本次完成：原型驱动需求理解与初步架构建议

## 做了什么
- 通读并交叉理解了原型 `prototype/index.html`、多项目 PRD、无代码编排 PRD、系统架构设计、节点与流程规范、数据库设计、默认全局变量以及节点类型图。
- 以原型为需求核心，提炼出 Morphix 的真实产品结构、核心业务闭环、领域边界与初期架构方向。
- 产出《`report-原型驱动需求理解与初步架构建议.md`》作为后续架构设计的共识基线。

## 关键判断
- 这不是单纯的聊天机器人后台，而是“多项目 + 多渠道 + 多账号 + 多Agent + 无代码编排 + 运营任务”的私域运营执行平台。
- 无代码编排是核心引擎，但不是全部产品；产品还包含渠道托管、客户管理、运营SOP、数据面板、组织权限等完整控制面。
- 手机端需要区分两类：
  - 运营人员使用的移动管理端
  - 设备执行侧的独立手机 App（真正负责收发消息、采集联系人/群/动态、执行服务端指令）
- 初期更适合采用“模块化单体控制面 + 独立执行组件 + 独立设备接入层”的混合架构，而不是一开始全微服务。

## 后续建议
- 下一步优先补：领域架构图、核心数据模型、关键运行时时序图、分阶段实施路线。
- 如果继续推进，我建议先把控制面 / 执行面 / 设备面三层的边界彻底定稿，再进入详细技术方案。

## 本次补充修订
- 根据讨论，已修订报告中多Agent部分：从原来的“三类 Agent”升级为“总控编排层 + 三类 Agent + 可选 Supervisor Agent”。
- 明确结论：系统需要总控能力，但不建议一开始依赖单一总控Agent；总控职责主要由 `Workflow Runtime / Session Orchestrator` 与 `Policy Router` 承担，Supervisor Agent 只在复杂场景下参与。

## 本次继续推进
- 新增《`design-总控编排层详细设计.md`》：把总控编排层拆成 Session Orchestrator、Policy Router、Workflow Runtime、Agent Executor、Supervisor Agent、Human Handoff Coordinator、Device Command Gateway 等核心组件，并明确职责边界、状态机、对象模型与 MVP 落地建议。
- 新增《`design-总控编排时序与状态图.md`》：补充入站消息、Supervisor Agent 触发、人工接管、主动运营任务等关键时序，以及会话状态机、运行状态机和中断策略说明，方便后续接口设计与运行时实现。

## 本次继续推进（二）
- 新增《`design-核心数据模型设计.md`》：系统性定义了 Project、Bot、WorkflowVersion、Conversation、SessionRuntime、WorkflowRun、NodeExecution、AgentInvocation、PolicyDecision、Device、ChannelAccount、DeviceCommand、CustomerProfile、CampaignTask 等核心实体。
- 明确了关键建模原则：Bot / WorkflowVersion / SessionRuntime 必须拆开，会话态 / 运行态 / 客户态必须拆开，设备执行事实 / 策略决策事实 / Agent 调用事实必须独立留痕。
- 补充了字段建议、唯一性约束、索引方向、分区与扩展思路，以及 MVP 建表优先级，作为后续 ER 图、数据库设计和接口设计的基线。

## 本次继续推进（三）
- 新增《`design-数据库表结构设计.md`》：将核心数据模型进一步下钻为可实施的数据库表结构基线，覆盖 PostgreSQL 选型建议、主骨架表、执行链路表、CRM 基础表以及增强治理表。
- 明确了核心表的字段类型建议、主外键关系、唯一约束、索引方向和大表分区/归档思路，尤其收敛了 `session_runtime`、`message`、`workflow_run`、`agent_invocation`、`policy_decision`、`device_command` 等关键表的落库方式。
- 补充了 MVP 建表顺序与外键策略，作为后续 ER 图、数据库建模和接口设计的直接输入。

## 本次继续推进（四）
- 新增《`design-接口设计-总控编排与会话运行时.md`》：把总控编排层进一步落成接口基线，覆盖会话入口、消息入站、运行态查询、工作流运行控制、设备命令下发与回执、人工接管与交还、策略决策与 Agent 调用审计等核心 API。
- 收敛了控制面 API、执行面 API、内部编排 API 三层接口划分，并统一了返回体、幂等要求、鉴权建议和错误码方向。
- 给出了 MVP 接口优先级，明确先做“入站消息 -> 总控编排 -> 设备命令 -> 回执闭环 -> 人工接管 -> 运行态查询”这条最核心链路，作为后续 OpenAPI 与研发拆解的直接输入。

## 本次继续推进（五）
- 新增《`openapi-总控编排与会话运行时.yaml`》：将前面的接口设计正式下钻为 OpenAPI 3.1 初稿，覆盖控制面、执行面与内部编排三层接口。
- 统一补齐了安全方案、幂等 Header、分页/路径参数、错误响应、状态枚举与核心 schema，使其可以直接作为前后端联调、Mock、SDK 生成与 OpenAPI 评审的基线。
- 明确了 Morphix 的核心 API 主链路：`入站消息 -> 会话运行态 -> 工作流运行控制 -> 设备命令 -> 设备回执 -> 人工接管 -> 策略/Agent 审计 -> 内部编排协作`，后续可以继续补充 ER 图、接口时序图和研发任务拆解。

## 本次继续推进（六）
- 新增《`design-MVP研发任务拆解清单.md`》：将前面已完成的需求理解、总控编排设计、数据模型、表结构、接口设计与 OpenAPI 初稿，正式拆成可以启动研发的 MVP 任务清单。
- 按“基础底座、数据库与数据骨架、总控编排与运行时、设备接入、控制面前后端、联调测试与运维”六条工作流拆分任务，并补充依赖关系、验收口径、里程碑与角色分工建议。
- 明确了 MVP 的真正目标不是功能堆叠，而是优先打通 `入站消息 -> 编排执行 -> 设备动作 -> 回执闭环 -> 人工接管 -> 运行态审计` 这条可上线、可排障、可灰度的系统主链路。

## 本次继续推进（七）
- 新增《`backlog-后端任务拆解.md`》：把 MVP 清单进一步下钻成面向后端团队的可执行 backlog，按控制面后端、运行时后端、设备接入后端和公共基础四类 owner 拆分任务。
- 为每个核心任务补充了优先级（P0/P1/P2）、依赖关系、接口对应、数据落点、验收标准与推荐 Sprint 顺序，便于直接排期和分配 owner。
- 进一步收敛了后端实施优先级：先把 `入站消息 -> 会话定位 -> Policy Router -> Workflow Run -> Device Command -> ACK/Complete/Fail -> 人工接管 -> 审计查询` 这条运行时主链路做扎实，再扩展控制面完整度。

## 本次继续推进（八）
- 新增《`backlog-前端任务拆解.md`》：把控制台前端工作进一步下钻为可执行 backlog，围绕会话工作台、人工接管、运行调试、Bot/WorkflowVersion 绑定、鉴权与 API 集成拆分任务。
- 为前端任务补充了优先级（P0/P1/P2）、依赖关系、对应接口、页面落点、状态管理建议与验收标准，并给出推荐 Sprint 顺序与前后端联调顺序。
- 进一步收敛了前端实施重点：MVP 先把“运营可观察、可接管、可排障”的控制台做出来，优先支撑 `会话列表 -> 会话详情 -> 运行态 -> 人工接管 -> Run/节点/决策审计` 这条控制面主链路。

## 本次继续推进（九）
- 新增《`backlog-设备端任务拆解.md`》：把设备执行端 App / Device Agent 进一步下钻为可执行 backlog，围绕设备绑定、在线心跳、命令拉取、本地命令队列、ACK/complete/fail 回执、人工接管协作、联系人/群同步与本地诊断拆分任务。
- 为设备端任务补充了优先级（P0/P1/P2）、端云职责边界、对应接口、依赖关系、联调顺序、验收门禁与风险提示，便于设备端、设备接入后端和运行时团队对齐开发节奏。
- 进一步收敛了设备端实施重点：MVP 先把设备做成“可绑定、可在线、可接命令、可回执、可暂停、可排障”的边缘执行站点，优先打通 `设备绑定 -> 在线心跳 -> 拉命令 -> ACK -> complete/fail -> 人工接管协作 -> 本地诊断` 这条设备主链路。

## 本次继续推进（十）
- 新增《`plan-MVP实施路线图.md`》：把需求理解、架构设计、OpenAPI 初稿以及后端/前端/设备端三条 backlog 统一收敛成一张可执行的阶段路线图。
- 明确了 6 个实施阶段、5 个关键里程碑、跨团队依赖图、推荐联调顺序、各阶段验收门禁、灰度上线建议与主要风险应对，方便研发、测试、实施和项目管理共用同一张推进地图。
- 进一步收敛了整体实施重点：Morphix 的 MVP 不应按传统瀑布拆端推进，而应围绕 `入站消息 -> 编排执行 -> 命令下发 -> 设备回执 -> 人工接管 -> 运行态与审计` 这条业务闭环，让后端、前端、设备端按阶段持续合流。

## 本次继续推进（十一）
- 新增《`openapi-设备接入补充接口.yaml`》：针对设备执行端 App / Device Agent 补齐设备接入契约，覆盖设备注册绑定、令牌刷新、在线心跳、设备直接上报入站消息、联系人同步、群聊同步以及诊断日志/运行快照上报。
- 明确了设备侧补充契约与现有《`openapi-总控编排与会话运行时.yaml`》的边界：原有文件继续负责命令拉取与 ACK/complete/fail 回执，这次新增文件负责“设备如何进系统、如何报在线、如何报事实、如何做排障”的剩余关键链路。
- 进一步收敛了设备接入 MVP 的联调重点：先把 `设备注册/绑定 -> 令牌初始化 -> 在线心跳 -> 入站消息上报 -> 联系人/群同步 -> 诊断快照` 这条设备接入事实链打通，再扩展更重的目录治理与自动化运维能力。

## 本次继续推进（十二）
- 新增《`plan-里程碑与验收门禁.md`》：把路线图里的阶段目标进一步下钻成项目推进闸门，明确 M1~M5 的进入条件、退出门禁、证据要求、阻塞项定义与 Green/Yellow/Red/Blocked 状态规则。
- 将联调门、灰度门和停灰条件独立写清，特别补上“什么时候绝对不能往下走”这一层管理视角，避免项目只看任务完成度、不看主链路稳定性。
- 进一步收敛了项目推进方式：Morphix 的节奏应该围绕“阶段门禁 + 验收证据 + 阻塞项关闭”来推进，而不是围绕口头上的‘差不多做完了’推进。

## Git 提交记录
- 2026-07-12：将原型相关设计文档提交并推送到 GitHub `https://github.com/stevenlk2002/Morphix.git` 的 `main` 分支（commit `8be4fc8`）。
- 本次提交包含 15 个文件、约 11,936 行新增，覆盖需求理解报告、总控编排设计、核心数据模型、数据库表结构、接口设计、两份 OpenAPI 初稿、三端 backlog、MVP 实施路线图与里程碑门禁，以及 `overview.md` 更新。
- 说明：`NoCodeFlow/` 为独立的实现工程（6311 个文件），未纳入本次提交，避免污染以“原型 + 设计文档”为定位的仓库；如需纳入，后续可单独提交。

## 本次继续推进（十三）
- 新增《`plan-联调测试用例清单.md`》：把前面收敛出的架构、两份 OpenAPI、三端 backlog 与里程碑门禁进一步落成可执行的联调测试基线。
- 清单覆盖 7 大分组、约 45 个用例：主链路 E2E（A）、控制面（B）、设备接入（C）、人工接管与交还（D）、异常与边界（E）、安全与鉴权（F）、里程碑验收（G），并给出用例总览表、接口索引、联调顺序、缺陷定级红线与用例模板。
- 用例全部锚定真实接口与 M1~M5 / 联调1~5 门禁，重点把 P0 阻塞项映射到具体反例：重复消息幂等、回执 no-op、设备离线重投、断网补传、接管后停发、可回放审计。

## 本次继续推进（十四）
- 新增《`openapi-morphix-unified.yaml`》：将《`openapi-总控编排与会话运行时.yaml`》与《`openapi-设备接入补充接口.yaml`》合并为统一总契约。
- 合并后共 33 个 path / 33 个 operation，含 5 个 securityScheme（ControlAuth / RuntimeAuth / DeviceAuth / InternalServiceAuth / DeviceProvisioningAuth）、12 个 tag、115 个 schema。
- 去重与合并处理：DeviceAuth 合并为一份；`IdempotencyKey` 描述合并覆盖控制面与设备侧写操作；`responses` 5 个统一；`SuccessEnvelope/ErrorEnvelope/ConversationType` 去重；`ChannelType` 取超集（wechat/wecom/qq/unknown）；`ErrorObject.code` 枚举合并两边全部错误码，`details` 采用结构化 `ErrorDetail[]`。
- 已用 Python 脚本做语法校验与引用完整性检查：33 path 无重复、140 个 `$ref` 全部命中、securityScheme 与 tag 无悬空引用，校验通过。

## 本次继续推进（十五）— 渠道账号添加流程 7 步重构
依据 8 张参考图（添加渠道账号2~8 + 最终 Clipboard_Screenshot），把"渠道账号管理 → 添加渠道账号"改为完整 7 步流程：

- **Step 1 选择渠道类型**（`channel-account-add`）：保留 stepper，页面顶部为「添加渠道账号」标题 + 剩余席位 1个 [购买更多] 横幅，下方两张渠道类型卡片（尘微 / 邮暖），含图标、名称、描述、右侧箭头；点击后下一步按钮启用。
- **Step 2 协议选择**（`channel-account-protocol`，新增）：stepper 第 1 步完成、第 2 步 active。协议下拉显示「ipod (推荐) / pc」两选项，含 radio 圆点 + 名称 + 说明（"iPad 协议 · 稳定 · 风险低" / "PC 协议 · 兼容老系统"），底部根据选项动态切换提示。底部按钮：上一步 / 创建账号。
- **Step 3 扫码页**（`channel-account-qr`）：文案改为「请使用企业微信扫码 [扫一扫→]」+ 嵌入 SVG 二维码 + 「扫码添加渠道账号」+ 2 分钟有效提示；点击「扫一扫」进入等待手机确认态。
- **Step 4 等待手机确认**（`channel-account-waiting`，新增）：用 CSS + SVG 渲染一个手机外壳 mockup（黑底、刘海、状态栏、chevron、pad SVG、「其他端 企业微信登录确认」标题、登录/取消登录按钮），下方显示「正在等待确认…（已等待 N 秒）」脉冲动画；4 秒后自动跳到验证码输入页（模拟手机端确认完成）。
- **Step 5 验证码输入**（`channel-account-verify`，新增）：两列布局——左侧「请在企业微信上确认登录」tag + 医补通档案（医补通 / 通天晕·林建）+ 返回；右侧「请输入验证码」+ 6 个分隔输入框（3·3 格式，含中间分隔点）+ 6 位数字 60 秒有效提示 + 返回重新扫码。6 位填满后自动触发完成。
- **Step 6 成功跳转**：完成时 toast 提示「已成功添加渠道账号，正在拉取会话列表…」，700ms 后跳到 `channel-sessions`。
- **Step 7 渠道会话管理**：动态注入新账号「医补通」到侧边栏首位并设为 active（ipad在线），替换中间列表为该账号下的 10 个好友/群（医补@新民、Cloud@新民、聚主白银做营顾、远志-洪创意、Dr.Jack 恒康倍力、竹绿-健康-巴...、钉钉、客户联系、希犬-林瞰、钉钉会话），并把顶栏「剩余席位 1」自动降为 0（消耗一个席位）。

### 实现要点
- 5 个新页面的 CSS 组件族：`.channel-add-seats`、`.channel-type-card`、`.channel-protocol-select`、`.channel-qr-*`、`.channel-phone-mock`、`.channel-verify-*`，沿用品牌色 `--primary` 与金色点缀。
- JS 状态机 `channelAddState = { type, protocol, waitTimer, waitSec, justAdded }`，串联 5 步流程。
- 协议下拉点击外部自动关闭（document click 委托）。
- 验证码输入框：仅数字、自动跳格、Backspace 回退、6 位填满自动完成。
- 等待计时器在页面切换/完成时清理，避免内存泄漏。
- 顺带修复：之前 `channel-account-qr` 存在两个重复 key，合并为单一定义。

### 验证
- `node --check` 语法通过。
- agent-browser 走通完整 7 步流程，截图保存：
  - `prototype/shot-channel-add-1-type.png`（Step 1 选择渠道类型）
  - `prototype/shot-channel-add-2-protocol.png`（Step 2 协议选择默认）
  - `prototype/shot-channel-add-2b-protocol-open.png`（Step 2 协议下拉打开）
  - `prototype/shot-channel-add-3-qr.png`（Step 3 二维码）
  - `prototype/shot-channel-add-4-waiting.png`（Step 4 等待手机确认）
  - `prototype/shot-channel-add-5-verify.png`（Step 5 验证码输入）
  - `prototype/shot-channel-add-6-sessions.png`（Step 7 渠道会话管理：医补通账号 + 好友/群列表 + 剩余席位 0）