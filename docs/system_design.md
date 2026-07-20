# Morphix「渠道会话」栏目 — 系统架构设计与任务分解

> 设计者：高见远（software-architect）　|　依据：PRD `docs/prd-channels.md` + 原型 `prototype/index.html`（行号溯源）+ 现有前后端代码
> 后端：FastAPI + 裸 SQL `DatabaseBackend`（SQLite，`database/morphix_mvp.db`，端口 2181）；`MORPHIX_DEV=1` 启动 `init_schema()` + `seed_defaults()`
> 前端：Vite + React18 + TS(strict) + MUI + Tailwind + lucide-react（端口 5183，代理 `/api` → 2181）
> 交付物：`docs/system_design.md` / `docs/class-diagram.mermaid` / `docs/sequence-diagram.mermaid`（覆盖旧的 message-logs 文档）

---

## 一、实现方案与框架选型

**沿用既有技术栈，不引入任何新框架/依赖（零新增包）。**

- **后端**：FastAPI + `DatabaseBackend`（裸 SQL，占位符 `?`）+ Pydantic v2。沿用 Repository 模式（SQL 集中在 `repositories.py`，Router 只调方法）。新增 `routers/channel_mgmt.py`，在 `routers/__init__.py` 中以 `api_router.include_router(...)` 挂载（统一 `/api` 前缀）。
- **前端**：React + TS(strict)，复用 `src/api/client.ts` 的封套感知 `api` 客户端；弹窗复用 `src/components/common/Modal.tsx`；图标复用已装的 `lucide-react`（渠道类型角标用 `channelTypeIcon` 映射 SVG）。
- **架构模式**：经典「Router → Repository → DatabaseBackend」三层；前端采用「页面组件 → 共享子组件 → `channelsApi` → 后端」的单向数据流，三栏布局用受控 state（`selectedAccountId` / `selectedSessionId` / `selectedContactId`）驱动。

**核心策略**
1. **真实接入**：本期所有列表/详情数据从 DB 获取（`USE_MOCK=false`）；缺失数据用种子填充并同步 DB。
2. **数据模型**：新建 `channel_sessions` 表承载「渠道会话管理」IM 收件箱（不复用已 DEPRECATED 的 `conversations`）；新建 `hosting_sessions` 投影表承载「托管管理」批量页（与原型两个屏幕数据天然不同，见 §七 Q1）。
3. **API 前缀统一**：本期新增渠道管理接口统一落 `/api/channels/...`（复数），与 `ChannelSettings.tsx` 既有契约 `/api/channels/wechat-subjects` 对齐；遗留 `/api/channel-accounts` 保留不变（向后兼容）。详见 §七 Q2。

---

## 二、文件列表（新增 / 修改，相对仓库根）

### 后端（`project/backend/app/`）
| 文件 | 动作 | 说明 |
|---|---|---|
| `schema.py` | 修改 | `SCHEMA_SQL`/`INDEX_SQL` 追加新表 + `channel_accounts` 扩展列；`migrate_schema` 追加幂等 ALTER；`seed_defaults` 追加种子块 |
| `database/init_morphix_mvp.sql` | 修改 | 同步追加相同 DDL（运行时以 `schema.py` 为准，此文件作独立初始化快照） |
| `repositories.py` | 修改 | 新增 `ChannelMgmtRepository`（accounts/contacts/sessions/hosting/wechat-subjects/teams 读写）+ `row_to_*` 映射 |
| `routers/channel_mgmt.py` | 新增 | 本期全部新增路由（`/channels/...`） |
| `routers/__init__.py` | 修改 | `include_router(channel_mgmt.router)` |
| `schemas.py` | 修改 | 新增请求模型（创建/更新渠道账号、托管规则、批量托管更新、企微主体等） |

### 前端（`src/`）
| 文件 | 动作 | 说明 |
|---|---|---|
| `api/client.ts` | 修改 | 扩展 `channelsApi`：accounts/contacts/sessions/hosting/wechat-subjects/teams/hosting-bots |
| `router.tsx` | 修改 | 增加子路由 `/channels/accounts/add`、`/channels/accounts/:id/hosting` |
| `types/channels.ts` | 新增 | 渠道域 DTO 类型（Account/Contact/Session/HostingSession/HostingRule/WechatSubject/Team/CustomerProfile…） |
| `pages/Channels/ChannelAccounts.tsx` | 重写 | 卡片网格 + 团队信息条（P0-ACC-1） |
| `pages/Channels/AccountAdd.tsx` | 新增 | 添加渠道账号向导（P0-ACC-2） |
| `pages/Channels/ChannelHosting.tsx` | 新增 | 托管管理：批量托管 + 规则配置（P0-ACC-3/4） |
| `pages/Channels/ChannelSessions.tsx` | 重写 | 三栏 IM 收件箱（P0-SES-1） |
| `pages/Channels/ChannelContacts.tsx` | 重写 | 三栏联系人（P0-CON-1） |
| `pages/Channels/ChannelSettings.tsx` | 重写 | 接真实后端（P0-SET-1 / P1-SET-2），`USE_MOCK=false` |
| `pages/Channels/shared/TeamInfoBar.tsx` | 新增 | 团队信息条（ACC/SES 复用） |
| `pages/Channels/shared/TeamSelector.tsx` | 新增 | SES 顶栏团队选择器（含新建/管理入口占位） |
| `pages/Channels/shared/AccountListPanel.tsx` | 新增 | 左栏账号列表（渠道下拉+搜索+状态Tab，SES/CON 复用） |
| `pages/Channels/shared/ChannelTypeBadge.tsx` | 新增 | 渠道类型角标（wechat-work/wechat/whatsapp） |
| `pages/Channels/shared/StatusDot.tsx` | 新增 | 在线/离线状态点 |
| `pages/Channels/sessions/SessionChatPanel.tsx` | 新增 | 右栏聊天面板（托管开关/选机器人/气泡/输入遮罩） |
| `pages/Channels/sessions/SessionCustomerDetail.tsx` | 新增 | 右栏客户详情抽屉（双 Tab + 基本信息 + 沟通记录） |
| `pages/Channels/contacts/ContactDetailPanel.tsx` | 新增 | 右栏联系人详情（归属/备注/描述/来源/发消息） |
| `pages/Channels/*.css` | 修改/新增 | 复用 `prototype.css` 既有 `.channel-*`/`.session-*`/`.contacts-*`/`.hosting-*` class，补少量局部样式 |

---

## 三、数据库 Schema 变更（DDL）

### 3.1 扩展既有 `channel_accounts`（追加列，新库 CREATE 直带、旧库 `migrate_schema` ALTER）
```sql
ALTER TABLE channel_accounts ADD COLUMN team_id       TEXT    NOT NULL DEFAULT '';
ALTER TABLE channel_accounts ADD COLUMN channel_type  TEXT    NOT NULL DEFAULT '';   -- wecom|wechat|whatsapp|business_whatsapp
ALTER TABLE channel_accounts ADD COLUMN protocol      TEXT    NOT NULL DEFAULT '';   -- 如 'ipad'
ALTER TABLE channel_accounts ADD COLUMN sessions_count INTEGER NOT NULL DEFAULT 0;   -- 账号会话数
```
> 旧列 `channel`(显示名如「企业微信」)、`account_name`、`status`、`bound_bot`、`daily_quota` 保留；`channel_seats`(seats_left/online_sessions) 保留作「账号在线会话」用途，与团队席位（teams.seats_left）区分。

### 3.2 新增表（CREATE IF NOT EXISTS，并入 `SCHEMA_SQL`）
```sql
CREATE TABLE IF NOT EXISTS teams (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  seats_left  INTEGER NOT NULL DEFAULT 0,
  energy_value INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_contacts (
  id          TEXT PRIMARY KEY,
  account_id  TEXT NOT NULL,
  channel     TEXT NOT NULL DEFAULT '',       -- 显示：@微信 / @企业微信
  channel_type TEXT NOT NULL DEFAULT 'wechat',-- wecom|wechat|whatsapp|business_whatsapp
  name        TEXT NOT NULL,
  nickname    TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'customer', -- customer|internal|customer_group|internal_group
  status      TEXT NOT NULL DEFAULT 'online',   -- online|offline
  remark      TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  add_time    TEXT NOT NULL DEFAULT '',
  source      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS customer_profiles (
  id          TEXT PRIMARY KEY,
  contact_id  TEXT NOT NULL,                    -- FK channel_contacts.id
  phone       TEXT NOT NULL DEFAULT '',
  email       TEXT NOT NULL DEFAULT '',
  company     TEXT NOT NULL DEFAULT '',
  position    TEXT NOT NULL DEFAULT '',
  region      TEXT NOT NULL DEFAULT '',
  age         INTEGER,
  birthday    TEXT NOT NULL DEFAULT '',
  remark      TEXT NOT NULL DEFAULT '',
  add_time    TEXT NOT NULL DEFAULT '',
  add_channel TEXT NOT NULL DEFAULT '',
  signature   TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS communication_records (
  id          TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,                    -- FK customer_profiles.id
  content     TEXT NOT NULL DEFAULT '',
  ai_summary  TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'note',     -- note|call|...
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS custom_attributes (
  id          TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,                    -- FK customer_profiles.id
  name        TEXT NOT NULL DEFAULT '',
  value       TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_sessions (    -- 渠道会话管理(IM 收件箱) 核心表
  id            TEXT PRIMARY KEY,
  account_id    TEXT NOT NULL,
  contact_id    TEXT,                            -- FK channel_contacts.id (可空)
  name          TEXT NOT NULL,
  channel       TEXT NOT NULL DEFAULT '',
  channel_type  TEXT NOT NULL DEFAULT 'wechat',
  last_message  TEXT NOT NULL DEFAULT '',
  last_time     TEXT NOT NULL DEFAULT '',
  unread_count  INTEGER NOT NULL DEFAULT 0,
  read_status   TEXT NOT NULL DEFAULT 'unread', -- read|unread
  hosted_status TEXT NOT NULL DEFAULT 'unhosted', -- hosted|unhosted
  hosted_bot_id TEXT,
  owner         TEXT NOT NULL DEFAULT '',
  online_status TEXT NOT NULL DEFAULT 'online',  -- online|offline
  session_type  TEXT NOT NULL DEFAULT '外部联系人',-- 外部联系人|外部群聊
  external_tag  TEXT NOT NULL DEFAULT '外部',
  add_time      TEXT NOT NULL DEFAULT '',
  hosting_chain TEXT NOT NULL DEFAULT '-'
);

CREATE TABLE IF NOT EXISTS hosting_sessions (    -- 托管管理(批量页) 投影表
  id             TEXT PRIMARY KEY,
  session_key    TEXT NOT NULL DEFAULT '',        -- 关联 channel_sessions.id(预留)
  account_id     TEXT NOT NULL,
  customer_name  TEXT NOT NULL DEFAULT '',
  customer_remark TEXT NOT NULL DEFAULT '',
  add_time       TEXT NOT NULL DEFAULT '',
  hosted_status  TEXT NOT NULL DEFAULT 'unhosted',-- hosted|unhosted
  hosting_chain  TEXT NOT NULL DEFAULT '-'
);

CREATE TABLE IF NOT EXISTS hosting_rules (
  id                  TEXT PRIMARY KEY,
  account_id          TEXT,                       -- NULL = 全局
  auto_resume_seconds INTEGER,                    -- NULL = 不恢复
  auto_cancel_enabled INTEGER NOT NULL DEFAULT 0, -- 0|1
  created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wechat_subjects (
  id          TEXT PRIMARY KEY,
  full_name   TEXT NOT NULL,
  short_name  TEXT NOT NULL,
  corp_id     TEXT NOT NULL,
  config_json TEXT NOT NULL DEFAULT '{}'
);
```

### 3.3 索引（并入 `INDEX_SQL`）
```sql
CREATE INDEX IF NOT EXISTS idx_channel_accounts_team      ON channel_accounts(team_id);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_ctype    ON channel_accounts(channel_type, status);
CREATE INDEX IF NOT EXISTS idx_channel_contacts_account  ON channel_contacts(account_id, type, status);
CREATE INDEX IF NOT EXISTS idx_channel_sessions_account  ON channel_sessions(account_id, read_status, hosted_status, online_status);
CREATE INDEX IF NOT EXISTS idx_hosting_sessions_account  ON hosting_sessions(account_id, hosted_status);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_contact ON customer_profiles(contact_id);
CREATE INDEX IF NOT EXISTS idx_communication_records_cust ON communication_records(customer_id);
CREATE INDEX IF NOT EXISTS idx_custom_attributes_cust    ON custom_attributes(customer_id);
```

### 3.4 DDL 同步
在 `database/init_morphix_mvp.sql` 末尾追加 **完全相同** 的扩展列 + 9 张新表 DDL + 索引，保证与 `schema.py` 一致（运行时以 `schema.py` 为准，该文件仅作独立快照）。

---

## 四、后端 API 设计

新增路由文件 `routers/channel_mgmt.py`：`APIRouter(prefix="/channels", tags=["channels"])`，由 `api_router`（前缀 `/api`）挂载 → 完整路径以 `/api/channels/...` 开头。

### 4.1 路由总表
| 方法 | 路径 | 说明 | 查询/路径参数 | 请求体 |
|---|---|---|---|---|
| GET | `/channels/teams` | 团队列表（ACC/SES 顶部） | — | — |
| POST | `/channels/teams` | 新建团队（P2） | — | `{name, seatsLeft?, energyValue?}` |
| GET | `/channels/accounts` | 渠道账号列表（**扩展 DTO**，含 team/protocol/sessionsCount） | — | — |
| POST | `/channels/accounts` | 添加渠道账号（向导完成） | — | `{channelType, protocol?, teamId?, name?}` |
| GET | `/channels/contacts` | 联系人列表（筛选） | `accountId,type,status,search` | — |
| GET | `/channels/contacts/{id}` | 联系人详情（含 profile/沟通记录/自定义属性） | — | — |
| GET | `/channels/sessions` | 会话列表（IM 收件箱，筛选） | `accountId,read,hosted,online,search` | — |
| GET | `/channels/sessions/{id}/messages` | 会话消息（聊天面板） | — | — |
| POST | `/channels/sessions/{id}/hosting` | 开启/关闭托管 + 选机器人 | — | `{hosted:bool, botId?:string|null}` |
| GET | `/channels/hosting-sessions` | 托管批量列表（筛选） | `accountId,botId,sessionType,nickname,start,end` | — |
| POST | `/channels/hosting-sessions/batch-update` | 批量编辑托管状态/链 | — | `{ids:[],hostedStatus?,hostingChain?}` |
| GET | `/channels/hosting-rules` | 托管规则 | `accountId?` | — |
| PUT | `/channels/hosting-rules` | 保存托管规则 | — | `{accountId?,autoResumeSeconds?,autoCancelEnabled?}` |
| GET | `/channels/wechat-subjects` | 企微主体列表 | — | — |
| POST | `/channels/wechat-subjects` | 新增企微主体 | — | `{fullName,shortName,corpId,configJson?}` |
| PUT | `/channels/wechat-subjects/{id}` | 更新企微主体 | — | `{fullName,shortName,corpId,configJson?}` |
| GET | `/channels/hosting-bots` | 托管可选机器人（静态配置） | — | — |

> 遗留 `GET/POST /api/channel-accounts`（`routers/channels.py`）**保留不变**，本期新版页面改用 `/api/channels/accounts`。

### 4.2 关键响应结构（裸数据，无封套，与资源域一致）
- `GET /channels/accounts` 单项：
  ```json
  {"id":"acc-zhulu","name":"竹绿-健康","channel":"企业微信","channelType":"wecom",
   "protocol":"ipad","status":"online","online":true,"sessionsCount":181,
   "teamId":"team-initial","boundBot":"yefengqiu"}
  ```
- `GET /channels/contacts` 单项：
  ```json
  {"id":"c-cloud","accountId":"acc-zhulu","name":"Cloud","channel":"@微信","channelType":"wechat",
   "type":"customer","status":"online","remark":"","description":"","addTime":"2026-06-30 18:29:18","source":"扫码"}
  ```
- `GET /channels/contacts/{id}` 返回 `{contact, profile, communications:[], attributes:[]}`。
- `GET /channels/sessions` 单项：
  ```json
  {"id":"ses-drjack","accountId":"acc-zhulu","contactId":"c-cloud","name":"Dr.Jack 恒康倍力",
   "channel":"@微信","lastMessage":"可以的，后续可以用","lastTime":"10:36",
   "unreadCount":0,"readStatus":"read","hostedStatus":"hosted","hostedBotId":"yefengqiu",
   "owner":"竹","onlineStatus":"online","sessionType":"外部联系人","externalTag":"外部"}
  ```
- `GET /channels/hosting-sessions` 单项：
  ```json
  {"id":"hs-yangyang","accountId":"acc-zhulu","customerName":"洋洋","customerRemark":"",
   "addTime":"2026-06-30 18:29:12","hostedStatus":"unhosted","hostingChain":"-"}
  ```
- `GET /channels/hosting-bots` 返回：`[{"id":"yefengqiu","name":"野风秋大健康机器人"},{"id":"yangqicheng","name":"杨奇成健康机器人"},{"id":"zhulu","name":"竹绿健康助手"}]`（静态配置 `HOSTING_BOTS`，无需建表）。

### 4.3 `ChannelMgmtRepository` 方法清单（`repositories.py`）
- `list_teams() / create_team(...)`
- `list_accounts_enriched()`（JOIN `channel_accounts`+`channel_seats`+`teams`）
- `create_account(channel_type, protocol, team_id, name?)`
- `list_contacts(account_id?, type?, status?, search?)`
- `get_contact_detail(contact_id)`（聚合 `customer_profiles`+`communication_records`+`custom_attributes`）
- `list_sessions(account_id?, read?, hosted?, online?, search?)`
- `list_session_messages(session_id)`（复用既有 `messages` 表，`conversation_id=session_id`）
- `set_session_hosting(session_id, hosted, bot_id)`（UPDATE `channel_sessions`）
- `list_hosting_sessions(account_id?, bot_id?, session_type?, nickname?, start?, end?)`
- `batch_update_hosting(ids, hosted_status?, hosting_chain?)`
- `get_hosting_rules(account_id?) / upsert_hosting_rules(...)`
- `list_wechat_subjects() / create_wechat_subject(...) / update_wechat_subject(id, ...)`
- `list_hosting_bots()`（返回 `HOSTING_BOTS`）

### 4.4 `schemas.py` 新增请求模型
`ChannelAccountUpsertRequest{channelType, protocol?, teamId?, name?}`、`HostingRuleRequest{accountId?, autoResumeSeconds?, autoCancelEnabled?}`、`HostingBatchUpdateRequest{ids:list[str], hostedStatus?, hostingChain?}`、`SessionHostingRequest{hosted:bool, botId?}`、`WechatSubjectCreateRequest{fullName, shortName, corpId, configJson?}`、`WechatSubjectUpdateRequest`（同上）、`TeamCreateRequest{name, seatsLeft?, energyValue?}`。

---

## 五、前端组件拆分（三栏组件树）

### 5.1 渠道账号管理 ACC（`/channels/accounts`）
```
ChannelAccountsPage
├─ TeamInfoBar                 (团队名 / 剩余席位 / 动能值)  ← shared
├─ AccountCardGrid
│   ├─ AccountAddCard          (虚线添加卡 → /channels/accounts/add)
│   └─ AccountCard            (头像 + 渠道角标 + 在线徽标[ipad在线] + 协议 + 账号会话数 + 操作[设置/托管管理/换绑团队])
├─ AccountAdd (路由 /channels/accounts/add)  步骤条[选渠道类型→扫码]
└─ ChannelHosting (路由 /channels/accounts/:id/hosting)
    ├─ Tabs[批量托管 | 托管规则配置]
    ├─ HostingFilters         (昵称/托管账号/机器人/会话类型/添加时间/标签+且或 + 重置/查询)
    ├─ HostingTable           (列:☑/会话/相关客户昵称·备注/所属托管账号/添加时间/托管状态/托管链)
    │   └─ HostingTableRow
    ├─ HostingTableTools      (跨页全选/批量编辑托管链/编辑/分页)
    └─ HostingRulesCard       (恢复时间(秒≤3600)/自动取消托管开关/保存)
```

### 5.2 渠道会话管理 SES（`/channels/sessions`）
```
ChannelSessionsPage
├─ SessionTopbar              (TeamSelector + 剩余席位 + 移动端管理入口QR)  ← shared
├─ AccountListPanel (左)      ← shared (渠道下拉 + 账号搜索 + 状态Tab[全部/在线/离线] + 账号列表)
├─ SessionMainPanel (中)
│   ├─ Toolbar                (会话名称搜索 + 工具行[回到顶部/定位未读/定位当前/创建群聊/一键已读])
│   ├─ Filters                (阅读[全部/未读] + 托管[全部/已托管/未托管])
│   └─ SessionList
│       └─ SessionRow         (头像/名称/external tag/时间/最后消息/在线状态/未读badge/归属人)
├─ SessionChatPanel (右1)     → sessionChatHTML
│   ├─ ChatHeader             (名称/渠道/托管开关/选机器人下拉/托管管理/客户详情)
│   ├─ ChatMessages           (bot/user 气泡 + 时间戳)
│   └─ ChatInputWrap          (表情/图片/文件/文件夹 + 输入 + 发送；托管开启→disabled + 遮罩)
└─ SessionCustomerDetail (右2, 默认 collapsed)  → sessionCustomerDetailHTML
    ├─ Tabs[客户详情 | 渠道客户详情]
    ├─ 客户详情 (头像/名称/渠道/添加标签/备注/基本信息[电话/邮箱/公司/职位/区域/年龄/生日/添加时间]/沟通记录)
    └─ 渠道客户详情 (描述/添加时间/来源)
```

### 5.3 渠道联系人列表 CON（`/channels/contacts`）
```
ChannelContactsPage
├─ AccountListPanel (左)      ← shared
├─ ContactsListPanel (中)
│   ├─ Search                 (联系人名称/备注)
│   ├─ TypeTabs               (客户/内部成员/客户群聊/内部群聊)
│   ├─ StatusTabs             (全部/在线/离线)
│   └─ ContactList
│       └─ ContactRow         (头像/名称/@渠道/状态/归属于：账号)
└─ ContactDetailPanel (右)    → contactCustomerDetailHTML
    ├─ Header (头像/名称/渠道/昵称id)
    └─ Body   (归属账号/备注(填写)/描述(填写)/添加时间/来源/发消息按钮)
```
> 联系人详情字段与「客户管理-客户列表」抽屉共用 `customer_profiles`，本期右栏取 `GET /channels/contacts/{id}` 聚合数据（见 §七 Q5）。

### 5.4 特殊渠道设置 SET（`/channels/settings`）
```
ChannelSettingsPage   (重写：USE_MOCK=false，接 /channels/wechat-subjects)
├─ 主体卡片网格
│   ├─ WechatConfigCard   (企业全称/简称/ID + 取消/保存)
│   └─ AddCard            (虚线新增 → Modal)
└─ AddSubjectModal       (企业全称/简称/ID → POST)
```

### 5.5 共享（ACC/SES 复用）
`TeamInfoBar`、`TeamSelector`、`AccountListPanel`、`ChannelTypeBadge`、`StatusDot`、`types/channels.ts`、`channelsApi`。

---

## 六、依赖包列表

**无新增依赖。**
- 后端：沿用 FastAPI / SQLite（标准库）/ Pydantic v2，`DatabaseBackend` 裸 SQL，不引入 ORM 或任何第三方库。
- 前端：图标复用已装的 `lucide-react`；MUI/Tailwind 已在栈；不新增 npm 包。

---

## 七、PRD 第 7 节「7 个待确认问题」设计决策与理由

| # | 问题 | 决策 | 理由 |
|---|---|---|---|
| Q1 | 渠道会话数据模型归属 | **新建 `channel_sessions` 表**；另建 `hosting_sessions` 投影表 | `conversations` 已 DEPRECATED 且服务 `/api/control` 契约，字段（缺 account_id/external_tag/unread/owner/online）与 IM 收件箱语义不同；原型中「会话管理」(4 条：Dr.Jack/通天草/知足常乐/福寿康VIP) 与「托管管理」(6 条：洋洋/Min/xıngyue/文/丽丽/Cloud) 数据天然不同，分表最贴合原型、零漂移。 |
| Q2 | API 前缀不一致 | 本期新增统一 `/api/channels/...`（复数）；遗留 `/api/channel-accounts` 保留 | 与 `ChannelSettings.tsx` 既有契约 `/api/channels/wechat-subjects` 对齐；复数前缀语义更清晰；旧路由不动避免契约回归。 |
| Q3 | 团队范围 | 最小 `teams` 表 + 只读展示；P0 仅展示初始团队；P2 再做新建/管理弹窗 | ACC/SES 顶部均依赖团队条；本期聚焦渠道会话，团队作为只读上下文即可，新建团队（`POST /channels/teams`）留 P2。 |
| Q4 | 移动端 `mobile-session-hosting` | 桌面端不做独立页面；其筛选维度（账号/机器人/单群/标签/日期）回填进桌面托管管理筛选区 | 原型列为 P2 参考态；其筛选维度已纳入 `hosting-sessions` 查询参数（accountId/botId/sessionType/nickname/start/end），移动端入口仅保留「扫码」UI 占位。 |
| Q5 | 客户档案复用 | 渠道联系人与「客户管理-客户列表」共用 `customer_profiles`（跨栏目统一） | 详情字段高度重合（基本信息/沟通记录/自定义属性）；本期 `customer_profiles.contact_id` 关联 `channel_contacts`，右栏直接聚合返回；P2 再与客户管理打通写路径（§六 任务分解标注）。 |
| Q6 | 托管管理入口（单账号/全局） | ACC 卡片「托管管理」→ 全局批量页 `/channels/accounts/:id/hosting`，**按当前账号名预筛** | 原型 `openHostingMgmt('竹绿-健康')` 传账号名；路由带 `:id` 并初始 `accountId` 查询参数预筛，符合「按账号预筛」且复用同一批量页。 |
| Q7 | 真实渠道接入 | 扫码添加账号、企微扫码授权本期仅 UI + 种子 mock | 不接真实第三方网关；`POST /channels/accounts` 仅落库并置 `online` + `protocol='ipad'`；企微授权弹窗仅展示二维码 UI，不发起真实 OAuth。 |

> 另：原型团队席位在 ACC 页显示「剩余席位 1」(L7805)、SES 顶栏显示「剩余席位 0」(L8103)，存在不一致。本设计统一以 `teams.seats_left` 为单一来源，种子取 **1**（对齐 ACC 团队信息条这一最明确规范），两页读同一值（SES 顶栏因此显示 1，与原型 0 差 1，属原型自身不一致，接受）。

---

## 八、种子数据方案（表 / 量级 / 幂等守卫落地位置）

### 8.1 幂等守卫约定（沿用现有 `_count(...) == 0` 模式，仅空表写入）
全部写入位于 `schema.py` 的 `seed_defaults(backend)` 内，沿用既有 `if _count(backend, "SELECT COUNT(*) AS c FROM <表>") == 0:` 守卫；扩展列通过 `migrate_schema` 的 `_has_column` 检测后 `ALTER TABLE` 幂等追加。**改种子后验证需删除 `database/morphix_mvp.db` 重启后端重新生成**（与现有约定一致）。

### 8.2 种子量级与关键行
| 表 | 量级 | 关键内容 |
|---|---|---|
| `teams` | 1 | `(team-initial, 初始团队, seats_left=1, energy_value=908)` |
| `channel_accounts` | 3（**替换**原有 ch-1/2/3 demo 行，对齐原型） | `acc-zhulu`(企业微信/竹绿-健康/online/ipad/会话181/team-initial/bound_bot=yefengqiu)、`acc-hengkang`(企业微信/恒康倍力/online/ipad/会话73)、`acc-fushou`(微信/福寿康/offline//会话12) |
| `channel_seats` | 3（随账号 id 更新） | `(acc-zhulu,580,20)`/`(acc-hengkang,285,15)`/`(acc-fushou,110,10)` |
| `channel_contacts` | 12（均属 `acc-zhulu`） | 客户7(Cloud/拾柒/didi/小星星/常胜将军/快乐的小可爱/开心)+内部2(张三/李四)+客户群聊2(远志…/中医流体学入门会员)+内部群聊1(内部运营群) |
| `customer_profiles` | 5 | 对 Cloud/didi/张三/常胜将军/开心 各 1 条（半数字段留空 `--`，add_time 2026-06-30/07-03） |
| `communication_records` | 1 | didi 一条演示「有态」记录 |
| `custom_attributes` | 1 | didi 一条自定义属性 |
| `channel_sessions` | 4 | ses-drjack(在线/已读/已托管/yefengqiu)、ses-tongtian(在线/未读2/未托管)、ses-zhizu(离线/已读/已托管)、ses-fushou(离线/已读/未托管)，均属 acc-zhulu |
| `messages`（复用既有表） | ~8 | 为上述 4 个 `channel_sessions.id` 各写 1–3 条（conversation_id=session_id），ses-drjack 写入原型 Dr.Jack 对话气泡（L5980-5986） |
| `hosting_sessions` | 6 | 洋洋/Min/xıngyue/文/丽丽/Cloud，均 acc-zhulu，add_time 2026-06-30 18:27–18:29，hosted_status=unhosted，hosting_chain='-' |
| `hosting_rules` | 1 | `(全局 NULL, auto_resume_seconds=NULL, auto_cancel_enabled=0)` |
| `wechat_subjects` | 1 | `(wx-subj-1, 医林通健康科技, 医林通, ww8f2a1c3d4e5, '{}')` |
| `hosting_bots` | 静态配置（非表） | `HOSTING_BOTS = [yefengqiu, yangqicheng, zhulu]` |

> **注意事项**：`channel_accounts` 种子由原有 3 条 demo 改为原型 3 条，需同步把 `channel_seats` 种子 id 改为 `acc-zhulu/acc-hengkang/acc-fushou`（`channel_seats.channel_account_id` 逻辑关联，无外键约束）。其他功能（如 `message_logs`）仅用账号名字符串、无硬 FK，不受替换影响；若概览页等处引用旧 demo 账号名，一并改指新 id（低风险）。

---

## 九、共享知识（跨文件约定）

- **状态枚举**：`hosted_status ∈ {hosted, unhosted}`（前端映射 已托管/未托管）；`read_status ∈ {read, unread}`；`online_status/status ∈ {online, offline}`；`type ∈ {customer, internal, customer_group, internal_group}`；`channel_type ∈ {wecom, wechat, whatsapp, business_whatsapp}`。
- **命名转换**：DB snake_case → DTO camelCase，沿用 `row_to_*`（`channel_type→channelType`、`sessions_count→sessionsCount`、`auto_resume_seconds→autoResumeSeconds` 等）。
- **日期展示**：`YYYY-MM-DD HH:mm:ss`；会话列表 `last_time` 可用相对值（10:36/昨天）由前端格式化。
- **分页结构**：列表类沿用 `{items, total, page, pageSize, hasMore}`（`paginate_result` / 前端 `Paged<T>`）；联系人/会话列表本期可全量返回（数据量小），预留分页参数。
- **托管机器人来源**：`GET /channels/hosting-bots` 静态返回；聊天面板「选择机器人」与托管「托管AI机器人」筛选共用。
- **图标映射**：`channelTypeIcon`：wechat-work/wechat/whatsapp（原型 L2244-2251）；账号角标 class `channel-account-type wechat-work`；前端 `ChannelTypeBadge` 内联同款 SVG，避免引入图片资源。
- **接真实后端开关**：`ChannelSettings.tsx` 置 `USE_MOCK=false`；其余页面移除本地 `MOCK` 常量，直接走 `channelsApi`。
- **聊天输入遮罩**：`hosted_status==hosted` 时输入框 `disabled` + 显示「已开启机器人托管，请关闭托管后再手动回复」。

---

## 十、典型流程时序图（另见 `sequence-diagram.mermaid`）

1. **会话列表加载**：前端 `ChannelSessionsPage` 并行 `GET /channels/teams` + `GET /channels/accounts`；用户选账号 → `GET /channels/sessions?accountId=` → `ChannelMgmtRepository.list_sessions` → DB → DTO → 渲染左/中栏。
2. **开启托管**：用户切换聊天面板开关 → `POST /channels/sessions/{id}/hosting {hosted:true, botId}` → repo 更新 `channel_sessions` → 返回更新后 session → 前端禁用输入 + 显示遮罩。
3. **联系人详情加载**：左栏选账号 → `GET /channels/contacts?accountId=` → 中栏选联系人 → `GET /channels/contacts/{id}`（聚合 profile/沟通记录/属性）→ 渲染右栏。
4. **批量托管更新**：托管管理页勾选 → `POST /channels/hosting-sessions/batch-update {ids, hostedStatus}` → repo 更新 `hosting_sessions` → 返回影响行数 → 刷新表格。

---

## 十一、任务列表（有序 + 依赖，按子版面分组）

> 实现顺序：后端基础（T01–T05）→ 前端 API/路由/共享（T06–T08，可与后端并行）→ 各子版面前端（T09–T12）→ 联调自查（T13）。P0 优先。

| Task | 子版面 | 名称 | 涉及文件 | 依赖 | 优先级 | 验收点 |
|---|---|---|---|---|---|---|
| T01 | 后端基础 | Schema 扩展 + 新表 DDL | `schema.py`、`database/init_morphix_mvp.sql` | — | P0 | `init_schema` 可建表；`channel_accounts` 含 team_id/channel_type/protocol/sessions_count；9 张新表存在；索引建立 |
| T02 | 后端基础 | 种子数据扩展 | `schema.py`(seed_defaults)、`database/init_morphix_mvp.db`(重跑) | T01 | P0 | 删库重启后：teams(1)/accounts(3 原型账号)/contacts(12)/profiles(5)/sessions(4)/hosting_sessions(6)/hosting_rules(1)/wechat_subjects(1) 均落库；`channel_seats` id 同步 |
| T03 | 后端基础 | ChannelMgmtRepository | `repositories.py` | T01 | P0 | 各 list/get/create/update 方法可用，SQL 集中、返回 DTO |
| T04 | 后端基础 | 路由 + 注册 + 请求模型 | `routers/channel_mgmt.py`、`routers/__init__.py`、`schemas.py` | T03 | P0 | `/api/channels/{teams,accounts,contacts,sessions,hosting-sessions,hosting-rules,wechat-subjects,hosting-bots}` 全部可 200；`__init__` 注册成功 |
| T05 | 后端基础 | 重启后端验证 | `database/morphix_mvp.db` | T01–T04 | P0 | 后端启动无报错；curl 各端点返回种子数据 |
| T06 | 前端基础 | API 层扩展 | `api/client.ts`、`types/channels.ts` | — | P0 | `channelsApi` 含 accounts/contacts/sessions/hosting/wechat-subjects/teams/hosting-bots；DTO 类型齐全 |
| T07 | 前端基础 | 路由 + 子路由 | `router.tsx` | — | P0 | `/channels/accounts/add`、`/channels/accounts/:id/hosting` 可达；旧 4 路由保留 |
| T08 | 前端基础 | 共享组件/工具 | `pages/Channels/shared/*`、`ChannelTypeBadge`、`StatusDot`、`AccountListPanel`、`TeamInfoBar`、`TeamSelector` | — | P0 | 共享三栏左栏/团队条/角标可复用；ACC/SES/CON 引用一致 |
| T09 | ACC | 账号管理+向导+托管 | `ChannelAccounts.tsx`、`AccountAdd.tsx`、`ChannelHosting.tsx` + 共享 | T04,T06,T07,T08 | P0 | 卡片网格+团队条(P0-ACC-1)；添加向导(P0-ACC-2)；托管批量+规则(P0-ACC-3/4)；数据来自 API |
| T10 | SES | 三栏会话+聊天+详情 | `ChannelSessions.tsx`、`sessions/SessionChatPanel.tsx`、`sessions/SessionCustomerDetail.tsx` + 共享 | T04,T06,T07,T08 | P0 | 三栏重建(P0-SES-1)；托管开关/选机器人/遮罩(P0-SES-2)；客户详情双Tab(P0-SES-3)；消息来自 `messages` 表 |
| T11 | CON | 三栏联系人 | `ChannelContacts.tsx`、`contacts/ContactDetailPanel.tsx` + 共享 | T04,T06,T07,T08 | P0 | 左账号+中类型/状态Tab+右详情(P0-CON-1)；发消息按钮(P1-CON-2) |
| T12 | SET | 特殊渠道设置接后端 | `ChannelSettings.tsx` | T04,T06 | P0 | `USE_MOCK=false`；GET/POST/PUT `/channels/wechat-subjects` 生效(P0-SET-1/P1-SET-2) |
| T13 | 联调 | 自查与联调 | 仓库根（前端 `npm run build`、后端启动） | T05,T09–T12 | P1 | tsc 无错；4 子版面数据均从 DB 加载；视觉对齐原型 class/状态标签(P2-UI) |

> **范围备注（P2，不在本期派工）**：移动端 `mobile-session-hosting` 独立页（T13 仅桌面端）；换绑团队/团队新建弹窗（`POST /channels/teams` 后端已留，前端 P2）；客户详情「添加标签」联动 `customer_tags`、沟通记录 AI 总结；联系人与客户管理档案写路径打通。后端接口与种子已为这些预留。

---

## 十二、附：Mermaid 图

- 类图：`docs/class-diagram.mermaid`
- 时序图：`docs/sequence-diagram.mermaid`
