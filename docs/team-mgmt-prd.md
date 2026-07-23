# 渠道账号页 - 团队管理链路改造（增量 PRD）

> **文档版本**: v1.0
> **创建日期**: 2026-07-23
> **作者**: 许清楚（产品经理）
> **项目**: Morphix 私域运营 AI 协同平台

---

## 1 项目信息

| 项 | 值 |
|---|---|
| Language | TypeScript / Python |
| Programming Language | Vite + React 18 + TS（前端） / FastAPI + SQLAlchemy + SQLite（后端） |
| Project Name | `team_mgmt_chain` |
| 原始需求 | 改造渠道账号页左侧团队展示为可交互下拉选择器，补全新建团队 / 团队管理 / 成员管理完整链路；删除顶部冗余「添加渠道账号」按钮 |

---

## 2 产品定义

### 2.1 Product Goals

| # | 目标 | 说明 |
|---|------|------|
| G1 | 消除 UI 冗余入口 | 删除渠道账号页顶部右侧「添加渠道账号」按钮，与卡片网格内「添加渠道账号」卡片统一，减少用户困惑 |
| G2 | 打通团队管理闭环 | 从团队下拉选择器出发，支持新建团队 → 管理团队（基础信息编辑 / 删除）→ 添加成员，形成完整的团队管理操作链路 |
| G3 | 统一视觉规范 | 团队名称字体与登录账号字体对齐，整体美观一致 |

### 2.2 User Stories

| # | User Story | 优先级 |
|---|-----------|--------|
| US1 | 作为**运营管理员**，我希望点击团队名称弹出下拉框（含新建团队 / 管理），以便快速进入团队管理操作 | P0 |
| US2 | 作为**运营管理员**，我希望通过两步向导新建团队（设置基础信息 → 添加成员），以便有序完成团队创建流程 | P0 |
| US3 | 作为**运营管理员**，我希望在管理页修改团队名称和简介、删除多余团队（最后一个团队禁止删除），以便维护团队信息准确性 | P0 |
| US4 | 作为**运营管理员**，我希望在团队成员 Tab 中添加已注册的系统授权用户，以便将人员纳入团队协作 | P0 |
| US5 | 作为**普通用户**，我希望页面顶部不再出现重复的「添加渠道账号」按钮，界面更简洁 | P0 |

---

## 3 技术规范

### 3.1 需求池（Requirements Pool）

#### P0 — Must Have（本期实现）

| ID | 需求描述 | 前端变更 | 后端变更 | 截图索引 |
|----|---------|---------|---------|---------|
| **R01** | **删除渠道账号页顶部右侧「添加渠道账号」按钮** | `ChannelAccounts.tsx` L122-126：移除 `<div className="channel-header-actions">` 整块 | 无 | 截图 #1（改造前） |
| **R02** | **将 TeamInfoBar 替换为 TeamSelector 下拉组件** | `ChannelAccounts.tsx`：引入 `TeamSelector` 替代 `TeamInfoBar`，传入 teams/currentTeamId/onSelect 回调 | 无 | 截图 #2（改造后） |
| **R03** | **TeamSelector 字体与登录账号字体统一，美化样式** | `TeamSelector.tsx`：调整 `.team-selector-trigger` 内 span 字体大小/字重/颜色，与侧栏登录账号（`.sidebar-user-name`）保持一致 | 无 | 截图 #2 |
| **R04** | **TeamSelector 「新建团队」跳转 `/teams/create` 页面** | `TeamSelector.tsx`：注入 `useNavigate()`，「新建团队」onClick → `navigate('/teams/create')` | 无 | 截图 #2 → #3 |
| **R05** | **TeamSelector 「管理」跳转 `/teams/:id/manage` 页面** | `TeamSelector.tsx`：「管理」onClick → `navigate(\`/teams/${t.id}/manage\`)` | 无 | 截图 #2 → #5 |
| **R06** | **新增路由 `/teams/create` 和 `/teams/:id/manage`** | `router.tsx`：import 并注册 `TeamCreatePage`、`TeamManagePage` | 无 | — |
| **R07** | **新建团队页面 - 第一步表单（团队名称必填 + 简介 0/20 字）** | 新建 `pages/Teams/TeamCreate.tsx`：Step 1 表单含 name（Input required）、description（Textarea maxLength=20+字数统计）、校验、「下一步」按钮 | 新增 `PUT /channels/teams/{id}`（更新 description）或复用现有 POST | 截图 #3 |
| **R08** | **新建团队页面 - 第二步添加成员（向导步骤切换）** | `TeamCreate.tsx`：Step 2 复用成员选择弹层逻辑（见 R14），完成后创建团队并添加成员 | 复用成员接口 | 截图 #3（步骤指示器） |
| **R09** | **团队管理页 - 标题「管理：{团队名}」+ 返回导航** | 新建 `pages/Teams/TeamManage.tsx`：页面标题动态展示，返回按钮 `navigate(-1)` 或 `navigate('/channels/accounts')` | 无 | 截图 #5 |
| **R10** | **团队管理页 - Tab「基础消息」「团队成员」** | `TeamManage.tsx`：Tab 切换组件，默认激活「基础消息」Tab | 无 | 截图 #5 |
| **R11** | **基础消息 Tab - 编辑团队名称 + 简介 + 确认修改** | `TeamManage.tsx`：表单预填当前值，调用更新 API，成功后 toast + 刷新数据 | **新增** `PUT /channels/teams/{id}` 接口 | 截图 #5 |
| **R12** | **基础消息 Tab - 删除团队（多团队可删 / 单团队禁用+提示）** | `TeamManage.tsx`：「删除团队」按钮：teams.length > 1 时可点，=1 时 disabled + 显示提示文案「当前团队为最后一个团队，无法删除」 | **新增** `DELETE /channels/teams/{id}` 接口 | 截图 #5 |
| **R13** | **团队成员 Tab - 展示当前成员列表 +「添加成员」按钮** | `TeamManage.tsx`：成员列表表格（列：登录账号 / 用户名 / 所属角色），添加按钮触发弹层 | **新增** `GET /channels/teams/{id}/members` 接口 | 截图 #6 |
| **R14** | **添加成员弹层 - 搜索（登录账号/用户名）+ 选择表格** | 新建组件 `AddMemberModal.tsx`：搜索条件（account/nickname Input）、查询/重置按钮、表格（checkbox + 登录账号 + 用户名 + 所属角色）、确定选择 | 数据源复用 `GET /org/auth-users?account=&nickname=` | 截图 #6 |
| **R15** | **后端 - teams 表增加 `description` 列** | 前端 TeamDTO 增加 `description: string` | `schema.py` teams 表 ALTER/重建，加 `description TEXT NOT NULL DEFAULT ''` | — |
| **R16** | **后端 - 新增 team_members 表** | 前端新增 `TeamMemberDTO` 类型 | `schema.py` 新建表：`id/team_id/user_id/account/nickname/role/joined_at` | — |
| **R17** | **后端 - PUT /channels/teams/{id} 更新团队** | `channelsApi.updateTeam(id, data)` | `channel_mgmt.py` 新增路由 + repository 方法 | — |
| **R18** | **后端 - DELETE /channels/teams/{id} 删除团队** | `channelsApi.deleteTeam(id)` | `channel_mgmt.py` 新增路由 + repository 方法 | — |
| **R19** | **后端 - GET/POST /channels/teams/{id}/members 成员 CRUD** | `channelsApi.listTeamMembers(id)` / `channelsApi.addTeamMembers(id, userIds)` | `channel_mgmt.py` 新增路由 + repository 方法 | — |

#### P1 — Should Have（本期可选）

| ID | 需求描述 | 说明 |
|----|---------|------|
| R20 | 团队切换功能 | TeamSelector 点击其他团队行时，实际切换当前团队上下文（影响下方账号列表筛选） |
| R21 | 成员移除功能 | 团队成员 Tab 中支持移除已有成员 |
| R22 | 新建团队第二步完成后自动跳转到管理页 | 向导完成后 `navigate(`/teams/${newTeamId}/manage`)` |

#### P2 — Nice to Have（后续迭代）

| ID | 需求描述 | 说明 |
|----|---------|------|
| R23 | 团队简介字数超限实时截断/提示 | 当前仅做计数显示，可加防溢出 |
| R24 | 删除团队二次确认弹窗 | 当前直接删除，建议加 confirm dialog |
| R25 | 成员添加去重校验 | 已在团队中的用户在弹层中置灰/隐藏 |
| R26 | 团队席位/动能值在管理页可编辑 | 当前仅展示，后续可在管理页调整 |

### 3.2 变更范围总览

```
前端新增文件：
├── pages/Teams/
│   ├── TeamCreate.tsx          # 新建团队向导页（R07/R08）
│   └── TeamManage.tsx          # 团队管理页（R09-R13）
├── pages/Teams/shared/
│   └── AddMemberModal.tsx      # 添加成员弹层（R14）

前端修改文件：
├── pages/Channels/ChannelAccounts.tsx   # R01/R02
├── pages/Channels/shared/TeamSelector.tsx  # R03/R04/R05
├── router.tsx                           # R06
├── api/client.ts                        # channelsApi 扩展（R17-R19 对应方法）
└── types/channels.ts                    # TeamDTO 加 description / 新增 TeamMemberDTO

后端修改文件：
├── schema.py                            # R15（description列）/ R16（team_members表）
├── schemas.py                           # TeamCreateRequest 加 description / 新增请求/响应模型
├── routers/channel_mgmt.py              # R17/R18/R19 路由
└── repositories.py                      # 对应 Repository 方法
```

---

## 4 UI 设计稿

### 4.1 截图索引说明

| 编号 | 文件名 | 内容描述 |
|------|--------|---------|
| #1 | `clipboard-2026-07-23T01-32-25-794Z-cafacb3b.png` | **改造前**：渠道账号页顶栏，左侧「初始团队」，右侧「+ 添加渠道账号」按钮（需删除） |
| #2 | `clipboard-2026-07-23T01-32-25-794Z-1d985531.png` | **改造后**：团队选择器下拉态，「初始团队 ▼」+ 剩余席位/动能值 badge，下拉框内「+ 新建团队」+「初始团队 管理」 |
| #3 | `clipboard-2026-07-23T01-32-25-794Z-c5a9ba6d.png` | **新建团队页 Step 1**：标题「新建团队」，步骤条（①设置团队基础信息 / ②添加团队成员），表单（*团队名称 / 团队简介 0/20），「下一步」按钮 |
| #4 | `clipboard-2026-07-23T01-32-25-793Z-c5a9ba6d.png` | 同 #3（重复截图） |
| #5 | `clipboard-2026-07-23T01-32-25-793Z-9e5add6d.png` | **团队管理页**：标题「< 管理：初始团队」，Tab「基础消息」/「团队成员」，基础消息表单（*团队名称 / 团队简介），底部「删除团队」（禁用态）+「确认修改」，警告提示「当前团队为最后一个团队，无法删除」 |
| #6 | `clipboard-2026-07-23T01-32-25-792Z-488b2cb4.png` | **添加成员弹层**：标题「添加成员」，搜索区（登录账号 / 用户名输入框 + 查询/重置按钮），表格（checkbox / 登录账号 / 用户名 / 所属角色），底部「确定选择」按钮，空状态「暂无数据」 |

### 4.2 各页面布局文字描述

#### 页面 A：渠道账号页顶栏（改造后）

```
┌─────────────────────────────────────────────────────────────────────┐
│ [初始团队 ▼]  [剩余席位 1]  [动能值 899]     🔍 搜索...  [在线状态▼] │
│ ┌──────────────────────┐                                    [排序▼] │
│ │ +  新建团队           │                                            │
│ ├──────────────────────┤                                            │
│ │ 初始团队        管理  │                                            │
│ └──────────────────────┘                                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐                                                   │
│  │   +          │  添加渠道账号                                      │
│  │  添加渠道账号 │  支持企业微信、WhatsApp、企业WhatsApp               │
│  └──────────────┘                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  账号卡片...  │  │  账号卡片...  │  │  账号卡片...  │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```
> **变化点**：移除右上角「+ 添加渠道账号」Button；左侧从静态 TeamInfoBar 改为可交互 TeamSelector 下拉。

#### 页面 B：新建团队向导（Step 1）

```
┌──────────────────────────────────────────────────────────┐
│  <  返回                                                 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                     新建团队                              │
│                                                          │
│         ① 设置团队基本信息   ②  添加团队成员              │
│         ●━━━━━━━━━━━━━━━   ○                             │
│                                                          │
│       * 团队名称                                         │
│       ┌──────────────────────────────────────────┐       │
│       │ 请输入团队名称                          ⓧ │       │
│       └──────────────────────────────────────────┘       │
│                                                          │
│         团队简介                                          │
│       ┌──────────────────────────────────────────┐       │
│       │ 请输入团队简介                       0/20 │       │
│       └──────────────────────────────────────────┘       │
│                                                          │
│       ┌──────────────────────────────────────────┐       │
│       │              下 一 步                     │       │
│       └──────────────────────────────────────────┘       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### 页面 C：团队管理页

```
┌──────────────────────────────────────────────────────────┐
│  <  管理：初始团队                                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│          ┌──────────┐  ┌──────────┐                      │
│          │ 基础消息  │  │ 团队成员  │                      │
│          └──────────┘  └──────────┘                      │
│                                                          │
│       * 团队名称                                         │
│       ┌──────────────────────────────────────────┐       │
│       │ 初始团队                               ⓧ │       │
│       └──────────────────────────────────────────┘       │
│                                                          │
│         团队简介                                          │
│       ┌──────────────────────────────────────────┐       │
│       │ 请输入团队简介                             │       │
│       └──────────────────────────────────────────┘       │
│                                                          │
│  ┌──────────────────┐  ┌────────────────────────────┐    │
│  │    删 除 团 队    │  │        确 认 修 改          │    │
│  └──────────────────┘  └────────────────────────────┘    │
│                                                          │
│  ⚠ 当前团队为最后一个团队，无法删除                         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### 弹层 D：添加成员

```
┌──────────────────────────────────────────────────────────┐
│  添加成员                                           ✕   │
├──────────────────────────────────────────────────────────┤
│  登录账号：[请输入        ]  用户名：[请输入    ]          │
│                                              [ 重置 ][查询]│
│  ┌─────────────────────────────────────────────────────┐ │
│  │ ☐  │ 登录账号     │ 用户名      │ 所属角色           │ │
│  ├─────┼─────────────┼─────────────┼───────────────────┤ │
│  │     │  （暂无数据）                                   │ │
│  │     │        📭 暂无数据                              │ │
│  └─────────────────────────────────────────────────────┘ │
│                                         [ ✓ 确定 ]       │
└──────────────────────────────────────────────────────────┘
```

---

## 5 数据模型变更

### 5.1 teams 表变更

```sql
-- 现有字段
CREATE TABLE IF NOT EXISTS teams (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  seats_left  INTEGER NOT NULL DEFAULT 0,
  energy_value INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 本期新增字段
ALTER TABLE teams ADD COLUMN description TEXT NOT NULL DEFAULT '';
```

### 5.2 team_members 表（新增）

```sql
CREATE TABLE IF NOT EXISTS team_members (
  id          TEXT PRIMARY KEY,            -- UUID
  team_id     TEXT NOT NULL,               -- 外键 → teams.id
  user_id     TEXT NOT NULL,               -- 外键 → org auth_users.id
  account     TEXT NOT NULL DEFAULT '',     -- 冗余存储（来自 auth_users.account）
  nickname    TEXT NOT NULL DEFAULT '',     -- 冗余存储（来自 auth_users.nickname）
  role        TEXT NOT NULL DEFAULT '',     -- 冗余存储（来自 auth_users.role）
  joined_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id);
```

### 5.3 DTO 变更

```typescript
// types/channels.ts - TeamDTO 扩展
export interface TeamDTO {
  id: string
  name: string
  seatsLeft: number
  energyValue: number
  description: string  // ← 新增
}

// types/channels.ts - 新增
export interface TeamMemberDTO {
  id: string
  teamId: string
  userId: string
  account: string
  nickname: string
  role: string
  joinedAt: string
}
```

---

## 6 API 接口设计

### 6.1 新增接口清单

| Method | Path | 说明 | Request Body | Response |
|--------|------|------|-------------|----------|
| PUT | `/api/channels/teams/{id}` | 更新团队基础信息 | `{ name?, description? }` | `TeamDTO` |
| DELETE | `/api/channels/teams/{id}` | 删除团队 | — | `{ deleted: true, id }` |
| GET | `/api/channels/teams/{id}/members` | 获取团队成员列表 | — | `TeamMemberDTO[]` |
| POST | `/api/channels/teams/{id}/members` | 添加团队成员 | `{ userIds: string[] }` | `{ added: number, members: TeamMemberDTO[] }` |

### 6.2 修改接口

| Method | Path | 变更说明 |
|--------|------|---------|
| POST | `/api/channels/teams` | Request Body 新增可选字段 `description?: string` |

### 6.3 复用接口

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/org/auth-users?account=&nickname=` | 添加成员弹层的用户搜索数据源 |

---

## 7 待确认问题（Open Questions）

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| Q1 | **新建团队时 seatsLeft / energyValue 默认值如何设定？** | 后端 `POST /teams` 目前需要这两个字段。向导第一步只有 name + description。 | 建议：seatsLeft 默认 1，energyValue 默认 0（与种子数据「初始团队」逻辑一致）；或在向导第二步补充设置 |
| Q2 | **删除团队时，该团队下的渠道账号如何处理？** | channel_accounts 表有 team_id 外键指向 teams.id。删除团队后这些账号变成孤儿数据。 | 建议：软删除（加 deleted_at 标记），或将关联账号的 team_id 置空；本期先硬删并清空关联账号 team_id |
| Q3 | **团队成员角色是否需要独立于组织角色？** | 当前 role 来自 auth-users 的全局角色。团队成员是否可以有团队内的角色（如管理员/普通成员）？ | 建议：本期直接复用 auth-users.role，不做团队级角色体系 |
| Q4 | **TeamSelector 是否需要支持多团队切换刷新账号列表？** | 当前 ChannelAccounts 页取 teams[0] 为 currentTeam。如果用户创建了多个团队，切换是否要过滤显示该团队的账号？ | 建议：本期 P0 仅实现 UI 切换效果（不实际过滤）；P1 再做数据联动 |
| Q5 | **新建团队向导第二步「添加成员」是否必须？** | 如果用户第一步完成后不想立即添加成员，能否跳过？ | 建议：允许跳过——第二步提供「稍后再说」或「完成创建」按钮，直接创建空团队 |

---

## 附录 A：代码现状验证记录

| 文件路径 | 关键发现 | 与需求对照 |
|---------|---------|-----------|
| `src/pages/Channels/ChannelAccounts.tsx` L122-126 | 顶部右侧存在 `<Button>添加渠道账号</Button>` | R01 目标明确 |
| `src/pages/Channels/shared/TeamInfoBar.tsx` | 纯静态展示组件（name/seatsLeft/energyValue） | 将被 TeamSelector 替代 |
| `src/pages/Channels/shared/TeamSelector.tsx` | 已有下拉结构 + 新建/管理占位，但 onClick 为空操作（仅 setOpen(false)） | R04/R05 需填充 navigate |
| `src/router.tsx` | 无 `/teams/*` 路由 | R06 需新增 |
| `src/api/client.ts` channelsApi | 有 listTeams/createTeam，缺 update/delete/members | R17-R19 需扩展 |
| `src/types/channels.ts` TeamDTO | `{ id, name, seatsLeft, energyValue }` 缺 description | R15 需扩展 |
| `backend/app/schema.py` L196-202 | teams 表 5 列，无 description；无 team_members 表 | R15/R16 需改 |
| `backend/app/schemas.py` L111-114 | TeamCreateRequest 有 name/seatsLeft/energyValue，缺 description | 需扩展 |
| `backend/app/routers/channel_mgmt.py` | GET/POST /teams 仅两条，无 PUT/DELETE/members | R17-R19 需新增 |
| `backend/app/routers/organization.py` | GET /org/auth-users 支持 account/nickname 筛选 | R14 数据源就绪 |
