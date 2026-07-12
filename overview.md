# Morphix 原型改造总结

## 本次完成：SOP 工作流节点拖拽与配置联动（任务 #95）

### 改造内容
- 文件：`/Users/stevenmac/Desktop/工作目录/Morphix/prototype/index.html`
- 页面：`sop-create-customer`、`sop-create-group`
- 在已改造的「工作流模式」基础上，新增节点交互与右侧面板联动：
  - **节点悬停 + 按钮**：鼠标移到节点卡片上，右上角显示金色 `+` 圆点；点击后弹出菜单框。
  - **添加节点菜单**：菜单标题「客户触达 / 群聊触达」，含 5 个选项：消息触达、客户属性修改、机器人托管、运行机器人、延迟。
  - **节点追加与连线**：选择菜单项后，在被点击节点右侧自动追加对应节点，并用带箭头的连线连接；新节点自动选中。
  - **右侧面板联动**：选中不同节点时，右侧固定配置面板实时切换为对应节点的配置表单：
    - 消息触达：文本 / 图片 / 视频 / 文件 / 卡片链接 Tab + 文本内容输入 + 添加群发内容
    - 客户属性修改：添加标签 + 移除标签
    - 机器人托管：选择托管机器人
    - 运行机器人：选择运行机器人
    - 延迟：延迟时间（小时）
  - **删除节点**：非设置节点显示「删除」按钮，删除后自动重新排布后续节点位置。
  - 流程设置节点保留原有的执行客户/群聊与触发规则完整配置。

### 新增 JS 能力
- `customerFlowState` / `groupFlowState`：维护节点数组与当前选中节点。
- `FLOW_NODE_TYPES`：节点类型元数据（标签、图标、主题色、宽度）。
- `initCustomerFlow()` / `initGroupFlow()`：初始化默认的「流程设置」节点。
- `renderCustomerFlow()` / `renderGroupFlow()`：动态渲染节点、计算位置、绘制连线和箭头。
- `showFlowNodeMenu()` / `hideFlowNodeMenu()`：显示/隐藏添加节点菜单。
- `addFlowNode()` / `deleteFlowNode()`：节点增删与重新排布。
- `selectFlowNode()` / `renderCustomerConfigPanel()` / `renderGroupConfigPanel()`：节点选中与右侧面板渲染。

### 新增 CSS 类
- `.flow-node-add`：节点右上角 + 按钮
- `.flow-node-menu` / `.flow-node-menu-item` / `.flow-node-menu-title`：添加节点菜单
- `.flow-connector`：节点间带箭头连线
- `.flow-node.message` / `.attr` / `.robot` / `.run-robot` / `.delay`：各类型节点主题色
- `.flow-content-tabs` / `.flow-textarea` / `.flow-add-content`：消息触达内容配置
- `.flow-node-delete`：节点删除入口

### 验证
- `node --check` 语法通过
- agent-browser 实跑：悬停显示 + 按钮、点击展开菜单、追加各类型节点、右侧面板正确切换、群聊 SOP 设置节点图标正确
- 删除节点：节点卡片「删除」按钮 `onclick` 中 `node.id` 未加引号导致 `ReferenceError`，已修复；右侧面板新增红色「删除」按钮；流程设置节点不可删除；删除后后续节点自动重新排布。客户 SOP 与群聊 SOP 均通过节点卡片和配置面板两种入口验证通过。

### 截图
- `prototype/shot-sop-customer-workflow-v3.png`（客户SOP 工作流初始态）
- `prototype/shot-sop-customer-menu-v3.png`（客户SOP 添加节点菜单）
- `prototype/shot-sop-customer-message-v3.png`（消息触达节点）
- `prototype/shot-sop-customer-attr-v3.png`（客户属性修改节点）
- `prototype/shot-sop-customer-robot-v3.png`（机器人托管节点）
- `prototype/shot-sop-customer-runrobot-v3.png`（运行机器人节点）
- `prototype/shot-sop-customer-delay-v3.png`（延迟节点）
- `prototype/shot-sop-group-workflow-v3.png`（群聊SOP 工作流初始态）
- `prototype/shot-sop-customer-delete-v4.png`（客户SOP 节点删除入口与右侧面板删除按钮）
- `prototype/shot-sop-group-delete-v4.png`（群聊SOP 节点删除入口）

## 授权用户管理页面（任务 #103）

### 改造内容
- 文件：`prototype/index.html`
- 页面：`org-auth`（组织管理 → 授权用户管理）
- 替换原有占位页面，实现完整授权用户管理：
  - **筛选栏**：「登录账号」「用户昵称」输入框，右侧「重置」「查询」「+ 新增」按钮（金色品牌色）。
  - **用户表格**：表头「登录账号 | 用户昵称 | 所属角色 | 操作」，空状态展示文件夹图标 +「暂无数据」。
  - **新增 RAM 用户弹窗**：标题「新增RAM用户」，必填字段「账号」「密码」「角色」；账号/密码带 `0/20` 字符计数，密码框带眼睛图标可切换显示/隐藏；底部「取消」「确定」。
  - **操作列**：已存在用户显示「编辑」「删除」入口；删除后表格实时刷新。

### 新增 JS 能力
- `authorizedUsers`：用户数据数组。
- `renderAuthUserTable()` / `queryAuthUsers()` / `resetAuthUserFilter()`：表格渲染与筛选。
- `openAddRAMUserModal()` / `saveRAMUser()` / `deleteRAMUser()`：新增与删除用户。
- `updateRAMAccountCount()` / `updateRAMPasswordCount()` / `toggleRAMPasswordVisibility()`：字符计数与密码显隐。

### 新增 CSS 类
- `.auth-user-mgmt` / `.auth-user-card` / `.auth-user-filter` / `.auth-user-table`：页面布局与表格样式。
- `.btn-auth-gold` / `.btn-auth-secondary`：金色主按钮与白色次要按钮。
- `.ram-form-row` / `.ram-input-wrap` / `.ram-input-suffix` / `.ram-select`：弹窗表单与密码框 suffix。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑：空态渲染、新增弹窗、字符计数、密码显隐、保存后表格回显、删除返回空态均正常。

### 截图
- `prototype/shot-org-auth-empty.png`（授权用户管理空态）
- `prototype/shot-org-auth-modal-direct.png`（新增 RAM 用户弹窗）
- `prototype/shot-org-auth-withdata.png`（新增用户后的表格）

## 数据面板机器人指标率右侧开关改造（任务 #106）

### 改造内容
- 文件：`prototype/index.html`
- 页面：`data-panel`（数据面板 → 数据总览卡片）
- 将原「机器人消息处理率」「机器人会话处理率」「机器人转人工率」三个率指标从图表上方横向数值卡片，改造为图表右侧垂直排列的复选框开关：
  - **右侧指标筛选面板**：浅灰背景，固定宽度 220px，标题「指标筛选」；三个 `.dp-rate` 行使用自定义 16px 复选框 + 指标名称 + 问号图标。
  - **曲线联动**：默认全部选中，图表叠加三条百分比折线（带圆点）；取消勾选后对应折线立即消失，只影响曲线图指标。
  - **公式 tooltip**：每个问号图标 hover 显示黑色气泡，分别展示：
    - 机器人消息处理率 = 机器人处理消息数 / 总消息数
    - 机器人会话处理率 = 机器人处理会话数 / 有客户消息的托管会话数
    - 机器人转人工率 = 机器人转人工数 / 机器人处理消息数
  - **双 Y 轴**：左侧保持原数值刻度，右侧新增 0~100% 百分比刻度。

### 新增 JS 能力
- `drawDataChart()` 扩展：每个数据点按公式计算 `msgRate` / `sessionRate` / `transferRate`；根据 `.dp-rate.checked` 状态绘制/隐藏对应折线。
- `toggleRate(el)`：切换率指标选中状态并重绘图表。

### 新增 CSS 类
- `.dp-chart-row` / `.dp-chart-main`：图表与指标面板左右布局容器。
- `.dp-rates` / `.dp-rate` / `.dp-rate-check` / `.dp-rate-label`：右侧垂直复选框指标行。
- `.dp-rate-help` / `.dp-rate-tip` / `.dp-rate-tip::after`：黑色气泡 tooltip。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑：默认三率均选中并显示折线；点击取消后对应折线消失；三个问号图标 hover 均正确弹出黑色公式 tooltip。

### 截图
- `prototype/shot-data-panel-rates.png`（三率默认全选，右侧折线）
- `prototype/shot-data-panel-uncheck-msg.png`（取消「机器人消息处理率」后蓝色折线消失）
- `prototype/shot-data-panel-tooltip-hover.png`（机器人消息处理率 tooltip）
- `prototype/shot-data-panel-tooltip-session.png`（机器人会话处理率 tooltip）
- `prototype/shot-data-panel-tooltip-transfer.png`（机器人转人工率 tooltip）

## 数据面板右侧增加托管账号/机器人筛选（任务 #107）

### 改造内容
- 文件：`prototype/index.html`
- 页面：`data-panel`（数据面板 → 数据总览卡片）
- 在图表右侧「指标筛选」面板顶部，新增「筛选条件」区域，放置「托管账号」「托管机器人」两个筛选字段：
  - **托管账号**：标签 + 问号图标（hover 提示「选择需要查看的托管账号」）+ 只读输入框（默认「全部」）+ 右侧搜索图标，点击展开下拉选项（全部 / 竹绿-健康 / 恒康倍力）。
  - **托管机器人**：标签 + 问号图标（hover 提示「选择需要查看的托管机器人」）+ 只读输入框（默认「全部」）+ 右侧下箭头，点击展开下拉选项（全部 / 野风秋大健康机器人 / AI客服-1）。
  - 选择后输入框实时回填，并 toast 提示所选值；两个下拉互斥，打开一个时自动关闭另一个。

### 新增 JS 能力
- `toggleDPFilter(type)`：切换「托管账号」或「托管机器人」的下拉选项列表。
- `selectDPFilter(type, value, event)`：回填对应输入框并关闭下拉，同时 toast 反馈。

### 新增 CSS 类
- `.dp-filters` / `.dp-filters-title` / `.dp-filter`：筛选条件区域容器与标题。
- `.dp-filter-label` / `.dp-filter-help` / `.dp-filter-tip`：标签 + 问号图标 + 黑色气泡 tooltip。
- `.dp-filter-input` / `.dp-filter-icon` / `.dp-filter-options` / `.dp-filter-option`：只读输入框与下拉选项列表。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑：右侧面板出现「筛选条件」、两个字段下拉均可展开、选择「竹绿-健康」后正确回填并 toast 反馈。

### 截图
- `prototype/shot-data-panel-filters.png`（默认状态，右侧筛选条件与指标筛选）
- `prototype/shot-data-panel-account-open.png`（托管账号下拉展开）
- `prototype/shot-data-panel-robot-open.png`（托管机器人下拉展开）
- `prototype/shot-data-panel-filters-final.png`（最终干净状态）

## 数据面板六张指标卡片问号 tooltip（任务 #108）

### 改造内容
- 文件：`prototype/index.html`
- 页面：`data-panel`（数据面板 → 六张指标卡片）
- 在「新增会话数」「托管会话数」「机器人处理会话数」「总消息数」「机器人处理消息数」「机器人转人工数」六张指标卡片标题旁，增加问号圆圈图标；鼠标 hover 时分别显示对应业务定义的黑色气泡 tooltip：
  - 新增会话数：选定期间内，新出现在Morphix平台上的会话数，包含单聊、群聊；可能是新增好友的会话，也可能是添加渠道账号前已存在，添加后首次收到新消息的会话。
  - 托管会话数：选定期间内，曾处于过机器人托管状态的会话数，包含单聊、群聊。请注意，这里包含后来取消托管的会话。
  - 机器人处理会话数：选定期间内，机器人曾处理过其中客户消息的会话数，包含单聊、群聊。请注意，处理指机器人思考过用户发送的消息，可能思考后选择不回复或转人工。
  - 总消息数：选定期间内，Morphix平台在各个托管会话中收到的外部消息数；会排除掉系统消息和企微内部联系人发送的消息。
  - 机器人处理消息数：选定期间内，机器人曾处理过的客户消息数。请注意，处理指机器人思考过用户发送的消息，可能思考后选择不回复或转人工。
  - 机器人转人工数：选定期间内，机器人思考过后，决定转人工的次数。

### 新增 CSS 类
- `.dp-metric-help`：问号图标容器，hover 时显示黑色气泡。
- `.dp-metric-help .tab-tooltip-bubble`：继承现有 `.tab-tooltip-bubble` 样式，居中定位到问号图标（`left:50%; transform:translate(-50%,4px)`），默认隐藏，hover 时显示。
- `.dp-metric-help .tab-tooltip-bubble::before`：向下箭头，居中于气泡底部。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑：六张卡片均显示问号图标；hover 后弹出黑色气泡 tooltip，文案与参考图一致；点击问号图标不会触发卡片的勾选切换。

## 数据面板筛选与指标筛选同一行布局调整

### 改造内容
- 文件：`prototype/index.html`
- 页面：`data-panel`（数据面板）
- 按需求重新组织数据面板布局：
  - 移除「数据总览」卡片右侧的「筛选条件」区块（含托管账号/机器人下拉），因为顶部筛选栏已存在。
  - 在顶部 filter-bar 的「托管账号」「托管机器人」下拉中补全选项（全部/竹绿-健康/恒康倍力、全部/野风秋大健康机器人/AI客服-1）。
  - 将原右侧「指标筛选」三个率开关（机器人消息处理率/机器人会话处理率/机器人转人工率）移出右侧边栏，作为 `.dp-rate-card` 与六张指标卡片放在同一行。
  - 调整 `.dp-metrics` 为 flex 布局，`.dp-metric` 自适应宽度，`.dp-rate-card` 固定 160px；压缩卡片内边距、字号与间距，确保在 1280px 视口下 6 张指标卡 + 指标筛选卡可在同一行显示且文字不换行。
  - 数据总览图表改为全宽展示（`.dp-chart-body`），不再保留右侧边栏。

### 新增/变更 CSS 类
- `.dp-rate-card`：承载三个率开关的卡片容器，与指标卡片同处一行。
- `.dp-chart-body`：图表全宽容器。
- 移除（不再使用）：`.dp-rates` 右侧边栏、`.dp-filters` 筛选区块、`.dp-chart-row`/`.dp-chart-main` 左右布局。

### 新增/变更 JS 能力
- 移除不再使用的 `toggleDPFilter()` / `selectDPFilter()` 函数。
- `drawDataChart()` 与 `toggleRate()` 逻辑保持不变，继续通过 `.dp-rate.checked` 控制折线显示。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑：顶部筛选下拉内容完整；指标卡与三率开关在同一行；取消勾选率指标后对应折线消失；图表 tooltip 正常。

### 截图
- `prototype/shot-dp-layout-final.png`（指标卡与三率开关同一行最终布局）
- `prototype/shot-dp-rate-toggle.png`（取消勾选率指标后图表联动）
- `prototype/shot-dp-chart-tooltip-after.png`（全宽图表鼠标悬停 tooltip）

## 对话机器人卡片改为两列并排

### 改造内容
- 文件：`prototype/index.html`
- 页面：`robots`（对话机器人）
- 机器人卡片从单列堆叠改为双列并排：新增 `.bot-card-grid`（`display:grid; grid-template-columns: repeat(2,1fr); gap:16px`），`.bot-card` 由写死宽度改为放入网格容器；`@media (max-width:900px)` 回退单列。卡片自身样式不变。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑：页面出现 `.bot-card-grid` 两列布局。
- 截图：`prototype/shot-robots-grid.png`

## 编排页面（流程编辑）重构为可拖曳工作流 + 右侧浮动节点面板

### 改造内容
- 文件：`prototype/index.html`
- 入口：对话机器人列表页「流程编辑」按钮 → `navigate('robot-orchestrate')`；`afterNavigate` 中加 `if (page==='robot-orchestrate') setTimeout(initOrchestratePage, 50);`。
- 布局：`.orchestrate-page`（顶栏标题 + 导出/保存按钮）> `.orchestrate-editor#orchestrateEditor`（左侧 `.flow-canvas#flowCanvas` 空画布 + 右侧 `.flow-panel#flowPanel` 浮动面板）。
- 浮动面板能力：折叠/展开（`.collapsed`）、拖拽改宽（min 200px）、实时搜索过滤、三个 Tab 切换 + 折叠态竖排 Tab。
- 三 Tab 节点体系（`const ORCHESTRATE_NODES`，约 L2764）：
  - **基础节点**（29 个）：获取内容(3) + 输出(9) + 工具(3) + 流程控制(3) + 逻辑处理(11)。
  - **复合节点**（13 个）：AI机器人嵌入(1) + 子流程调用(12)。用户原图仅列 5 个，原型额外补充了空行分隔回答、清空聊天上下文及更多子流程节点。
  - **特殊渠道节点**（11 个）：企业微信(5，与用户需求完全一致) + Morphix(6，按对称扩展，需用户确认是否裁剪)。
- 交互：面板节点可拖拽到画布生成新节点（ghost 跟随）；画布节点可拖动；折叠/搜索/改宽均可用。

### 关键 JS（约 L2854）
- `initOrchestratePage()`：重置状态、预置两个画布节点（智能体嵌入@60,80、强提醒子流程@340,60）、渲染面板与画布、绑定事件。
- `getNodeDef()` / `getNodeIconHtml()`：复用 `icons` 映射，自定义 Fx/A/M 文本图标。
- `renderFlowPanel()` / `updatePanelTabs()` / `switchFlowPanelTab()` / `filterFlowPanel()` / `toggleFlowPanel()` / `startResizeFlowPanel()`。
- `renderCanvasNodes()` / `createCanvasNode()` / `startCanvasNodeDrag()` / `startPanelNodeDrag()` / `setupCanvasEvents()`。

### 验证
- `node --check` 语法通过。
- agent-browser 实跑 DOM 断言全部通过：
  - 基础 Tab：5 分类 29 节点，分类标题与节点名完全匹配。
  - 复合 Tab：2 分类 13 节点。
  - 特殊 Tab：2 分类 11 节点（企业微信 5 个与需求一致）。
  - 搜索「输出」精确过滤出 9 个节点。
  - `toggleFlowPanel()` 后面板加 `.collapsed` 类。
  - `createCanvasNode()` 使画布节点 2→3 且坐标正确。
  - `startResizeFlowPanel` 拖拽改宽 300→200px（受 min 200 钳制）。
- 截图：`prototype/shot-orchestrate-basic.png`、`shot-orchestrate-composite.png`、`shot-orchestrate-special.png`、`shot-orchestrate-collapsed.png`
- 注：当前模型不支持图片解析，视觉细节需用户在多模态模型下复核截图。

## 编排节点参数编辑面板（每个节点可编辑输入/输出参数）

### 改造内容
- 文件：`prototype/index.html`
- 依据：`Morphix无代码编排手册V2.0.pdf`（节点构成 = 左侧输入点 + 中间执行逻辑 + 右侧输出点；输入点 3 类：仅连线 / 仅直接输入 / 两者皆可；带 * 输入点必须赋值才能保存）。
- 新增 `NODE_SCHEMAS`：为全部 53 个节点定义 `inputs`（输入点：mode/required/varName/dataType）、`outputs`（输出点只读）、`config`（执行配置可编辑字段：text/textarea/select/number/note）。
  - 关键参数：用户输⼊无输入、输出 消息原始内容/AI识别内容/消息类型；消息输出 输入「消息」(必填)+配置 分段方式；AI对话 输入 用户问题(必填)/聊天记录/知识库引用 + 配置 大模型/提示词({userChatInput}{chatHistory}{knowledges}) + 输出 AI回复内容；知识库搜索 输入 用户问题(必填)+配置 知识库/搜索模式/返回数量；多重判断器 输入 判断内容(必填)+配置 判断模式/匹配内容/运算符/比较值；时间控制 输入「触发」(connect)+配置 延迟秒数；全局变量 配置 变量名/数据类型/输入方式。
- 交互：点击画布节点打开右侧 `.node-inspector` 抽屉（同时隐藏左侧节点面板），分「输入参数 / 执行配置 / 输出参数」三区；连线型输入渲染为只读 chip「连线输入 · {varName}」；编辑实时写入节点实例；点击画布空白或关闭按钮收起面板并恢复节点面板；支持删除节点。
- CSS：`.node-inspector`、`.inspector-section/title`、`.inspector-field`、`.inspector-port-chip`、`.inspector-output-row`、`.dt-badge`、`.inspector-hint`、`.inspector-footer-note`。

### 验证
- `node --check` 语法通过。
- agent-browser DOM 断言：智能体嵌入节点打开后 输入1/配置1/输出1 且节点面板隐藏；AI对话 输入[question,history,knowledge]+配置[model,prompt]+输出[AI回复内容]，提示词 textarea 与大模型 select 存在，编辑值持久化成功；时间控制 输入为 connect-only 渲染 chip、配置[seconds]；收起后面板恢复。
- 截图：`prototype/shot-inspector-aichat.png`、`shot-inspector-multijudge.png`、`shot-inspector-wecomgroup.png`、`shot-inspector-timecontrol.png`、`shot-inspector-userinput.png`
- 注：当前模型不支持图片解析，视觉细节需用户在多模态模型下复核截图。

---

## 节点连线删除交互增强

### 问题
- 上一版已提供双击删除，但 SVG 连线层 `.flow-links-layer` 为 `pointer-events:none`，`<path ondblclick>` 事件无法到达，导致用户实际上无法删除连线。

### 改动
- **状态**（`index.html`）：`orchestrateState` 新增 `selectedLinkId`；`initOrchestratePage` 中重置并绑定一次 `Delete/Backspace` 监听器；节点选中/拖动/新建时同步清除连线选中态。
- **渲染**（`renderLinks` / `buildPath`）：每条连线渲染为 `<g class="flow-link">` 分组，含：
  - `.flow-link-hit`：透明宽命中区（stroke-width:16，pointer-events:stroke），SVG 层保持 `pointer-events:none` 使空白区仍能穿透到画布/节点。
  - `.flow-link-line`：可见线，hover/selected 时变红加粗。
  - `.flow-link-del`：连线中点红色圆形 × 删除按钮，hover/selected 时浮现。
- **删除方式**：
  1. 悬停连线 → 中点 × 按钮 → 点击删除；
  2. 点击连线选中 → 按 `Delete`/`Backspace` 删除；
  3. 双击连线（命中区）仍保留快捷删除。
- **提示**：画布左下角增加 `flow-canvas-hint` 提示条。

### 验证
- `node --check` 语法通过。
- agent-browser 真实交互：注入测试连线后，hover 点击中点 × 按钮，连线 DOM 与 `links.length` 同时由 1 变为 0；选中一条连线后按 Delete，仅该连线被删除，另一条保留；`selectedLinkId` 同步清空。
- 截图：`prototype/shot-link-delete.png`（悬停态，连线变红，中点 × 按钮可见）。

---

## 渠道会话管理接入移动端小程序原型

### 需求
- 在“渠道会话管理”右侧内容区右上角新增提示入口：**“您也可以在移动端管理会话托管哦~点击这里”**。
- 点击后进入一个面向未来微信小程序形态的移动端原型页面，并吸收 8 张参考图里的核心界面状态，而不是只做一张静态手机截图。

### 改动
- **桌面入口**（`prototype/index.html` / `channel-sessions`）：
  - 在 `.session-toolbar-top` 右侧新增 `.session-mobile-entry` 胶囊提示，内含引导文案与点击态高亮。
  - 点击后跳转到新增页面路由 `mobile-session-hosting`。
- **移动端原型页**（新增 `pages['mobile-session-hosting']`）：
  - 页面结构采用“左侧场景导航 + 右侧手机壳预览”，便于桌面评审多个小程序状态。
  - 顶部说明区明确定位为“微信小程序原型”，并解释该页面承载的是会话托管移动端信息架构。
- **小程序状态建模**：
  - 新增 `miniappHostingState` 与渲染函数：`initMiniappHostingPage()`、`switchMiniappScene()`、`renderMiniappHostingPreview()`、`getMiniappHostingSceneHtml()`。
  - 把参考图抽象为 8 个可切换场景：
    1. 全部会话列表
    2. 托管中列表
    3. 日期筛选弹层
    4. 标签筛选弹层
    5. 批量勾选态
    6. 托管账号下拉
    7. 机器人下拉
    8. 单聊/群聊下拉
- **样式体系**：
  - 新增 `.mobile-miniapp-*` / `.miniapp-*` 组件族，覆盖手机壳、状态栏、胶囊头、搜索框、Tab、筛选条、会话卡片、底部操作栏、弹层、下拉面板。
  - 视觉上延续参考图的浅蓝顶部背景、白色卡片、蓝色主按钮与小程序胶囊头，但做了桌面端评审友好的结构增强。
- **初始化接入**：在 `afterNavigate(page)` 中为 `mobile-session-hosting` 挂载初始化逻辑。

### 验证
- `node --check` 语法通过。
- agent-browser 验证：
  - “渠道会话管理”页面右上角入口文案出现且可点击。
  - 进入移动端页后，默认场景为 `all`，存在 3 个顶部 Tab、4 张会话卡片、底部“选择机器人”按钮。
  - 切到日期场景后，弹层标题正确显示 `2026年07月`。
  - 切到机器人下拉场景后，存在“全部 / 无 / 杨奇成健康机器人”选项。
- 截图：
  - `prototype/shot-channel-session-mobile-entry.png`
  - `prototype/shot-mobile-miniapp-overview.png`
  - `prototype/shot-mobile-miniapp-calendar.png`

---

## 渠道会话管理顶部布局重排

### 需求
- 用户反馈：`mobile entry` 与搜索框塞在一行太挤，应将“初始团队”下拉 + “剩余席位”抽出，与移动端提示文案共同组成一个独立的上部信息条。
- 结构要求：
  - 左侧：初始团队下拉 + 剩余席位
  - 右侧：您也可以在移动端管理会话托管哦~点击这里（独立成行）

### 改动
- **结构**（`index.html` / `channel-sessions`）：
  - 用 `.session-page-shell` 包裹内容，顶部新增 `.session-page-topbar`。
  - `.session-page-topbar-left` 内放置原有 `#teamSelector`（初始团队下拉）和 `#currentTeamSeats` 所在 `剩余席位` 标签。
  - `.session-page-topbar` 右侧放置 `.session-mobile-entry` 移动端入口，右对齐独立显示，带地球图标和“点击这里”高亮。
  - 移除 `.session-toolbar-top` 中原有的重复入口，避免双份文案。
- **样式**：
  - 新增 `.session-page-topbar` / `.session-page-topbar-left`。
  - 顶部 `.team-selector` 设为白底卡片、圆角、阴影，与原来左侧栏内的扁平样式区分。
  - `.session-mobile-entry` 设为透明背景、无边框、右对齐，仅通过图标和蓝色文字提示。
  - 移动端适配：顶部条在窄屏下纵向堆叠，左侧块自动折行。

### 验证
- `node --check` 语法通过。
- agent-browser 验证 DOM 结构：
  - `topbar: true`, `left: true`
  - `team: "初始团队"`, `seats: "剩余席位0"`, `entry: "您也可以在移动端管理会话托管哦~点击这里"`
  - `dupInToolbar: false`（工具栏内无重复入口）
- 截图：`prototype/shot-channel-session-topbar.png`（顶部信息条独立成行，左侧团队/席位，右侧移动入口）。

---

## 渠道会话管理二维码弹窗 + 结构与样式清理

### 需求
- 用户反馈：点击“您也可以在移动端管理会话托管哦~点击这里”应直接显示小程序二维码，而不是直接跳转。

### 改动
- **入口行为**：把 `.session-mobile-entry` 的 `onclick` 从 `navigate('mobile-session-hosting')` 改为 `openMobileHostingQR()`。
- **二维码弹窗**（新增 `#mobileQRModal` / `.mobile-qr-overlay` / `.mobile-qr-card`）：
  - 嵌入 Base64 PNG 二维码（`https://morphix.ai/mobile/session-hosting`），验证 PNG 头尾完整；
  - 弹窗顶部关闭按钮 ×、中间小程序图标 + 二维码、下方提示文案“微信扫码即可使用 Morphix 管理小程序”；
  - 底部“查看原型”链接，点击后关闭弹窗并进入 `mobile-session-hosting`。
- **结构 bug 修复**：在整理 `channel-sessions` 页面顶部布局时，发现该字符串末尾少了一个 `</div>`，导致 `session-page-shell` 未闭合，浏览器把整段 `mobile-session-hosting` 页面吸收进 `channel-sessions` 的 `.page` 容器。补回缺失的 `</div>`，使两个页面平级、互不嵌套，移动端页面 active 时正常显示。
- **样式清理**：CSS 中 786-867 行混入了前序编辑的 diff 残留（`@@` 和 `+ ` 前缀），导致整段 `.mobile-miniapp-*` 样式失效。清理 86 处 `+ ` 前缀和 2 处垃圾行，确认 `grep -c "^[+@]"` 为 0。

### 验证
- `node --check` 语法通过。
- agent-browser 验证：
  - 点击入口后 `#mobileQRModal` 含 `open` 类，二维码图片 `naturalWidth > 0`；
  - 点击“查看原型”后 `mobile-session-hosting` 页 `offsetW: 1006, offsetH: 1175`，正确渲染手机壳、8 个场景按钮、4 张会话卡片；
  - DOM 确认 `#content` 下 `mobile-session-hosting` 不再嵌套在 `channel-sessions` 内部；
  - 关闭弹窗后返回 `channel-sessions` 顶部布局正常。
- 截图：
  - `prototype/shot-channel-session-qr-modal.png`（弹窗居中，二维码、文案、查看原型按钮可见）。
  - `prototype/shot-channel-session-topbar.png`（顶部布局正常）。
  - `prototype/shot-mobile-miniapp-styled.png`（修复后移动端小程序页正常渲染手机壳与卡片）。
