# Morphix P0 主链路联调集合（Bruno）

本集合覆盖 `plan-联调测试用例清单.md` 中全部 **P0** 用例，串成「Morphix 主业务闭环」：

```
设备注册/绑定 → 令牌刷新 → 在线心跳(含反向指令) → 设备/运行时上报入站消息
→ 控制面/运行时编排(生成会话运行态、WorkflowRun、DeviceCommand)
→ 设备拉取命令 → ACK / complete / fail 回执
→ 人工接管与交还 → 运行态 / 节点 / 决策审计查询
```

并包含关键异常反例：**重复消息幂等、重复回执 no-op、设备离线重投、断网补传回执、接管后设备停发**。

## 1. 安装 Bruno

- 桌面端：https://www.usebruno.com/downloads （推荐，开箱即用，可视化链式运行）
- CLI：`npm install -g bru` 或 `brew install bruno`

## 2. 用桌面端打开

1. 打开 Bruno 桌面端 → `Open Collection` → 选择本目录（`Morphix P0 主链路`）。
2. 环境：顶部环境选择器选择 `Morphix P0 主链路`（即根目录 `bruno.json`）。
   - 若桌面端未自动识别根 `bruno.json` 为环境，可将其复制到 `environments/Morphix P0 主链路/bruno.json` 后再选。
3. 填写 token（见第 4 节），然后按文件夹顺序点选请求运行，或用 `Run` 顺序执行整个集合。

## 3. 用 CLI 运行

```bash
# 从本目录（集合根）执行全部请求
bru run --env "Morphix P0 主链路"

# 仅跑某个阶段
bru run 设备接入 --env "Morphix P0 主链路"
```

> 说明：本集合把环境变量放在集合根 `bruno.json`（按任务要求）。若你的 Bruno 版本要求环境位于
> `environments/<名>/bruno.json`，复制一份即可，变量内容完全一致。

## 4. 变量怎么填（首次运行只需填 token）

集合根 `bruno.json` 已定义全部变量，**除 token 外都有默认/自动写入值**：

| 变量 | 说明 | 谁来填 |
|---|---|---|
| `baseUrl` | `http://localhost:8000`（本地）/ `https://api.morphix.local`（联调） | 已默认 |
| `controlToken` | 控制面 JWT（`Authorization: Bearer`） | **你填** |
| `runtimeToken` | 执行面令牌（`X-Runtime-Token`） | **你填** |
| `deviceToken` | 设备令牌（`X-Device-Token`） | 注册后**自动写** |
| `internalToken` | 内部服务令牌（`X-Internal-Service-Token`） | 仅 E05 用，**你填** |
| `provisioningKey` | 设备预配置密钥（`X-Device-Provisioning-Key`） | **你填** |
| `projectId` / `channelAccountId` | 项目/渠道账号 ID（任务中的 `channelId` 即 `channelAccountId`） | 已默认，可改 |
| `conversationId` / `deviceId` / `runId` / `commandId` / `inboundRequestId` | 链路中间产物 | 运行中**自动写** |
| `operatorId` / `bindCode` / `workflowVersionId` | 运营 ID / 绑定码 / 工作流版本 | 已默认，可改 |

token 如何获取（需架构/后端确认，见文末待确认项）：
- `controlToken`：运营控制台登录后下发的 JWT。
- `runtimeToken`：渠道接入层/网关的服务身份令牌。
- `provisioningKey`：设备首次注册的一次性预配置密钥（绑定码配套）。
- `deviceToken`：由「设备注册绑定」响应 `data.deviceToken` 自动写入，**不要手填**。

## 5. 推荐跑通顺序（端到端）

1. **设备接入**：注册绑定 → 令牌刷新 → 心跳 →（可选）设备直接上报入站消息
2. **运行时编排**：上报入站消息-单聊 → 查询入站事件状态 → 创建设备命令
   （这一步会自动把 `conversationId / runId / commandId` 写入环境变量）
3. **设备命令回执**：设备拉取待执行命令 → ACK → complete
4. **人工接管**：发起人工接管 →（验证设备拉取为空）→ 交还托管
5. **审计查询**：查询运行实例详情 → 查询节点轨迹
6. **异常边界**：按需要单跑幂等/重投/补传/安全反例
7. **门禁验收(G)**：M1~M5 探活（多为只读验证，详见下方映射）

> 链式关键：请求 `afterResponse` 脚本用 `bru.setEnvVar` 把响应里的
> `deviceId/deviceToken/channelAccountId/conversationId/runId/commandId/inboundRequestId`
> 写入环境变量，后续请求直接引用 `{{...}}`，因此**顺序运行即可自动串起主链路**。

## 6. 里程碑门禁映射（P0 用例 → 门禁）

| 门禁 | 含义 | 由以下 P0 用例 / 请求证明 |
|---|---|---|
| M1 | 开发基线冻结 | G01（控制面探活）、F01（鉴权拒绝） |
| M2 | 运行时命令可生成 | G02、运行时编排-上报入站消息、创建设备命令、E01（幂等） |
| M3 | 设备回执闭环 | 设备接入全量、设备命令回执全量、E02/E03/E04、D02 |
| M4 | 控制台可操作 | 控制面入口全量、人工接管、审计查询、F03 |
| M5 | 小流量灰度就绪 | G05（审计可观测）、E05（兜底）、E07（fail→人工）、控制开关经心跳/注册响应下发 |

## 7. 已知待确认（契约不明确处，详见主理人回报）

- 幂等 Header 名称：OpenAPI 参数定义为 `Idempotency-Key`，任务描述写为 `X-Idempotency-Key`。
  本集合**按 OpenAPI 使用 `Idempotency-Key`**，请用前与架构确认服务端实际接受的名字。
- 跨项目越权返回码：契约仅定义 401/404，未显式定义 403；错误码枚举含 `FORBIDDEN`。
  TC-F03 期望 403 或 404，需确认。
- 各 token 获取接口：当前 OpenAPI 未提供 `controlToken/runtimeToken/provisioningKey` 的签发端点，
  仅 `deviceToken` 由注册接口返回。需在联调前明确这些 token 的获取方式。
