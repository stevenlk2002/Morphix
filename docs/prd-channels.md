# Morphix「渠道会话」栏目 — 产品需求文档（PRD）

> 范围：左侧一级栏目 **「渠道会话」**（原型 nav id: `channels`）下属的全部子功能版面。
> 依据：原型 `/Users/stevenmac/Desktop/工作目录/Morphix/prototype/index.html`（9537 行，HTML+模板字符串屏幕定义在 `pages` 对象内，起始于 L7040）。
> 说明：所有结论均基于原型与现有代码实际，无臆测字段。

---

## 1. 原型定位与导航结构

### 1.1 原型中的栏目定位
- 侧边栏导航定义位于 **L2208-2241**（`navItems` 数组）。
- 一级栏目「渠道会话」定义：**L2215-2220**

```js
{ id: 'channels', label: '渠道会话', icon: 'chat', children: [
  { id: 'channel-accounts',  label: '渠道账号管理' },
  { id: 'channel-sessions',  label: '渠道会话管理' },
  { id: 'channel-contacts',  label: '渠道联系人列表' },
  { id: 'channel-settings',  label: '特殊渠道设置' }
]}
```

### 1.2 子版面清单（含原型屏幕定义行号）
| 子版面 | 原型 screen key | 原型行号 | 建议前端路由（`src/router.tsx` 现有约定） |
|---|---|---|---|
| 渠道账号管理 | `channel-accounts` | L7801-7846 | `/channels/accounts` ✅已存在 |
| ├─ 添加渠道账号向导 | `channel-account-add` / `channel-account-qr` | L7848-7874 | `/channels/accounts/add` |
| ├─ 托管管理（批量托管 + 规则） | `channel-hosting` | L7876-8083 | `/channels/accounts/:id/hosting` |
| 渠道会话管理 | `channel-sessions` | L8085-8286 | `/channels/sessions` ✅已存在 |
| ├─ 移动端会话托管（小程序原型） | `mobile-session-hosting` | L8288-8328 | 参考态，桌面端非必做 |
| 渠道联系人列表 | `channel-contacts` | L8330-8468 | `/channels/contacts` ✅已存在 |
| 特殊渠道设置 | `channel-settings` | L8470-8484 | `/channels/settings` ✅已存在 |

> 关键澄清：**「渠道会话管理」(channel-sessions) 是 IM 风格的客服会话收件箱（三栏：账号列表 / 会话列表 / 聊天+客户详情）**，与现有资源域 `/sessions`（`src/pages/Sessions`，基于 `/api/control/conversations` 的 bot 会话监控）是**两个不同概念**，请勿混淆。

### 1.3 详细字段生成函数（工程师需重点对齐）
- `sessionChatHTML(name, channel, account, hosted)` — L5959（聊天面板：托管开关/选机器人/消息气泡/输入区）
- `sessionCustomerDetailHTML(name, channel)` — L6001（客户详情/渠道客户详情双 Tab）
- `contactCustomerDetailHTML(id, name, channel, account)` — L5538（联系人详情）
- `customerDetailDrawerHTML(...)` — L5561（客户抽屉：基本信息/沟通记录/关联渠道/自定义属性）

---

## 2. 逐子版面业务逻辑

### 2.1 渠道账号管理 `channel-accounts`（L7801-7846）
- **页面目标**：集中管理私域渠道账号的接入、在线状态与席位。
- **核心用户故事**：
  - UA（运营）：作为运营，我要添加/查看企业微信、微信、WhatsApp 渠道账号，以便统一托管客户会话。
  - UA：作为运营，我要看到每个账号的「账号会话数」与在线状态，以便判断接入健康度。
- **数据实体 ChannelAccount**：`id, team_id, name, channel_type(wecom|wechat|whatsapp|business_whatsapp), protocol(如 ipad), status(online|offline), sessions_count, seats_left, energy`
- **关键交互**：
  - 顶部团队信息条：团队名（初始团队）、剩余席位、动能值（L7804-7806）
  - 「添加渠道账号」按钮 → 进入向导（L7809）
  - 账号卡片（L7818-7844）：头像+渠道类型角标（wechat-work/wechat/whatsapp）、名称、协议「企业微信·ipad协议」、在线徽标「ipad在线」、账号会话数（181）、操作【设置 / 托管管理 / 换绑团队】
- **视觉要点**：`channel-cards-grid` 网格（L7812），首张为 dashed 添加卡；卡片含 `channel-account-type wechat-work` 角标样式。

### 2.2 添加渠道账号向导（L7848-7874）
- **流程**：步骤条「①选择渠道类型 → ②添加渠道账号」。① 三选一卡片（企业微信/微信/WhatsApp，L7852-7854）；② 企业微信扫码（L7860-7866，`svgIllustration('qr')`）。
- **数据**：选择结果需落库（`channel_accounts` 新增行）。

### 2.3 托管管理 `channel-hosting`（L7876-8083）
两个 Tab：
- **批量托管（batch）**：
  - 筛选区（L7882-7971）：用户昵称、托管账号、托管AI机器人、会话类型（外部联系人/外部群聊）、添加时间（日期范围+月历 `hostingCalendarPopover`，L7928-7941）、用户标签（沟通阶段/意向程度/满意度，L7945-7955）、标签关系（且/或，L7959-7965）；操作【重置 / 查询】。
  - 表格（L7978-8047）列顺序：**☑ / 会话 / 相关客户昵称·备注 / 所属托管账号 / 添加时间 / 当前托管状态(未托管) / 托管链(-)**。
  - 表格工具（L7973-7977）：跨页全选、批量编辑托管链、编辑。
  - 分页（L8049-8056）：第 1-6 条/总共 6 条。
- **托管规则配置（rules）**（L8058-8082）：
  - 手动取消托管后恢复时间（秒，≤3600，不填则不恢复）
  - 自动取消托管（开关；开启后其他非 12Times 渠道发消息时自动取消对应会话托管）
- **数据实体**：
  - `hosting_sessions`：`session_key, account_id, customer_name, customer_remark, add_time, hosted_status(未托管|已托管), hosting_chain`
  - `hosting_rules`：`account_id(或全局), auto_resume_seconds, auto_cancel_enabled`

### 2.4 渠道会话管理 `channel-sessions`（L8085-8286）— 核心三栏
- **页面目标**：在一个工作台内完成「选账号 → 看会话 → 聊客户 → 托管机器人 → 看客户详情」。
- **核心用户故事**：
  - 客服：作为客服，我要按渠道/账号/在线状态筛选会话，快速定位未读/当前会话并回复。
  - 运营：作为运营，我要对会话一键开启/关闭机器人托管，并查看客户资料与沟通记录。
- **顶栏（L8086-8109）**：团队选择器（初始团队 / 剩余席位 0 / 新建团队 / 管理，L8088-8102）、移动端管理入口（扫码，L8105-8108）。
- **左栏 session-accounts（L8124-8163）**：
  - 渠道下拉：企业微信/微信/WhatsApp/企业WhatsApp（L8126-8132）
  - 账号搜索「托管账号名称」（L8134）
  - 状态 Tab：全部/在线/离线（L8135-8139）
  - 账号列表项：`data-status`、头像、`name`、状态「[ipad在线]/[离线]」（L8140-8162，样例：竹绿-健康/恒康倍力/福寿康）
- **中栏 session-main（L8164-8277）**：
  - 搜索「请输入会话名称」（L8167-8169）
  - 工具行（L8172-8179）：回到顶部 / 定位未读 / 定位当前 / 创建群聊 / 一键已读
  - 筛选（L8181-8197）：阅读(全部/未读)、托管(全部/已托管/未托管)
  - 会话列表行（L8199-8277）字段：`data-id, data-online, data-unread, data-hosted, data-name`；展示 头像 / 名称 / tag「外部」/ 时间 / 最后消息 / 在线状态 / 未读 badge / 归属人 owner。样例：Dr.Jack 恒康倍力、通天草-林瞰(未读2)、知足常乐【中奖】、福寿康VIP。
- **右栏 session-chat（L8279-8281，由 `sessionChatHTML` L5959 生成）**：
  - 头部：名称、渠道、机器人托管开关、选择机器人下拉（无/野风秋大健康机器人/杨奇成健康机器人/竹绿健康助手）、托管管理按钮、客户详情按钮（L5966-5977）
  - 消息区：bot/user 气泡 + 时间戳（L5979-5986）
  - 输入区：表情/图片/文件/文件夹 + 输入框 + 发送；**托管开启时输入框 disabled + 遮罩「已开启机器人托管，请关闭托管后再手动回复」**（L5987-5998）
- **右栏 session-detail（L8282-8284，由 `sessionCustomerDetailHTML` L6001 生成，默认 collapsed）**：
  - Tab：客户详情 / 渠道客户详情
  - 客户详情：头像/名称/渠道、添加标签、备注、**基本信息(电话/邮箱/公司/职位/区域/年龄/出生日期/添加时间)**、**沟通记录(0)**（添加新沟通记录）
  - 渠道客户详情：描述、添加时间、来源

### 2.5 移动端会话托管 `mobile-session-hosting`（L8288-8328）— 参考态
- 小程序原型审阅态，8 个场景导航（全部/托管中/日期/标签/批量/账号/机器人/单群）。**桌面端开发可参照其筛选维度（账号/机器人/单群/标签/日期/全部·托管中·未托管 Tab + 批量勾选），但本身非必做页面。**

### 2.6 渠道联系人列表 `channel-contacts`（L8330-8468）— 三栏
- **页面目标**：按渠道账号查看其下的联系人（客户/内部成员/群聊），并查看归属与资料。
- **左栏 contacts-accounts（L8331-8361）**：同 channel-sessions 左栏（渠道下拉 + 账号搜索 + 状态 Tab + 账号列表；样例账号 竹绿-健康/恒康倍力/福寿康）。
- **中栏 contacts-list（L8362-8463）**：
  - 搜索「请输入联系人名称/备注」（L8363-8365）
  - 类型 Tab（L8367-8371）：**客户 / 内部成员 / 客户群聊 / 内部群聊**
  - 状态 Tab（L8373-8376）：全部/在线/离线
  - 列表项（L8378-8462）：头像、`name`、`channel(@微信/@企业微信)`、状态、归属账号；字段 `data-id, data-type, data-status, data-name, data-channel, data-account`。样例：Cloud/拾柒/didi/小星星/常胜将军/快乐的小可爱（客户）、张三/李四（内部成员）、远志…/中医流体学…（客户群聊）、内部运营群（内部群聊）。
- **右栏 contacts-detail（L8465-8467，由 `contactCustomerDetailHTML` L5538 生成）**：
  - 头部：头像/名称/渠道/昵称(id)
  - 归属账号、备注(填写)/描述(填写)、添加时间、来源、**发消息**按钮

> 联系人详情字段与「客户管理-客户列表」抽屉（`customerDetailDrawerHTML` L5561）高度重合（基本信息/沟通记录/关联私域渠道/自定义属性），建议复用同一客户档案数据模型。

### 2.7 特殊渠道设置 `channel-settings`（L8470-8484）
- **页面目标**：配置企业微信接入主体（企微应用）以实现扫码授权。
- **核心交互**：
  - 标题「特殊渠道配置」+「新增企微主体」按钮（弹窗表单：企业全称/企业简称/企业ID，L8470）
  - 主体卡片网格（L8471-8483）：「企微应用配置」卡（企业全称/简称/ID + 取消/保存）；dashed「新增企微主体」卡。
- **数据实体 WechatSubject**：`id, full_name, short_name, corp_id, config_json`
- 现有前端 `ChannelSettings.tsx` 已约定契约：`GET/POST /api/channels/wechat-subjects`、`PUT /api/channels/wechat-subjects/:id`（见该文件 L12-17 注释）。

---

## 3. 现有代码缺口分析

### 3.1 前端（均位于 `src/pages/Channels/`）
| 页面 | 现状 | 与原型差距 |
|---|---|---|
| `ChannelAccounts.tsx` | 简易 mock 表格（proto-table），字段 name/type/status/onlineSessions/addedAt | **完全未对齐**：原型是卡片网格+添加向导+托管管理；缺团队信息条、协议、账号会话数、设置/托管/换绑操作、向导与托管页 |
| `ChannelSessions.tsx` | 简易 mock 表格「渠道会话托管」 | **完全未对齐**：原型是三栏 IM 收件箱（账号列表/会话列表/聊天+客户详情）；缺筛选、托管开关、客户详情抽屉、消息气泡 |
| `ChannelContacts.tsx` | 简易 mock 表格「渠道联系人」 | **未对齐**：原型是三栏（账号/联系人列表含类型Tab/详情）；缺类型Tab、状态Tab、详情面板、发消息 |
| `ChannelSettings.tsx` | 较完整（WechatSubject mock + Modal + 契约注释），USE_MOCK=true | 逻辑接近，但**未接后端**，缺后端表/路由/种子 |
| 路由 `src/router.tsx` | 已有 `/channels/accounts|contacts|sessions|settings` | 缺子路由：`/channels/accounts/add`、`/channels/accounts/:id/hosting` |
| `src/api/client.ts` | `channelsApi` 仅 `list`/`create`（L162-164） | 缺 contacts/sessions/hosting/wechat-subjects/teams 接口封装 |

### 3.2 后端（`project/backend/app/`）
**已存在（可复用）**：
- `schema.py`：`channel_accounts`(L40)、`channel_seats`(L150)、`conversations`(L127)、`messages`(L138)、`customer_tags`(L49)
- `repositories.py`：`ChannelRepository`(L159)、`ChannelSeatRepository`(L725)、`ConversationRepository`(L581)
- `routers/channels.py`：`GET/POST /channel-accounts`、`/channel-accounts/paged`
- `routers/conversations.py`：资源域会话（已标记 DEPRECATED，走 `/api/control/conversations` 契约）

**缺失（需新增）**：
| 缺失项 | 说明 |
|---|---|
| 表 `channel_contacts` | 联系人（客户/内部/群聊），原型 L8330+ |
| 表 `customer_profiles` | 客户档案：电话/邮箱/公司/职位/区域/年龄/生日/备注/来源/签名（L6001/L5561） |
| 表 `communication_records` | 沟通记录（L6029/L5606） |
| 表 `custom_attributes` | 自定义属性（L5621） |
| 表 `hosting_sessions` + `hosting_rules` | 批量托管列表与规则（L7876+） |
| 表 `wechat_subjects` | 企微主体（L8470，契约 `/api/channels/wechat-subjects`） |
| 表 `teams` | 团队（初始团队/剩余席位/动能值，L7804/L8102） |
| 扩展 `channel_accounts` | 需补 `team_id`、`protocol`（ipad） |
| 扩展会话模型 | `conversations` 缺 `account_id/external_tag/unread_count/owner/online_status`；或新建 `channel_sessions` 视图 |
| 路由 | `channel-contacts`、`channel-sessions`、`channels/wechat-subjects`、`hosting-rules`、批量托管更新、团队 均无 |
| 种子 | `channel_contacts`/`customer_profiles`/`hosting_sessions`/`wechat_subjects`/`teams` 均无种子 |

---

## 4. 需求池

### P0（必须实现，对齐原型核心）
- **P0-ACC-1**（渠道账号管理）按原型 L7801-7846 重建卡片网格：团队信息条（团队/剩余席位/动能值）、添加卡、账号卡（类型角标/协议/在线徽标/账号会话数/操作【设置·托管管理·换绑团队】）。
- **P0-ACC-2**（添加向导）步骤条「选渠道类型→扫码添加」，L7848-7874。
- **P0-ACC-3**（托管管理-批量托管）筛选区+表格（列顺序严格 L7981-7989）+跨页全选/批量编辑托管链/编辑/分页，L7876-8057。
- **P0-ACC-4**（托管规则配置）恢复时间(秒≤3600)+自动取消托管开关，L8058-8082。
- **P0-SES-1**（渠道会话管理-三栏）左栏账号列表(渠道下拉/搜索/状态Tab/账号项)、中栏会话列表(搜索/工具行/阅读·托管筛选/会话行)、右栏聊天+客户详情，L8085-8286。
- **P0-SES-2**（聊天面板）机器人托管开关、选择机器人、消息气泡、托管时禁用输入+遮罩，L5959-5999。
- **P0-SES-3**（客户详情抽屉）客户详情/渠道客户详情双 Tab + 基本信息字段 + 沟通记录，L6001-6047。
- **P0-CON-1**（渠道联系人列表-三栏）左栏账号 + 中栏(类型Tab 客户/内部成员/客户群聊/内部群聊 + 状态Tab + 列表) + 右栏详情(归属账号/备注/描述/添加时间/来源/发消息)，L8330-8468。
- **P0-SET-1**（特殊渠道设置）企微主体卡片网格 + 新增弹窗(企业全称/简称/ID) + 保存，L8470-8484。
- **P0-DATA-1** 所有列表/详情数据**从数据库获取**（替换现有 MOCK）；缺失数据用种子填充并同步 DB。
- **P0-API-1** 新增后端路由与 Repository：`channel-contacts`、`channel-sessions`(区分于 control 契约)、`channels/wechat-subjects`、`hosting-rules`/批量托管更新、`teams`。

### P1（重要交互）
- **P1-SES-4** 会话交互：一键已读、定位未读、定位当前、创建群聊、回到顶部（L8174-8178）。
- **P1-SES-5** 筛选生效：阅读(全部/未读)、托管(全部/已托管/未托管)、账号状态(全部/在线/离线)、渠道切换。
- **P1-CON-2** 联系人类型/状态/关键字筛选联动；详情「发消息」跳转对应会话。
- **P1-ACC-5** 托管管理筛选全部生效（昵称/托管账号/机器人/会话类型/添加时间范围/标签+且或关系）+ 查询/重置。
- **P1-DATA-2** 客户档案(电话/邮箱/公司/职位/区域/年龄/生日/备注/来源/签名)、沟通记录、自定义属性落库并可编辑（复用客户管理模型）。
- **P1-SET-2** 企微主体新增/编辑/保存写入 `wechat_subjects`，对接后端。

### P2（增强）
- **P2-SES-6** 移动端会话托管小程序原型（L8288-8328）的桌面审阅态（筛选维度参考，非必做页面）。
- **P2-ACC-6** 换绑团队、团队新建/管理（`teams` 实体与弹窗）。
- **P2-SES-7** 客户详情「添加标签」联动 `customer_tags`；沟通记录 AI 总结展示（L5569 样例）。
- **P2-CON-3** 联系人与客户管理「客户列表」档案打通（同一 `customer_profiles`）。
- **P2-UI** 严格复用原型 CSS class（`session-*`、`contacts-*`、`hosting-*`、`channel-*`）与状态标签样式，保证视觉 1:1。

---

## 5. UI 设计稿要点（引原型行号）
- **整体布局**：渠道账号/会话/联系人均为左(账号列表, ~260px) + 中(主列表) + 右(详情) 三栏；会话管理右栏再分聊天+客户详情。
- **状态标签样式**：账号在线 `dot online` / 离线 `dot offline`（L8145/L8159）；会话外部 tag `session-row-tag`（L8206）；未读 `unread-badge`（L8235）；托管状态 `hosting-status`（L7998，未托管）。
- **表格列顺序（托管管理，严格对齐 L7981-7989）**：☑ → 会话 → 相关客户昵称/备注 → 所属托管账号 → 添加时间 → 当前托管状态 → 托管链。
- **筛选控件**：统一用 `import-select` 下拉（L7889 等）、`session-filter-select`（L8182）、`account-status-tab`（L8135）。
- **渠道类型图标**：`channelTypeIcon` 映射 wechat-work/wechat/whatsapp（L2244-2251），账号角标 `channel-account-type wechat-work`。
- **弹窗**：`showModal(title, body)`（L8470、L5648 等），新增主体/备注/沟通记录均用此机制。

---

## 6. 数据需求与种子方案

### 6.1 需新增/扩展的表
| 表 | 关键字段 | 关联子版面 |
|---|---|---|
| `teams`(新) | id, name, seats_left, energy_value | ACC/SES 顶部 |
| `channel_accounts`(扩) | + team_id, + protocol | ACC |
| `channel_contacts`(新) | id, account_id, channel, name, nickname, type(customer/internal/customer_group/internal_group), status, remark, description, add_time, source | CON |
| `customer_profiles`(新) | id, contact_id, phone, email, company, position, region, age, birthday, remark, add_time, add_channel, signature | SES/CON 详情 |
| `communication_records`(新) | id, customer_id, content, ai_summary, created_at, type | SES/CON 详情 |
| `custom_attributes`(新) | id, customer_id, name, value | 客户详情 |
| `hosting_sessions`(新) | session_key, account_id, customer_name, customer_remark, add_time, hosted_status, hosting_chain | ACC 托管 |
| `hosting_rules`(新) | account_id, auto_resume_seconds, auto_cancel_enabled | ACC 托管 |
| `wechat_subjects`(新) | id, full_name, short_name, corp_id, config_json | SET |

### 6.2 种子数据量级建议
- `teams`：1 条（初始团队，剩余席位 0-1，动能值 908）。
- `channel_accounts`：3 条（竹绿-健康/wecom/ipad在线/会话181；恒康倍力/wecom/在线；福寿康/wechat/离线）。
- `channel_contacts`：≥10 条，覆盖 4 种 type（客户 7 + 内部成员 2 + 客户群聊 2 + 内部群聊 1），均归属「竹绿-健康」。
- `customer_profiles`：对主要联系人各 1 条（基础信息半数留 `--`，添加时间 2026-06-30/07-03）。
- `hosting_sessions`：6 条（洋洋/Min/xıngyue/文/丽丽/Cloud，均「未托管」，竹绿-健康，2026-06-30）。
- `hosting_rules`：1 条默认（auto_resume_seconds 空、auto_cancel_enabled=false）。
- `wechat_subjects`：1 条（医林通健康科技 / 医林通 / ww8f2a1c3d4e5）。
- `communication_records` / `custom_attributes`：各 0-1 条（演示空态与有态）。
- 现有 `conversations` 可作为 channel-sessions 中栏数据源之一（需补 account_id/external_tag/unread/owner/online 字段或建视图）。

---

## 7. 待确认问题（原型歧义 / 范围）
1. **「渠道会话管理」数据模型归属**：是否复用现有 `conversations` 表（扩展列）还是新建 `channel_sessions` 视图？现有 `conversations` 已被标记 DEPRECATED 且仅服务资源域。建议新建，避免与 `/api/control/conversations` 契约耦合。
2. **API 路径前缀不一致**：现有 `/channel-accounts`（无 /api），ChannelSettings 注释用 `/api/channels/wechat-subjects`。新增 contacts/sessions/hosting 接口建议统一前缀（推荐 `/channels/...` 与现有 channel-accounts 对齐）。
3. **「团队」范围**：团队选择器在 ACC/SES 均出现，但是否属于「渠道会话」本期范围？还是归入组织管理？建议本期做最小 `teams` 表 + 只读展示/新建。
4. **移动端 `mobile-session-hosting`**：列为 P2 参考态，是否本期完全不做？其筛选维度（账号/机器人/单群/标签/日期）是否需回填到桌面端托管管理？
5. **客户档案复用**：渠道联系人详情字段与「客户管理-客户列表」高度重合，是否共享 `customer_profiles` 表（跨栏目统一）？需与客户管理模块负责人对齐。
6. **「换绑团队 / 托管管理(单账号)」入口**：ACC 卡片操作【托管管理】打开的是 `channel-hosting` 全局批量页还是该账号维度页？原型 L7841 `openHostingMgmt('竹绿-健康')` 传了账号名，建议按账号预筛。
7. **真实渠道接入**：扫码添加账号、企微扫码授权为真实集成，本期可否仅做 UI+种子（mock 接入状态）？

---

## 8. 结论
- 原型「渠道会话」含 **4 个主子版面 + 3 个子流程（添加向导/托管管理/移动端参考）**，业务逻辑以上已逐版面拆解，行号可溯源。
- 前端 4 个页面目前均为**简易 mock 表格，与原型偏差极大**，需按原型三栏结构重建；`ChannelSettings.tsx` 最接近。
- 后端缺 **contacts/customer_profiles/communication/custom_attributes/hosting/wechat_subjects/teams** 等表与对应路由、种子。
- 建议按 P0→P1→P2 推进，所有数据从 DB 获取、缺失用种子填充；视觉严格对齐原型 class 与状态标签。
