# 账号卡片增强 PRD（增量）

> 项目：`software-morphix-account-card` ｜ 语言：中文 ｜ 技术栈：FastAPI + SQLite / Vite + React 18 + TypeScript
> 变更类型：增量（仅改账号卡片展示与默认机器人配置，不新增渠道类型）

## 原始需求复述
用户已用真实 iPad 协议绑定企业微信渠道账号。当前卡片显示默认编号名"企业微信-0a9f62"、无真实头像、名称旁无企微图标、右侧"设置/托管管理/换绑团队"按钮竖排、缺少"默认单聊机器人"和"默认群聊机器人"展示。需对齐参考图：真实头像 + 真实昵称 + 企微图标 + ipad 在线徽标 + 会话数 + 默认单聊/群聊机器人展示与修改 + 底部横排按钮。

## 1. 变更目标
让企业微信 iPad 协议账号卡片展示真实身份（头像 / 昵称 / 企微标识）与"默认单聊 / 群聊机器人"配置，并将操作按钮规整为卡片底部横排，对齐参考图效果。

## 2. 用户故事
- 作为运营，我希望在账号列表中一眼看到企微账号的真实头像、昵称与在线状态，便于快速确认绑定的是正确账号。
- 作为运营，我希望在卡片上直接查看并修改"默认单聊机器人 / 默认群聊机器人"，便于配置托管默认接管方、减少进入二级页的操作。

## 3. 需求池

### P0（必须）
| # | 模块 | 需求 | 验收标准 |
|---|---|---|---|
| P0-1 | 后端 | 修正 `poll_wecom` 命名优先级：真实 `nickname` / `realname` 优先于 `start` 传入的默认名，兜底保留 `企业微信-{uuid[:6]}` | 新建账号名 = 真实昵称，不再被默认名覆盖 |
| P0-2 | DB | 迁移 `channel_accounts` 新增 `avatar`(TEXT)、`default_single_bot_id`(TEXT NULL)、`default_group_bot_id`(TEXT NULL) | 迁移脚本可执行，存量账号字段为 NULL |
| P0-3 | 后端 | 创建账号时从 `user_info` 写入 `avatar`（头像字段来源见待确认 Q3） | 列表 / `account` 返回 `avatar` URL |
| P0-4 | 后端 | 列表 / 详情接口返回 `avatar`、`default_single_bot_id`、`default_group_bot_id`；`AccountDTO` 补充对应字段 | 前端可直接消费 |
| P0-5 | 后端 | 新增 / 复用接口设置默认单聊 / 群聊机器人，校验机器人"已上线"且属当前团队 | 写库成功；跨团队 / 非上线状态拒绝 |
| P0-6 | 后端 | 提供"已上线"机器人枚举接口（`id + name`） | 作为前端选择器数据源 |
| P0-7 | 前端 | 卡片：圆形真实头像（有图用 `<img>`，无图首字母 + 背景色兜底），显示真实昵称，名称旁显示绿色企微气泡图标 | 视觉对齐参考图 |
| P0-8 | 前端 | 卡片：保留"ipad 在线"徽标；展示"账号会话 N" | 现状保持 + 会话数展示 |
| P0-9 | 前端 | 卡片：展示"默认单聊机器人 → 名称""默认群聊机器人 → 名称"（含空态文案） | 文案与值正确 |
| P0-10 | 前端 | "设置 / 托管管理 / 换绑团队"改为卡片底部一行横排 | 不再右侧竖排 |
| P0-11 | 前端 | 点击默认机器人行弹选择器修改（数据源 = 已上线机器人） | 可改、改后即时反映 |

### P1（应有）
- 列表接口一次性聚合默认机器人名称，减少前端二次请求。
- 默认机器人变更后卡片乐观更新。
- 换绑团队按待确认 Q2 结果决定打通或继续占位。

### P2（可选）
- 头像懒加载 + 失败回退首字母重试。
- WhatsApp 等多渠道复用同一卡片样式（企微图标换为对应渠道图标）。
- 机器人选择器支持搜索 / 分组。

## 4. UI 设计说明

### 布局（卡片由横排改为纵向堆叠）
| 区域 | 元素 | 规格 | 说明 |
|---|---|---|---|
| 容器 | `.channel-account-card` | `flex-direction: column; align-items: stretch`；padding 18px；圆角 var(--radius)；边框 var(--line) | 由当前 `main \| stats \| actions` 横排改为纵向 |
| 头部 | 头像 | 圆形 52×52，`border-radius: 50%`（原 14px 方角改圆） | 有 `avatar` 用图，无则首字母 + `avatarColor(a.id)` 兜底 |
| 头部 | 名称 | 16px / 800（var(--text-md)） | 显示真实昵称 |
| 头部 | 企微图标 | 聊天气泡 14px，色 `#07c160`，名称右侧 8px | 绿色企业微信标识 |
| 头部 | 在线徽标 | "ipad 在线" 11px / 700，绿底绿字（沿用 --green `#22c55e`） | 保持现状 |
| 信息 | 账号会话 | label 12px muted + value 20px / 800（var(--text-2xl)） | 保持现状 |
| 信息 | 默认单聊机器人 | label 12px muted + "→ 名称" 13px | 整行可点击，触发选择器 |
| 信息 | 默认群聊机器人 | 同上 | 整行可点击 |
| 底部 | 操作按钮 | 3 个 outline 按钮横排，`flex-direction: row`，`gap: 8px`，`width: 100%` | 设置 / 托管管理 / 换绑团队均分或 space-between |

### 颜色与间距
- 企微绿：`#07c160`；在线绿：沿用 `--green #22c55e`；描边按钮：沿用 `.btn-outline`（边框 --line，hover 变蓝）。
- 区块竖向间距 12–14px；头像与文字 gap 14px；卡片内 padding 18px。
- 字号层级：名称 16px(800) / 信息 label 12px(muted) / 会话值 20px(800) / 徽标 11px。

### 关键样式变更（示意）
```css
.channel-account-card { flex-direction: column; align-items: stretch; gap: 12px; }
.channel-account-avatar { border-radius: 50%; }            /* 圆形 */
.channel-account-actions { flex-direction: row; width: 100%; gap: 8px; }
.wecom-name-icon { width: 14px; height: 14px; color: #07c160; margin-left: 8px; }
.default-bot-row { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
```

## 5. 待确认问题
1. **默认机器人是否允许为空？** 空态显示"未设置"还是必须至少选一个？影响必填校验与卡片空态文案。
2. **换绑团队本次是否打通？** 当前为 P2 toast 占位；本次是按参考图实现真实换绑，还是继续占位、仅做横排样式？
3. **头像 / 昵称字段来源与优先级？** `user_info` 中头像字段名（`avatar` / `headImgUrl` / `headimgurl`？）、昵称优先级（`nickname` vs `realname`）如何取舍？存量"企业微信-xxx"账号是否需要回填修正脚本？
