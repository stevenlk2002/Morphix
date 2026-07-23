# 渠道会话管理页 · 右侧合并区域 — 增量 PRD

> 文档版本：v1.0
> 编写人：主理人齐活林（PM/架构师/工程师/QA 接管）
> 日期：2026-07-23
> 关联页面：`src/pages/Channels/ChannelSessions.tsx`

## 0. 项目信息

- **项目**：Morphix 私域运营 AI 协同平台
- **技术栈**：前端 React 18 + Vite + TypeScript（端口 5183）；后端 FastAPI + SQLite（端口 2181）
- **改造范围**：「渠道会话管理」页右一栏（聊天）+ 右二栏（客户详情）合并成一个整体区域；群聊显示群管理；单聊显示两 Tab + 抽屉 + 编辑弹窗 + AI 总结

## 1. 产品目标

- **G1 统一工作区**：将聊天与会话详情合并为一个有统一头部的区域，避免来回切换上下文。
- **G2 群管理能力**：在群聊上下文直接管理群成员/标签/公告/群主，群操作不必跳设备端。
- **G3 客户档案沉淀**：把备注、基本信息、沟通记录、AI 总结串到一处，支持历史追溯。

## 2. 用户故事

- US1：作为运营，我希望进入聊天区域就能看到对方名字 + 机器人托管开关 + 机器人选择 + 托管管理 + 渠道账号状态，一眼掌握对话上下文。
- US2：作为运营，我希望聊天与详情两栏可调宽、可折叠，方便在小屏 / 共享屏幕场景下聚焦。
- US3：作为群主，我希望能直接在会话右侧管理群（添加标签、增删成员、查看群二维码、转让群主、发布群公告、解散群）。
- US4：作为运营，我希望在单聊右侧直接编辑客户备注/基本信息、添加沟通记录，并能让 AI 帮忙总结沟通要点。
- US5：作为运营，我希望通过抽屉快速打开「详细信息」面板，在不离开客户详情的前提下浏览更全的档案。

## 3. 需求池

### P0（必须）
- R1 合并区域（聊天+详情为一个区域） + 统一头部
- R2 头部内容：名字 + 标签 + 机器人托管 switch + 机器人下拉 + 清空上下文 + 托管管理 + 渠道账号头像
- R3 区域下方两栏（聊天 / 详情）拖拽分隔 + 客户详情可向右收起
- R4 群聊：右栏显示群管理（成员列表 / 添加标签 / 增删成员 / 群公告 / 转让群主 / 解散群）
- R5 单聊：右栏两个 Tab（客户详情 / 渠道客户详情）+ 抽屉 + 备注/基本信息编辑 + 沟通记录 + AI 总结
- R6 群管理后端 API（添加成员 / 移除成员 / 群公告 / 转让群主 / 解散群）— mock-first 兜底
- R7 备注/基本信息编辑：复用现有 `PUT /api/channels/contacts/{id}/profile`
- R8 沟通记录：复用现有 `POST /api/customers/{customer_id}/communications`（aiSummary 字段已支持）
- R9 AI 总结：调用 LLM 走 `GET /api/llm-config` + 直接调 vendor API（前端实现）

### P1（应当）
- 群二维码展示（用真实 iPad 端 QR 路径，没有则用 placeholder）
- 详情抽屉中的「历史备注」Tab

### P2（增强）
- 群成员管理支持批量操作
- 抽屉支持打开标签编辑

## 4. UI 设计稿（文字描述）

### 4.1 整体区域
`.session-mgmt` grid 改为：
`var(--session-left-width,260px) 6px minmax(0,1fr) 6px minmax(360px, 30%) 6px`（右两栏合并为单一可拖拽区域，区域内部再分聊天/详情两栏）

### 4.2 区域头部
- 左侧：好友名 / 群名 + 标签（@微信 / 客户群 / 外部群 等）
- 中部（控制区）：机器人托管 switch + 机器人下拉 + 清空上下文按钮
- 右侧（操作区）：托管管理按钮 + 渠道账号头像（圆形 + 绿点在线状态）

### 4.3 区域主体（两栏可拖拽 + 折叠）
- 左侧：聊天（沿用 SessionChatPanel，去掉内嵌头部）
- 分隔条：6px 拖拽手柄
- 右侧：客户详情（可收起）
- 折叠按钮：半圆「›」在客户详情左侧边缘

### 4.4 群聊：右栏 = 群管理
```
[群头像] [群名]   [外部群]   [二维码图标]
归属账号：xxx@xxx
[+ 添加标签]
[搜索群成员____]
[头像1] [头像2] [头像3] [+] [-]
[成员1]  [成员2]  [成员3] 添加 移出

转让群主 >
群公告 >
[解散群聊]（红色）
```

### 4.5 单聊：右栏 = 两个 Tab + 抽屉
**Tab: 客户详情**
- 顶部好友卡片（头像 + 名字 + 详细>按钮）
- [+] 添加标签
- 备注 / [编辑]
- 基本信息 / [编辑]
- 沟通记录(N) / [+] 添加新沟通记录
  - 弹窗：textarea + AI总结 checkbox
- Tab 切换：沟通记录 / 历史备注

**Tab: 渠道客户详情**
- 关联私域渠道卡片
- 自定义属性 + [新建]

**抽屉（详细）**：在右栏之上再拉抽屉，显示完整客户档案

## 5. 数据 / 接口变更

### 后端新增
- `POST /api/channels/{account_id}/group/{room_id}/members` — 添加群成员
- `DELETE /api/channels/{account_id}/group/{room_id}/members/{user_id}` — 移除群成员
- `PUT /api/channels/{account_id}/group/{room_id}/notice` — 群公告
- `POST /api/channels/{account_id}/group/{room_id}/transfer` — 转让群主
- `DELETE /api/channels/{account_id}/group/{room_id}` — 解散群

### 后端复用
- `GET /api/channels/contacts/{contact_id}` — 联系人详情
- `PUT /api/channels/contacts/{contact_id}/profile` — 客户档案更新
- `GET /api/customers/{customer_id}/communications` — 沟通记录列表
- `POST /api/customers/{customer_id}/communications` — 新增沟通记录
- `GET /api/llm-config` — LLM 配置
- `GET /api/channels/hosting-bots` — 机器人列表

### 前端新增
- `src/pages/Channels/sessions/RightPanelArea.tsx` — 合并区域容器
- `src/pages/Channels/sessions/RightPanelHeader.tsx` — 区域头部
- `src/pages/Channels/sessions/GroupManagementPanel.tsx` — 群管理
- `src/pages/Channels/sessions/SessionDetailPanel.tsx` — 单聊详情 + 抽屉
- `src/pages/Channels/sessions/SessionDetailTabs.tsx` — 客户详情 / 渠道客户详情
- `src/pages/Channels/sessions/EditBasicInfoModal.tsx` — 编辑基本信息
- `src/pages/Channels/sessions/EditRemarkModal.tsx` — 编辑备注
- `src/pages/Channels/sessions/AddCommunicationModal.tsx` — 添加沟通记录 + AI 总结
- `src/pages/Channels/sessions/DetailDrawer.tsx` — 详细信息抽屉

### 前端修改
- `ChannelSessions.tsx` — 用 `RightPanelArea` 取代两个独立面板
- `SessionChatPanel.tsx` — 去掉内嵌头部（与外部重复）
- `Channels.css` — 新增合并区域/抽屉/折叠按钮等样式

## 6. 待确认问题

- Q1：群管理后端 API 的真实端点协议端是否有约定？mock-first 兜底方案能保证 UI 不阻塞，但真实环境下功能不可用。
- Q2：AI 总结的 LLM 调用是前端直接发请求还是经后端代理？本次 MVP 走前端直接调用（用 `llmConfigApi.getAll()` 拿主备配置）。
- Q3：拖拽分隔 + 客户详情折叠状态的持久化粒度（按账号 / 全局）？本次仅做本会话内，刷新重置（保持简单）。
- Q4：抽屉中的「详细信息」内容字段如何定义？本次 MVP 复用现有 ContactDetailDTO + 沟通记录列表 + 历史备注。

## 7. 任务列表

| 任务 | 名称 | 涉及文件 |
|------|------|----------|
| T01 | 群管理后端 API（mock-first） | `project/backend/app/ipad_sync.py`、`routers/ipad_sync.py`、`schemas.py` |
| T02 | 合并区域布局 + 头部 + 拖拽/折叠 | `ChannelSessions.tsx`、`RightPanelArea.tsx`、`RightPanelHeader.tsx`、`SessionChatPanel.tsx`、`Channels.css` |
| T03 | 群管理面板 | `GroupManagementPanel.tsx` + CSS |
| T04 | 单聊详情 + 抽屉 + 编辑弹窗 + 沟通记录 | `SessionDetailPanel.tsx`、`DetailDrawer.tsx`、`EditBasicInfoModal.tsx`、`EditRemarkModal.tsx`、`AddCommunicationModal.tsx` + CSS |
| T05 | AI 总结 + LLM 集成 | `src/api/llm.ts`（新增）+ AddCommunicationModal 调用 |
| T06 | 验证（py_compile / tsc / 测试） | `tests/test_session_detail_panel.py`（新增） |
