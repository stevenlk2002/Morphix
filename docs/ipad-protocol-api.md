# iPad 协议（企业微信）API 参考

> 来源：showdoc 文档「企业微信协议」（用户提供的访问密码 147258 后读取）
> 文档示例 base（服务 host:port 根）：`http://47.94.7.218:8083`（客户端自动拼接 `/wxwork/<Action>`）
> 用户指定真实服务：`http://47.94.7.218:9912`（实现时 base URL 做成可配置环境变量 `IPAD_PROTOCOL_BASE_URL`，默认即 `http://47.94.7.218:9912`，即服务 host:port 根；客户端再拼 `/wxwork/init` 等）
> 协议托管方式：`deverType: "ipad"`

## 完整对接流程（添加渠道账号 · 企业微信 iPad 托管）

```
1. POST /wxwork/init        -> 拿到 uuid（设备实例标识，生命周期内固定）
2. POST /wxwork/getQrCode   -> 拿到登录二维码（URL 或 base64）+ Key(qrcodeKey) + Ttl
3. [用户用企业微信扫码]       -> 手机端弹出验证码
4. POST /wxwork/CheckCode   -> 提交验证码（uuid + qrcodeKey + code）
5. 轮询 POST /wxwork/GetRunClientInfo -> loginType==2 表示已登录托管成功
```

> 注意：若之前已登录过（init 时传了 vid），获取二维码后**无需**再输验证码。
> CheckCode 若返回 `qrcode_not need verify`，说明手机端验证码界面被提前关掉，需重新走流程。

---

## 1. 初始化企业微信（第一步必须）

- 请求URL：`{base}/wxwork/init`
- 请求方式：POST
- ContentType：application/json

请求参数：

| 参数名 | 必选 | 类型 | 说明 |
|---|---|---|---|
| vid | 否 | long | 第一次登录传空字符串；登录成功后下次初始化填该账号的 id（16888 开头），用于自动登录与设备绑定。首次不传会生成新设备信息 |
| ip | 否 | string | 代理 ip |
| port | 否 | string | 代理端口 |
| proxyType | 否 | string | http 代理类型 |
| userName | 否 | string | 代理账号（无则不传） |
| passward | 否 | string | 代理密码（无则不传） |
| deverType | 否 | string | 设备类型，托管用 `"ipad"` |

请求示例：
```json
{
  "vid": "",
  "ip": "",
  "port": "",
  "proxyType": "",
  "userName": "",
  "passward": "",
  "deverType": "ipad"
}
```

返回示例：
```json
{
  "data": {
    "uuid": "427d7ee5-3a1c-4183-a83b-532ba1e71a1e",
    "is_login": "false"
  },
  "errcode": 0,
  "errmsg": "ok"
}
```

> `uuid` 是该账号生命周期内一直用到的标识，后续所有接口都靠它定位具体账号。

---

## 2. 获取登录二维码

- 请求URL：`{base}/wxwork/getQrCode`
- 请求方式：POST
- ContentType：application/json

请求参数：

| 参数名 | 必选 | 类型 | 说明 |
|---|---|---|---|
| uuid | 是 | String | 每个实例的唯一标识（来自 init） |

请求示例：
```json
{ "uuid": "f5a22e9b-9664-4250-b40a-08741dba549c" }
```

返回示例：
```json
{
  "data": {
    "qrcode": "http://47.94.7.218:8083/980343ff-bf71-4789-8a0a-af3f7fd40bc0.png",
    "qrcode_data": "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDABQODxIPDRQSEBIXFRQYHjIhHhwcHj0s",
    "Ttl": 600,
    "Key": "5DBC31948BB057101F9C6B93569FB39B"
  },
  "errcode": 0,
  "errmsg": "获取二维码成功"
}
```

> `qrcode` 为二维码图片可直接访问的 URL；`qrcode_data` 为 base64 文件流（可用于前端直接渲染）；`Key` 即 `qrcodeKey`，提交验证码时使用；`Ttl` 为有效期（秒）。

---

## 3. 输入验证码设置

- 请求URL：`{base}/wxwork/CheckCode`
- 请求方式：POST
- ContentType：application/json

说明：第一次登录需要输入验证码；若已登录过（init 传了 vid），获取二维码后无需再输验证码。

请求参数：

| 参数名 | 必选 | 类型 | 说明 |
|---|---|---|---|
| uuid | 是 | String | 实例唯一标识 |
| qrcodeKey | 是 | String | 获取二维码返回的 Key |
| code | 是 | String | 手机端显示的验证码 |

请求示例：
```json
{
  "uuid": "2b0863724106a1160212bd1ccf025295",
  "qrcodeKey": "B547FC8D049DFA333D89075C04BA9178",
  "code": "369130"
}
```

返回示例：
```json
{ "data": null, "errcode": 0, "errorcode": 0, "errmsg": "ok" }
```

> 注意事项：若返回 `qrcode_not need verify`，说明输入验证码前把手机上的验证码界面 x 掉了，不要提前关掉，输完验证码会自动关闭。

---

## 4. 根据 uuid 查看实例详情（轮询登录状态）

- 请求URL：`{base}/wxwork/GetRunClientInfo`
- 请求方式：POST
- ContentType：application/json

请求参数：

| 参数名 | 必选 | 类型 | 说明 |
|---|---|---|---|
| uuid | 是 | String | 要查询的账号状态 |

请求示例：
```json
{ "uuid": "xxxxxx" }
```

返回参数说明：

| 参数名 | 类型 | 说明 |
|---|---|---|
| loginType | int | 0 未初始化 / 1 初始化了未登录 / 2 已登录 |
| userInfo | object | 账号信息（acctid, avatar, corpId, mobile, phone, nickname, realname, userId, corpName, corpFullName, unionid 等） |
| longLinkState | String | 企微长连接状态：CONNECTING / HANDSHAKING / CONNECTED / RECONNECTING / CLOSED |

返回示例（节选）：
```json
{
  "data": {
    "loginType": 2,
    "uuid": "053527d77001829b01642bae60f6f5a1",
    "clientId": "75e40e0ade77ac898897da5790e5debe",
    "loginTime": 1780472038698,
    "userInfo": {
      "acctid": "ZXXXg",
      "avatar": "https://wework.qpic.cn/wwpic3az/167304_fPUqqK8DR06dgAG_1779497478/0",
      "corpId": 197032xxx2544,
      "mobile": "13xxx8293",
      "nickname": "6666",
      "realname": "xxxx",
      "userId": 1688xxx59,
      "corpName": "xxxx",
      "corpFullName": "xxxxx"
    },
    "reqUrl": "xxxx:8084",
    "clientCallbackConfig": {
      "callbackType": "HTTP",
      "url": "http://127.0.0.1:8080/wxwork/callback"
    },
    "proxySetting": null,
    "longLinkState": "CONNECTED"
  },
  "errcode": 0,
  "errmsg": "获取成功"
}
```

---

## 5. 获取运行中的实例列表（查看已托管账号）

- 请求URL：`{base}/wxwork/getRunClientList`
- 请求方式：POST
- 参数：无

返回示例（节选）：
```json
{
  "data": {
    "runClientList": [
      {
        "loginType": 2,
        "uuid": "053527d77001829b01642bae60f6f5a1",
        "clientId": "75e40e0ade77ac898897da5790e5debe",
        "loginTime": 1780472038698,
        "userInfo": { "nickname": "6666", "corpName": "济X", "mobile": "13573788293" },
        "longLinkState": "CONNECTED"
      }
    ]
  },
  "errcode": 0,
  "errmsg": "获取成功"
}
```

---

## 实现注意

- 所有接口 base 必须可配置（`IPAD_PROTOCOL_BASE_URL`，为服务 host:port 根），默认本地 `http://127.0.0.1:9912`；客户端自动拼接 `/wxwork/<Action>`。
- 二维码有效期 `Ttl`（秒），前端展示后应启动倒计时与轮询。
- 轮询策略：展示二维码后，后端按 `uuid` 轮询 `GetRunClientInfo`，`loginType==2` 即托管成功；期间用户扫码后手机显示验证码，前端收集 `code` 调 `CheckCode`。
- 错误码：除 `errcode:0 / errmsg:"ok"` 外，注意 `qrcode_not need verify` 等特定错误。
