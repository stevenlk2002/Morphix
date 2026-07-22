# 增量 PRD：Morphix「渠道会话 + 客户管理」iPad 协议同步

> 文档类型：**增量简单 PRD**（非从零开发）
> 作者：许清楚（产品经理）
> 关联代码：`project/backend/app`（ipad_client / routers / repositories / schema）、`src/pages/Channels`、`src/pages/Customers`
> iPad 协议 base：`http://47.94.7.218:9912`（可配，路径拼 `/wxwork/<Action>`，与 `ipad_client._base_url()` 一致）

---

## 1. 项目信息

| 项 | 内容 |
| --- | --- |
| Language | 中文 |
| 技术栈（后端） | Python / FastAPI / SQLite，复用现有 `ipad_client` + `repositories` + `schema` |
| 技术栈（前端） | React + Vite + Tailwind/CSS，**复用现有页面骨架**，不引入 MUI 等新 UI 库 |
| Project Name | `ipad_sync_prd` |
| 模式 | 增量开发：登录托管链路与页面骨架已存在，本次补齐「数据接入 + 发送能力」 |

**原始需求复述**：在账号托管成功（`loginType==2` 落库）之后，从真实 iPad 协议服务拉取「内部联系人 / 外部客户 / 会话 / 客户群」并落库，在前端客户管理与渠道会话页面真实展示；同时支持向联系人或客户群发送文本消息，补齐私域客户「查看 + 触达」闭环。

---

## 2. 现状调研摘要（确认增量范围）

经阅读后端 router 与前端页面，结论如下：**展示层与数据模型已基本就绪，核心缺口在「iPad → DB 的数据接入层」与「发送能力」**。

| 模块 | 现状 | 是否需增量 |
| --- | --- | --- |
| 登录托管链路（`ipad_client` + `channel_hosting`） | ✅ 已完成；`loginType==2` 时 `create_account_with_ipad` 落 `channel_accounts`（含 `ipad_uuid`/`ipad_user_info`/`host_status`） | 无需改 |
| 联系人展示路由 `/channels/contacts`、`/channels/contacts/{id}` | ✅ 已实现，读 `channel_contacts` + `customer_profiles` | 仅缺数据 |
| 会话展示路由 `/channels/sessions`、`/channels/sessions/{id}/messages` | ✅ 已实现，读 `channel_sessions` + `messages` | 仅缺数据 |
| 客户管理路由 `/customers`、`/customer-tag-groups`、`/customer-groups`、`/customer-tags` | ✅ 已实现（聚合 profile + 标签） | 仅缺数据 |
| 前端页面骨架 `ChannelContacts` / `ChannelSessions` / `SessionChatPanel` / `ContactDetailPanel` / `CustomerList` 等 | ✅ 骨架存在并调用真实路由 | 仅缺数据；「发消息」「群成员」为 stub |
| **iPad 同步服务层（拉取→落库）** | ❌ 不存在 | **核心增量** |
| **发文本消息**（`SendTextMsg` 封装 + 后端路由 + 前端发送） | ❌ `ipad_client` 未封装、无路由、`SessionChatPanel.handleSend` 为 stub | **核心增量** |
| 群成员详情（`GetRoomUserList` + 群成员抽屉） | ❌ 未封装、无前端 | 增量（P1） |
| 搜索/添加外部联系人（`SearchContact` / 搜索添加外部联系人） | ❌ 未封装、无前端入口 | 增量（P1） |
| 消息记录同步（历史回填） | ❌ 无 | 增量（P2） |

**数据模型结论（决定落库方案）**：现有表已能承接绝大部分同步数据，无需新建大表——
- 内部/外部联系人 → `channel_contacts`（`type=customer|internal`）+ 1:1 `customer_profiles`
- 会话 → `channel_sessions`（`session_type` 由 `msgtype` 映射，`contact_id` 关联）
- 消息 → `messages`（`conversation_id` = `session_id`）
- 账号 → `channel_accounts.ipad_uuid` 用于同步/发送调用
- 标签 → 现有 `customer_tags` / `customer_tag_groups` / `customer_tag_relations` 可承载外部联系人 `labelid` 映射
- 群（客户群/内部群）→ **待定**（见 §7 待确认问题 #1）

---

## 3. 产品目标

在企微账号托管成功（`loginType==2`）后，自动或按需从 iPad 协议服务拉取内部联系人、外部客户、会话、客户群及其成员并落库，使前端「客户管理」与「渠道会话」页面从空壳变为真实数据驱动；同时开放向联系人与客户群发送文本消息的能力，让运营人员可在 Morphix 内完成私域客户的查看与触达，形成「接入—查看—运营—触达」的闭环。

---

## 4. 用户故事

| ID | 角色 | 故事 | 价值 |
| --- | --- | --- | --- |
| US1 | 私域运营 | 作为运营，我希望账号托管后看到该企微下的全部外部客户与内部成员列表，以便统一管理客户资产 | 客户资产可视化 |
| US2 | 私域运营 | 作为运营，我希望查看每个客户/联系人的详情（备注、资料、来源、标签），以便了解客户背景 | 客户洞察 |
| US3 | 私域运营 | 作为运营，我希望在渠道会话页看到好友/群聊/应用三类会话与未读状态，以便跟进会话 | 会话跟进 |
| US4 | 私域运营 | 作为运营，我希望选中联系人或客户群后直接发送文本消息，以便主动触达客户 | 主动触达 |
| US5 | 群主（P1） | 作为群主，我希望查看客户群的成员列表与人数，以便掌握群规模与成员构成 | 群运营 |
| US6 | 运营（P1） | 作为运营，我希望通过手机号/关键词搜索并添加外部联系人，以便拓展客户 | 客户增长 |

---

## 5. 需求池

### P0（Must have）

| 编号 | 需求 | 验收标准 |
| --- | --- | --- |
| P0-1 | 同步内部联系人 | 调用 `GetInnerContacts`（`strSeq` 游标全量分页），upsert 到 `channel_contacts`（`type=internal`）+ 必要 `customer_profiles`；`is_department=1` 的部门条目按 §7#9 处理 |
| P0-2 | 同步外部联系人（客户） | 调用 `GetExternalContacts`（`seq` 游标），upsert `channel_contacts`（`type=customer`）；`status` 按 0/1/2049/其他映射；`labelid[]` 暂存待 P1 映射 |
| P0-3 | 同步会话列表 | 调用 `GetSessionList`（`star_index` 分页），upsert `channel_sessions`；`session_type` 由 `msgtype` 映射（0 好友/1 群聊/3 应用/6 开放平台），`external_tag` 按类型 |
| P0-4 | 同步客户群列表 | 调用 `GetChatroomMembers`（`star_index`），落库（方案见 §7#1）；含 `room_id`/`nickname`/`total`/`roomUrl`/`create_time`/`update_time` |
| P0-5 | 发文本消息 | 封装 `ipad_client.send_text_msg`；新增后端发送路由（按会话/联系人/群）；前端 `SessionChatPanel.handleSend` 调真实接口；入参 `uuid`(取 `account.ipad_uuid`)+`send_userid`/`roomid`+`isRoom`+`content` |
| P0-6 | 同步触发入口 | 托管成功后自动触发首次全量同步；提供手动「同步/刷新」按钮（账号卡片或页面顶部），调用同步任务 |
| P0-7 | 前端复用与接线 | `ChannelContacts`/`ChannelSessions` 已接真实路由，确保同步后有数据；发消息按钮接真实接口（替换 stub） |

### P1（Should have）

- **P1-1 标签映射**：外部联系人 `labelid[]` → 现有标签体系（建 `labelid→tag_id` 映射，写入 `customer_tag_relations`）。
- **P1-2 群成员详情**：封装 `GetRoomUserList`；新增「群成员抽屉」组件（复用现有 Drawer 模式），展示 `nickname`/`realname`/`avatar`/`room_nickname`/`sex`/`mobile`/`jointime`、群公告、群人数。
- **P1-3 搜索/添加外部联系人**：封装 `SearchContact` + `搜索添加外部联系人`；`ChannelContacts` 增加「搜索添加」入口与结果弹窗。
- **P1-4 内部部门分组展示**：`is_department` 条目的层级/分组呈现。
- **P1-5 同步状态与错误提示**：同步任务进度/失败（`iPad` 服务不可用）提示，对接现有 toast 体系。

### P2（Nice to have）

- **P2-1 消息记录同步**：通过 `GetMsg`/历史接口按 `server_id` 游标回填 `messages` 表（`conversation_id=session_id`），支撑聊天面板历史。
- **P2-2 已读/未读**：前端标记已读（复用/新增接口）；会话未读数回写 `channel_sessions.unread_count`/`read_status`。
- **P2-3 富消息**：引用 / @ / 撤回等消息类型扩展与 UI。
- **P2-4 增量实时同步**：长连接 / Webhook 回调触发增量更新（替代纯手动/定时）。
- **P2-5 移动端会话托管入口**（前端已有占位）。

---

## 6. UI 设计稿（复用现有页面骨架，不重复造页面）

### 6.1 客户管理页（复用 `CustomerList.tsx` + `CustomerDetailDrawer.tsx` + `CustomerTagModal.tsx`）
- **列表区**：类型筛选（外部客户/内部成员，可加「客户群」）、关键词搜索、标签筛选；数据来自 `/customers`（已聚合 profile + 标签）。
- **详情抽屉（`CustomerDetailDrawer`）**：基础信息、客户档案（`phone`/`company`/`position` 等来自 `customer_profiles`）、标签（`CustomerTagModal` 编辑）、沟通记录、自定义属性。P1 增加「标签来自 iPad `labelid` 映射」展示。
- **客户分组（`CustomerGroupCreateModal`）**：已有，直接复用。

### 6.2 渠道联系人页（复用 `ChannelContacts.tsx` + `ContactDetailPanel.tsx`，三栏）
- **左**：账号列表（`AccountListPanel`，已接 `/channels/accounts`）。
- **中**：联系人列表，含 4 个 tab（客户 / 内部成员 / 客户群聊 / 内部群聊）+ 状态 tab（在线/离线）+ 搜索；数据来自 `/channels/contacts`（`accountId`+`type`+`status`+`search`）。P1 在 tab 旁加「搜索添加」按钮。
- **右**：`ContactDetailPanel` 详情（基础信息/客户档案/沟通记录/自定义属性）。P1 客户群 tab 选中时，详情区改为「群信息 + 群成员入口」；「发消息」按钮（现 P2 stub）在 P0 接真实发送。

### 6.3 渠道会话页（复用 `ChannelSessions.tsx` 四栏 + `SessionChatPanel.tsx`）
- **顶栏**：`TeamSelector` + 移动端占位（P2）。
- **左**：`AccountListPanel`。
- **中**：会话列表，含 阅读（全部/未读）+ 托管（全部/已托管/未托管）过滤 + 搜索；数据来自 `/channels/sessions`。每会话显示头像/名称/最后消息/时间/未读角标/在线状态/外部标签。
- **右一**：`SessionChatPanel` 聊天面板（消息气泡 + 机器人托管开关 + 托管管理/客户详情按钮）。**发消息输入框**见 §6.5。
- **右二**：`SessionCustomerDetail`（客户详情）。
- **顶部新增「同步」按钮（P0-6）**：触发当前账号全量同步。

### 6.4 群成员抽屉（P1 新增，复用 Drawer 模式）
- **触发**：客户群/内部群聊会话或联系人详情中「查看成员」。
- **内容**：群名称、群人数（`total`）、群公告（`notice_content`）、成员列表（头像/昵称/群昵称/性别/手机/加入时间，来自 `GetRoomUserList` 全量返回）。
- **交互**：点击成员可跳转其联系人详情；可「发消息」给该成员。

### 6.5 发消息输入框（P0，修改 `SessionChatPanel`）
- **位置**：聊天面板底部 `chat-input-box`。
- **行为**：输入文本 → 回车/点击发送 → 调用后端发送接口（携带当前 `account.ipad_uuid` + 目标 `send_userid` 或 `roomid` + `isRoom`）。发送成功做本地乐观追加，失败 toast。
- **约束**：`hosted`（机器人托管开启）时仍禁用手动输入（保持现有逻辑）。
- **入口扩展**：联系人详情/群成员也可「发消息」（复用同一发送接口，由目标决定 `send_userid` 还是 `roomid`）。

---

## 7. 待确认问题（Open Questions）

1. **群数据落库方案**：`GetChatroomMembers` 返回的客户群/内部群，是（A）复用 `channel_contacts`（`type='customer-group'|'internal-group'`），还是（B）新建 `channel_groups` 表（含 `room_id`/`nickname`/`total`/`roomUrl`/`create_time`/`update_time` + 成员关系）？**建议 B**（群与联系人为不同实体，避免污染联系人查询）。
2. **标签映射**：iPad 外部联系人 `labelid[]` 与现有 `customer_tags`/`customer_tag_groups` 如何对齐？是否建 `labelid→tag_id` 映射表？还是首次同步自动建标签？
3. **消息记录来源**：P2 历史消息是否通过 `GetMsg`（`server_id` 游标）轮询回填？是否接长连接/回调（P2-4）？当前 iPad 服务是否提供消息回调？
4. **同步触发与策略**：首次全量（托管成功后自动）后，增量更新如何触发——手动刷新 / 定时任务 / 实时回调？分页是游标续查直到空还是限定上限？
5. **去重与并发**：重复同步的 upsert 策略（以 `user_id`/`room_id` 为自然键，`account_id` 限定）；并发账号同步是否限流。
6. **发送目标类型**：`SendTextMsg` 的 `send_userid` 取值——好友用 `user_id`，群用 `room_id` 且 `isRoom=true`，应用（`msgtype=3`）是否支持发送？`kf_id` 何时必填？
7. **失败与降级**：`IPAD_PROTOCOL_MODE=real` 抛 502 时，同步/发送的错误提示与重试策略；`auto` 模式是否触发 mock 兜底（目前 mock 无联系人数据，是否需补充 mock 联系人以便演示）。
8. **账号范围**：本期仅 `wecom` + `ipad` 协议；`channel_accounts` 中 `ipad_uuid` 为空（非 iPad 协议）的账号应排除在同步之外。
9. **部门条目处理**：`GetInnerContacts` 中 `is_department=1` 的部门节点，是落库为特殊 `type` 还是仅用于层级展示（不落为「联系人」）。

---

## 8. 非目标（Out of Scope）

- 非 iPad 渠道（微信个人号 / WhatsApp）的同步
- 消息富媒体（图片/文件/语音）发送（P0 仅文本）
- AI 自动回复策略本身（仅复用现有托管开关）
- 多租户 / 权限模型改造

---

## 附录：iPad 接口契约速查（base + `/wxwork/<Action>`）

| 用途 | Action | 入参 | 关键返回 | 落库目标 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| 内部联系人 | `GetInnerContacts` | `{uuid, limit, strSeq}` | `data.list[]`（user_id/nickname/realname/avatar/mobile/corpid/partyid/is_department/remark…） | `channel_contacts(type=internal)` | P0 |
| 外部联系人 | `GetExternalContacts` | `{uuid, limit, seq}` | `data.list[]`（user_id/nickname/realname/avatar/labelid[]/add_customer_time/status/source/company_remark/mobile…） | `channel_contacts(type=customer)` | P0 |
| 会话列表 | `GetSessionList` | `{uuid, limit, star_index}` | `data.room_list[]`（sessionid/msgtype 0好友1群聊3app6开放平台/unreadcnt/beginmsgseq）+ top_list/shield_list | `channel_sessions` | P0 |
| 客户群列表 | `GetChatroomMembers` | `{uuid, limit, star_index}` | `data.room_list[]`（room_id/nickname/total/roomUrl/create_time/update_time） | 群表（待定 §7#1） | P0 |
| 群成员 | `GetRoomUserList` | `{uuid, roomid}` | `data`（room_id/nickname/total/notice_content/member_list[]：nickname/realname/avatar/uin/room_nickname/sex/mobile/jointime） | 群成员（待定） | P1 |
| 发文本消息 | `SendTextMsg` | `{uuid, send_userid, isRoom(bool), content, kf_id?}` | `data`（msg_id/server_id/content/sendtime/sender/receiver） | 本地乐观追加 + 可选落 `messages` | P0 |
| 搜索联系人 | `SearchContact` | `{uuid, ...}`（手机号/关键词） | 联系人匹配 | — | P1 |
| 搜索添加外部联系人 | `搜索添加外部联系人` | `{uuid, ...}` | 添加结果 | `channel_contacts` | P1 |
| 消息历史（回填） | `GetMsg`/历史接口 | `{uuid, server_id, ...}` | 历史消息（`server_id` 游标） | `messages` | P2 |
