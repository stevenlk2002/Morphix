# 增量 PRD：Morphix「渠道会话 + 客户管理」P1 + P2（iPad 协议同步增量）

> 文档类型：**增量简单 PRD**（非从零开发）
> 作者：许清楚（产品经理）
> 关联：P0 已完成（联系人 / 会话 / 群同步 + 发文本消息）；T04（群成员抽屉）已完成并测试通过
> 协议 base：`http://47.94.7.218:9912`（可配，路径拼 `/wxwork/<Action>`，与现有 `ipad_client._base_url()` 一致；协议文档示例端口为 8083，以 `_base_url()` 为准）
> 协议文档：`AI study/企业微信IPad/IPad协议API文档_合并版.md`

---

## 1. 产品目标

在 P0 已打通「联系人 / 会话 / 群同步 + 发文本消息」与 T04 群成员抽屉的基础上，P1 聚焦**客户资产的精细化运营**——把 iPad 标签体系同步进 Morphix 标签系统并支持给联系人增减标签、开放「搜索手机号/关键词并发送好友申请」的获客入口、补齐内部群聊 tab 的真实数据（受协议能力限制以兼容方案呈现）、并打磨同步状态体验；P2 则补齐**会话内容的完整闭环**——消息历史回填让聊天面板有迹可循、已读消除小红点、支持图片/文件富媒体发送、并通过实时回调（SetCallbackUrl + 后端收端）让消息增量自动入站，使运营在 Morphix 内即可完成「获客 → 分层 → 跟进 → 触达 → 收消息」的全流程闭环。

---

## 2. 用户故事

| ID | 角色 | 故事 | 价值 |
| --- | --- | --- | --- |
| US1 | 私域运营 | 作为运营，我希望在客户详情看到 iPad 原始标签（如「高意向」「已成交」）并以 Morphix 标签名展示，且能直接增减客户标签 | 客户分层可视化、可运营 |
| US2 | 获客专员 | 作为获客专员，我希望用手机号/关键词搜索企业微信用户并一键发送好友申请，申请结果可落为联系人 | 拓客入口闭环 |
| US3 | 私域运营 | 作为运营，我希望在会话聊天面板里看到历史消息（1:1 与群），而不是只有刚发的文本 | 沟通上下文完整 |
| US4 | 私域运营 | 作为运营，我希望点开会话即把未读小红点清掉（已读），避免重复跟进 | 跟进状态清晰 |
| US5 | 私域运营 | 作为运营，我希望能发图片/文件给客户或群，而不只是文本 | 触达形式丰富 |
| US6 | 运营/值班 | 作为值班运营，我希望客户发来的新消息能实时出现在 Morphix（无需手动刷新同步），并触发未读提醒 | 实时响应、不漏消息 |

---

## 3. 需求池

> 优先级说明：P1 = Should have（核心运营闭环增强，建议本期完成）；P2 = Nice to have（内容闭环与实时能力，按需排期）。每条均给出「协议依据 / 验收要点」。

### 3.1 P1（Should have）

#### P1-1 标签映射与标签管理（核心）

| 项 | 内容 |
| --- | --- |
| 协议依据 | `GetLabelListReq`（获取标签列表，入参 `{uuid, index, sync_type}` 1企业/2个人，返回 `labelList[]` 含 `id/name/label_type/label_groupid`）；`UserAddLabelsReq`（入参 `{uuid, userid, labelid_list[]}`，一个用户多个标签） |
| 需求 | ① 同步 iPad 标签列表到 Morphix 标签体系（`customer_tags` / `customer_tag_groups` / `customer_tag_relations`），建立 `iPad labelid → Morphix tag_id` 映射（建议复用 `customer_profiles.tags` 已存的 `labelid[]` 镜像做关联）；② 外部联系人详情中以「标签名」展示其 `labelid[]`（而非原始数字）；③ 支持给联系人**加标签 / 移除标签**——前端选择标签后调用 `UserAddLabelsReq`，并落库 `customer_tag_relations`；④ 标签列表支持分页续查（`index` 游标） |
| 验收 | iPad 标签出现在客户标签体系；客户详情标签区显示真实标签名；选中/取消标签后调用协议成功且 DB 关系更新；重复同步不重复建标签（按 labelid 幂等） |
| 复用 | 现有 `CustomerTagModal` / `CustomerDetailDrawer` 标签编辑交互；现有 `customer_tag_relations` 落库 |

#### P1-2 搜索 / 添加外部联系人

| 项 | 内容 |
| --- | --- |
| 协议依据 | `SearchContact`（入参 `{uuid, phoneNumber}`，返回 `userList[]` 含 `user_id/name/sex/headImg/ticket/openId/corp_id/state`）；`AddSearch`（入参 `{uuid, vid, openId, phone, content, ticket}` 发送好友申请）；`AddWxUser`（入参 `{uuid, vid, content}`，「直接添加，仅限曾被删除过」）；`AgreeUser`（入参 `{uuid, corpid, vid}`，同意添加，vid 来自回调） |
| 需求 | ① 在「渠道联系人」页提供「搜索添加」入口（输入框 + 搜索按钮），按手机号/关键词调用 `SearchContact`；② 结果以列表/弹窗展示（头像、昵称、状态），每条带「发送好友申请」按钮，调用 `AddSearch`（优先）/ `AddWxUser`（兜底——仅限曾被删除场景，需 UI 提示）；③ 申请可填验证语 `content`；④ 申请成功后提示，并可「加入联系人」（触发一次增量同步或本地落 `channel_contacts`） |
| 验收 | 搜索返回结果正确展示；点击发送申请返回成功且 toast 提示；被删除场景的 `AddWxUser` 有区别提示；非法/空结果有空态与错误提示 |
| 复用 | 复用 `ChannelContacts.tsx` 搜索栏与现有弹窗/抽屉组件；复用 toast 体系 |

#### P1-3 内部群聊 tab 实数据（兼容方案）

| 项 | 内容 |
| --- | --- |
| 协议依据 | 现有 `GetChatroomMembers` 返回群列表（`room_id/nickname/total/roomUrl/...`），**协议层无「客户群 vs 内部群」区分字段**（设计文档 §8#1 已记录） |
| 需求 | 确认是否存在区分「内部群」的接口：**经查协议文档，未发现可区分客户群/内部群的原生字段**。故本期采用**兼容/占位方案**——「内部群聊」tab 复用与「客户群聊」相同的 `channel_groups` 数据源（或显式渲染为空态并说明「当前协议不支持区分内部群」），不新建独立数据通道；同时保留 `group_type` 字段（`customer_group` / `internal_group`）以便后续协议支持时无缝区分 |
| 验收 | 「内部群聊」tab 可正常渲染（与「客户群聊」同源或在无区分时显示明确空态说明）；不因为此 tab 产生重复/脏数据 |
| 待确认 | 见 §5 #1：是否接受兼容方案，或等待协议补齐区分字段 |

#### P1-4 同步状态提示体验打磨

| 项 | 内容 |
| --- | --- |
| 协议依据 | 无新增协议；依赖 `channel_accounts.sync_status`（syncing/success/degraded/error）与 `last_sync_at` |
| 需求 | P0 已部分实现同步触发与基础提示，P1 补齐体验细节：① 同步中按钮 loading + 禁用，避免重复点击；② 同步成功/失败/降级（degraded）三类 toast 文案区分（降级需提示「部分数据未同步，iPad 服务暂不可用」）；③ 账号卡片展示同步状态角标（绿点=成功/灰=未同步/黄=同步中/红=失败）；④ 会话/联系人列表在「首次同步尚未完成」时显示空态引导（而不是空白）；⑤ 多账号并行同步的状态各自独立展示 |
| 验收 | 上述 5 点均可在 UI 观察；降级（auto 模式协议失败）有明确用户可懂提示且不崩溃 |

### 3.2 P2（Nice to have）

#### P2-1 消息历史回填

| 项 | 内容 |
| --- | --- |
| 协议依据 | `GetGroupMsgList`（入参仅 `{uuid}`，返回 `listdata[]` 含 `id/seq/content[]/file_id/aes_key` 等多类型）；`SyncAllData`（入参 `{uuid, limit, seq}`，**返回「消息已分发到消息回填事件，请在回调中处理离线消息」——实际消息经回调推送，非 HTTP 返回**） |
| 需求 | ① 按 `session` 回填 `messages` 表（`conversation_id = session_id`，以 `server_id`/消息 `id` 去重 upsert）；② 群聊历史通过 `GetGroupMsgList` 拉取（⚠️ 文档示例无 room 选择参数，见 §5 #2）；③ 1:1 会话历史通过 `SyncAllData` 触发、由**实时回调（P2-4）**接收并落库（故 P2-1 与 P2-4 强耦合）；④ 聊天面板进入会话时按需加载历史（分页/游标续查，上限见 §5 #3） |
| 验收 | 进入有历史的会话可见历史消息；与实时收到的新消息衔接不重复、不丢；群与 1:1 均可用（在回调可用前提下） |
| 复用 | 现有 `SessionChatPanel.tsx` 消息气泡渲染；现有 `messages` 表 |

#### P2-2 已读消息

| 项 | 内容 |
| --- | --- |
| 协议依据 | `MarkAsRead`（入参 `{uuid, send_userid, isRoom}`，返回已读回执含 `server_id`） |
| 需求 | ① 进入/打开会话时调用 `MarkAsRead` 清除 iPad 侧未读（小红点）；② 同步回写 `channel_sessions.unread_count` / `read_status`；③ 群聊（`isRoom=true`）与 1:1（`isRoom=false`）分别按 `send_userid` 传群 id / 用户 id |
| 验收 | 打开会话后 iPad 端小红点消失；前端未读角标清零；`unread_count` 落库一致 |

#### P2-3 富消息发送（图片 / 文件）

| 项 | 内容 |
| --- | --- |
| 协议依据 | 发送前需 CDN 上传：`CdnUploadImg`（multipart `{file, uuid}` → 返回 `cdn_key/aes_key/md5/width/height/size`）、`CdnUploadFile`（multipart `{file, uuid}` → 返回 `aes_key/fileid/md5/size`）；发送：`SendCDNImgMsg`（入参 `{uuid, send_userid, isRoom, cdnkey, aeskey, md5, fileSize, width, height, ...}`）、`SendCDNFileMsg`（入参 `{uuid, send_userid, isRoom, cdnKey, aesKey, md5, file_name, fileSize}`） |
| 需求 | ① 聊天输入框增加「图片」「文件」按钮（复用现有 `SendMessageDialog` 或输入框扩展）；② 选择文件后**后端代理 CDN 上传**拿 `cdn_key/aes_key/md5/fileSize`，再调用 `SendCDNImgMsg`/`SendCDNFileMsg`；③ 发送成功后本地乐观追加对应气泡（图片缩略图 / 文件卡片）；④ 至少支持图片 + 文件（语音/视频为 P2 扩展，可留接口） |
| 验收 | 选图/选文件 → 发送成功 → iPad 侧收到；前端气泡正确展示；上传/发送失败有 toast；大文件/超限有提示 |
| 待确认 | 见 §5 #4：CDN 上传由后端代理还是前端直传；`CdnUploadFile` 返回 `fileid` 与 `SendCDNFileMsg` 所需 `cdnKey` 的映射 |

#### P2-4 实时回调（消息增量入站）

| 项 | 内容 |
| --- | --- |
| 协议依据 | `SetCallbackUrl`（入参 `{uuid, url, callbackType}` HTTP｜RABBITMQ）；回调以 POST 推送 `{uuid, json, type}` |
| 需求 | ① 后端提供回调接收端点（如 `POST /wxwork/callback`），解析 `{uuid, json, type}`；② 账号托管成功后调用 `SetCallbackUrl` 注册 Morphix 公网可达地址；③ 回调触发：新消息落 `messages`、更新 `channel_sessions` 未读、触发前端未读提醒（与 P2-1/P2-2 联动）；④ 支持配置 `callbackType`（默认 HTTP，企业内可切 RABBITMQ） |
| 验收 | iPad 侧收到新消息后 Morphix 自动出现该消息与未读；`SetCallbackUrl` 注册成功；回调幂等（重复推送不重复落库） |
| 关键限制 | **本地开发环境无公网 URL，iPad 服务无法回拨 `127.0.0.1`**。降级方案见 §5 #5：开发期可用内网穿透（如 frp/ngrok/cloudflared）暴露端点，或暂以手动「同步」代替；生产环境必须配置公网可达回调地址 |

---

## 4. UI 设计稿（复用现有页面骨架，不重复造页面）

> 原则：所有增量交互**复用现有组件/弹窗/抽屉**，仅在既有位置追加入口或字段。

### 4.1 标签管理（复用 `CustomerDetailDrawer` + 现有标签编辑）
- **入口**：客户详情 / 联系人详情的「标签」区，复用现有「编辑标签」按钮。
- **展示**：标签以标签名 chips 展示（来自 `customer_tag_relations` + `customer_tags` 映射），不再展示原始 `labelid` 数字。
- **编辑弹窗**：复用现有 `CustomerTagModal`——左侧可选 iPad 同步来的标签（来自 `customer_tags`），右侧为已选；选中/取消后调用 `UserAddLabelsReq` 并落库；保存后乐观刷新 chips。
- **注意**：若某 `labelid` 尚未同步进 `customer_tags`，需先触发一次标签列表同步（`GetLabelListReq`）再展示，避免「幽灵 id」。

### 4.2 搜索添加联系人（复用 `ChannelContacts` 搜索栏 + 现有弹窗）
- **入口**：`ChannelContacts.tsx` 顶部/「客户」tab 旁的「搜索添加」按钮（P0 已规划 tab，P1 加按钮）。
- **面板**：点击弹出搜索面板（输入框 + 搜索按钮 + 验证语输入）；结果列表每项：头像、昵称、状态标识、「发送申请」按钮。
- **交互**：点「发送申请」→ 调 `AddSearch`（带 `ticket/openId/phone`），成功 toast；申请可填验证语 `content`；申请成功后提供「加入联系人」触发增量同步或本地落库。

### 4.3 消息历史加载与展示（复用 `SessionChatPanel`）
- **加载**：进入会话时，若 `messages` 无/不足，调用历史回填（P2-1）；聊天面板顶部显示「加载历史」弱提示或自动滚动加载更早消息（分页游标）。
- **展示**：复用现有消息气泡组件，按时间排序；图片/文件气泡（P2-3）复用同一气泡容器扩展渲染。

### 4.4 富消息发送按钮（复用输入框 `chat-input-box`）
- **位置**：`SessionChatPanel` 底部输入框旁，增加「🖼 图片」「📎 文件」两个按钮（复用/扩展现有 `SendMessageDialog`）。
- **行为**：选文件 → 后端代理上传 CDN → 调发送接口 → 乐观追加气泡；`hosted` 或 `msgType==3` 时仍禁用（沿用 P0 逻辑）。

### 4.5 已读操作（复用 `SessionChatPanel` 进入会话逻辑）
- **触发**：打开会话（进入 `SessionChatPanel`）即自动调用 `MarkAsRead`，清除 iPad 未读；会话列表未读角标同步清零。
- **反馈**：无需额外按钮，仅角标状态变化 + 可选轻量 toast（「已标记为已读」）。

### 4.6 内部群聊 tab（兼容方案，复用 `ChannelContacts` 群 tab）
- **展示**：「内部群聊」tab 复用 `ChannelContacts` 现有群渲染；数据默认与「客户群聊」同源（`channel_groups`），或在确认无法区分时渲染空态说明。
- **详情**：点击进入复用现有 `GroupDetailDrawer`（`T04` 已完成）。

---

## 5. 待确认问题（Open Questions，需架构师 / 主理人拍板）

1. **内部群区分**：协议（`GetChatroomMembers`）无「客户群/内部群」区分字段。是否接受 P1-3 兼容方案（内部群 tab 复用 `channel_groups` 同源或空态说明）？还是等待协议补齐区分能力？`group_type` 字段已预留，后续支持可无缝切换。
2. **`GetGroupMsgList` 的 room 选择**：文档示例入参仅有 `uuid`、无 `room_id`，疑似只返回「当前/最近群」。是否可实际传 `room_id` 指定群？还是需逐一切换当前群再拉？这决定群历史回填的实现路径与成本。
3. **消息回填游标与上限**：`SyncAllData` 的 `seq`=最后 `server_id`，建议游标续查上限（参考 P0 的 5000 条/账号上限）；单会话历史分页步长、是否全量回填或仅回填最近 N 条，请定档。
4. **富消息 CDN 上传实现方式**：`CdnUploadImg/File` 为 multipart，建议由**后端代理上传**（前端传文件给后端，后端转发 iPad CDN 拿 `cdn_key` 等再发送），避免把 iPad 账号 `uuid`/密钥暴露给前端；`CdnUploadFile` 返回 `fileid` 而 `SendCDNFileMsg` 需 `cdnKey`，二者映射关系需工程确认。
5. **本地环境回调处理策略**：`SetCallbackUrl` 需公网可达地址，本地 `127.0.0.1` 不可达。开发期是否采用内网穿透（ngrok/frp/cloudflared）暴露回调端点？生产环境回调地址如何配置（环境变量）？未配置时的降级（仅手动同步）是否可接受？
6. **1:1 与群消息是否共用 `messages` 表**：现有设计 `messages.conversation_id = session_id`，1:1 与群会话均有 `session_id`，按此可自然共用。请确认是否统一落 `messages` 表（推荐），还是需要分表（如 `group_messages`）。
7. **P2-1 与 P2-4 强耦合风险**：1:1 历史经 `SyncAllData` 触发、由回调推送，若回调不可用则 1:1 历史无法回填。是否接受「回调可用才回填 1:1 历史、否则仅群聊历史（GetGroupMsgList）可用」的降级？
8. **`sync_type` 范围（标签）**：`GetLabelListReq` 的 `sync_type` 1=企业标签、2=个人标签，是否两类都同步进 Morphix 标签体系，还是仅同步个人标签（外部客户常用）？

---

## 附录：P1 + P2 iPad 接口契约速查（base + `/wxwork/<Action>`）

| 用途 | Action | 入参 | 关键返回 | 落库/前端目标 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| 获取标签列表 | `GetLabelListReq` | `{uuid, index, sync_type}` | `labelList[]{id,name,label_type,label_groupid}` | `customer_tags`/`customer_tag_relations` | P1 |
| 一个用户多个标签（增/减） | `UserAddLabelsReq` | `{uuid, userid, labelid_list[]}` | `ok` | `customer_tag_relations` | P1 |
| 搜索联系人 | `SearchContact` | `{uuid, phoneNumber}` | `userList[]{user_id,name,ticket,openId,corp_id,state}` | 结果面板 | P1 |
| 搜索添加外部联系人 | `AddSearch` | `{uuid, vid, openId, phone, content, ticket}` | `ok` | 触发增量同步 | P1 |
| 直接添加（曾被删除） | `AddWxUser` | `{uuid, vid, content}` | `ok` | 同上 | P1 |
| 同意添加 | `AgreeUser` | `{uuid, corpid, vid}` | `ok` | 来自回调 | P1 |
| 群消息列表 | `GetGroupMsgList` | `{uuid}`（⚠️ 文档无 room 参数） | `listdata[]{id,seq,content[],file_id,...}` | `messages` | P2 |
| 同步消息记录（离线） | `SyncAllData` | `{uuid, limit, seq}` | 触发回调派发离线消息 | 经回调→`messages` | P2 |
| 已读消息 | `MarkAsRead` | `{uuid, send_userid, isRoom}` | 已读回执 | `channel_sessions.unread_count` | P2 |
| CDN 上传图片 | `CdnUploadImg` | `multipart{file, uuid}` | `cdn_key,aes_key,md5,width,height,size` | 发送前暂存 | P2 |
| CDN 上传文件 | `CdnUploadFile` | `multipart{file, uuid}` | `aes_key,fileid,md5,size` | 发送前暂存 | P2 |
| 发送 CDN 图片 | `SendCDNImgMsg` | `{uuid, send_userid, isRoom, cdnkey, aeskey, md5, fileSize,...}` | 发送回执 | 乐观追加气泡 | P2 |
| 发送 CDN 文件 | `SendCDNFileMsg` | `{uuid, send_userid, isRoom, cdnKey, aesKey, md5, file_name, fileSize}` | 发送回执 | 乐观追加气泡 | P2 |
| 设置消息回调 | `SetCallbackUrl` | `{uuid, url, callbackType}` | 回调配置 | 后端收端 | P2 |
