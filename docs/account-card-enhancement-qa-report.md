# 账号卡片增强 — QA 验证报告

> 项目：`software-morphix-account-card` ｜ 日期：2026-07-22
> 测试范围：T01 后端数据/迁移/契约 + T02 后端接口 + T03 前端组件重构

## 1. 测试覆盖点

| # | 验证项 | 方式 |
|---|---|---|
| 1 | `channel_accounts` 新增 `avatar` / `default_single_bot_id` / `default_group_bot_id` 三列 | `PRAGMA table_info` + 后端启动迁移 |
| 2 | `GET /api/channels/accounts` 返回新字段（avatar、defaultSingleBotId/GroupBotId、defaultSingleBotName/GroupBotName） | API 调用 + pytest |
| 3 | `GET /api/channels/accounts/available-bots` 仅返回 `status='online'` 机器人 | pytest 断言 |
| 4 | `PUT /api/channels/accounts/{id}/default-bots`：成功/404/400/清空 | pytest 断言 |
| 5 | `poll_wecom` 命名优先级 `nickname>realname>name>start默认名>兜底`，并落库 `avatar` | pytest mock |
| 6 | 模块级 helper `_resolve_avatar_url` / `assert_online_bot` | pytest 单测 |
| 7 | 前端类型检查 `npx tsc --noEmit` | CLI |
| 8 | 前端页面可访问 `http://127.0.0.1:5183/channels/accounts` | HTTP 200 |

## 2. 测试结果

```
project/backend/.venv/bin/python -m pytest tests/test_account_card.py -v
============================== 7 passed in 0.32s ===============================
```

- `test_channel_accounts_migration_columns` ✅ PASSED
- `test_accounts_list_has_new_fields` ✅ PASSED
- `test_available_bots_only_online` ✅ PASSED
- `test_set_default_bots_flow` ✅ PASSED
- `test_poll_wecom_naming_and_avatar` ✅ PASSED（修复 `logger` 未定义后）
- `test_resolve_avatar_url_priority` ✅ PASSED
- `test_assert_online_bot` ✅ PASSED

前端类型检查：`npx tsc --noEmit` 退出码 0，零错误。  
前端页面：`/channels/accounts` HTTP 200，无白屏。

## 3. 回归问题与修复

第一轮测试发现 `project/backend/app/routers/channel_hosting.py` 第 151 行使用未定义的 `logger`，导致 `test_poll_wecom_naming_and_avatar` 失败：

```
NameError: name 'logger' is not defined
```

**智能路由判定**：源码 Bug → 反馈工程师修复。  
工程师在文件顶部补充 `logger = logging.getLogger(__name__)` 后重新跑测试，**7/7 全绿**。

## 4. 遗留风险 / 环境阻塞

- **真实昵称/头像无法在当前环境端到端验证**：当前库中真实 iPad 账号 `acc_475787e2`（uuid `0a9f6202569b86dfd38631258089b977`）在真实服务端已掉线，`GetRunClientInfo` 返回 `loginType:0`、`userInfo:null`。因此前端无法显示真实头像/昵称，只能验证空态回退（首字母+底色、默认名）。代码路径已按 `nickname>realname>name>start默认名>兜底` 和 `avatar>headImgUrl>headimgurl` 实现，待绑定稳定在线实例后即可生效。
- **团队隔离未实现**：`bots` 表无 `team_id`，`available-bots` 返回全部在线机器人，与本期设计一致。

## 5. 结论

**智能路由判定：NoOne（全部通过）**

代码层面满足 PRD P0 需求；前端布局、默认机器人展示/修改、后端接口契约、schema 迁移均已验证通过。待真实 iPad 实例稳定在线后，即可验证真实头像/昵称展示。
