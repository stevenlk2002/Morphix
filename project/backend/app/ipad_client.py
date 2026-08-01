"""企业微信 iPad 协议客户端。

对外暴露高层封装 `start_wecom / verify_wecom / poll_wecom`，
对上层（Router / 前端）屏蔽「真实 iPad 协议服务 vs mock 兜底」的差异。

设计要点（见 docs/system_design.md 第 3.1 节）：
- 模式由 `IPAD_PROTOCOL_MODE` 控制：`auto`（默认，先试真实，失败转 mock）/
  `real`（强制真实，失败抛 `IPadProtocolError`）/ `mock`（直接走 mock 分支）。
- 底层 HTTP 使用 `httpx`，`timeout=3.0`。任何连接异常 / 非 200 / 超时 → 视为失败；
  在 `auto`/`mock` 模式下降级为 mock；`real` 模式下抛异常由路由层转 502。
- mock 与真实返回**同构**，保证前端 UI 流转可完整演示。
- `MockState` 为进程内字典，足够演示；记录 `team_id / name / channel_type / verified`，
  供 `poll` 在 `loginType==2` 时落库取用。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# 1x1 透明 PNG（base64），用于 mock 二维码数据占位。
_MOCK_QRCODE_DATA = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# 进程内 mock 状态：uuid -> {"team_id", "name", "channel_type", "verified"}。
MockState: dict[str, dict] = {}


class IPadProtocolError(RuntimeError):
    """iPad 协议真实服务异常（real 模式下向上抛出，由路由层转 502）。"""


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------
def _base_url() -> str:
    """去除末尾斜杠的基址，避免拼路径时出现双斜杠。"""
    return (settings.ipad_protocol_base_url or "http://47.94.7.218:9912").rstrip("/")


def _mode() -> str:
    """当前协议模式（小写，缺省 auto）。"""
    return (settings.ipad_protocol_mode or "auto").lower()


def _post(path: str, payload: dict, timeout: float = 8.0) -> dict:
    """调用 iPad 协议服务；任何失败都抛出 `IPadProtocolError`。

    真实服务路径形如 `{base}/wxwork/<Action>`（base 为服务 host:port 根，
    默认 http://47.94.7.218:9912，客户端自动拼接 /wxwork/<Action>，
    详见 IPAD_PROTOCOL_BASE_URL 配置）。

    `timeout` 默认 8s：iPad 协议服务实测 `init` 拉起实例耗时常 >2.5s，在受限
    网络（代理/跨区）下容易超过 3s；过短的超时会被 `auto` 模式误判为服务不可用
    而降级成 mock（二维码变成 1x1 透明占位图）。`init`/`getQrCode` 用更长超时，
    普通调用用默认 8s 即可。
    """
    url = f"{_base_url()}/{path.lstrip('/')}"
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
    except (httpx.HTTPError, OSError) as exc:
        raise IPadProtocolError(f"iPad 协议服务调用失败: {url} ({exc})")
    if resp.status_code != 200:
        raise IPadProtocolError(
            f"iPad 协议服务返回非 200: HTTP {resp.status_code} ({url})"
        )
    try:
        data = resp.json()
    except ValueError as exc:
        raise IPadProtocolError("iPad 协议服务返回非 JSON 响应") from exc
    # 统一校验业务 errcode：真实服务常返回 HTTP 200 + {"errcode":500,...}
    # （如实例掉线时的「实例未登录」），若只判 HTTP 状态码会被误判为成功，
    # 导致全量同步静默落库 0 条并上报 success。errcode 为 0 / 缺省视为成功。
    errcode = data.get("errcode") if isinstance(data, dict) else None
    if errcode not in (None, 0, "0"):
        errmsg = (data.get("errmsg") if isinstance(data, dict) else None) or "iPad 协议返回业务错误"
        raise IPadProtocolError(f"iPad 协议业务错误 errcode={errcode}: {errmsg} ({url})")
    return data


def _norm(data: dict) -> dict:
    """兼容 `{...}` 与 `{"data": {...}}` 两种信封，统一取业务体。"""
    return data.get("data", data) if isinstance(data.get("data"), dict) else data


# ---------------------------------------------------------------------------
# 底层归一化函数（真实服务适配；失败抛 IPadProtocolError）
# ---------------------------------------------------------------------------
def init(dever_type: str = "ipad", vid: str = "") -> dict:
    """POST `{base}/wxwork/init` → `{uuid, is_login}`（归一化）。

    `vid` 为已登录账号的设备绑定 id（首次扫码传空串 `""`，登录成功后由
    `userInfo.userId` 持久化得到）。自动登录续传场景传入持久化 vid 取得新 uuid，
    再调 `automatic_login` 即可免扫码恢复登录（见 docs/IPad协议API文档）。
    """
    data = _post(
        "wxwork/init",
        {
            "vid": vid,
            "ip": "",
            "port": "",
            "proxyType": "",
            "userName": "",
            "passward": "",
            "deverType": dever_type,
        },
        timeout=15.0,
    )
    body = _norm(data)
    is_login = str(body.get("is_login", "false")).lower() in ("true", "1")
    return {
        "uuid": body.get("uuid") or "",
        "is_login": is_login,
    }


def get_qrcode(uuid: str) -> dict:
    """POST `{base}/wxwork/getQrCode` → `{qrcode, qrcode_data, ttl, qrcode_key}`。"""
    data = _post("wxwork/getQrCode", {"uuid": uuid}, timeout=12.0)
    body = _norm(data)
    return {
        "qrcode": body.get("qrcode"),
        "qrcode_data": body.get("qrcode_data") or body.get("qrcodeData"),
        "ttl": int(body.get("ttl") or body.get("Ttl") or 600),
        "qrcode_key": body.get("qrcode_key") or body.get("qrcodeKey") or body.get("Key") or "",
    }


def check_code(uuid: str, key: str, code: str) -> dict:
    """POST `{base}/wxwork/CheckCode` → `{ok, skip}`。

    真实协议成功响应为 `{"data": null, "errcode": 0, "errmsg": "ok"}`，
    没有 `ok` 字段，因此以 `errcode == 0` / `errmsg` 表示成功。
    `qrcode_not need verify` / `qrode_not need verify` 视为 `ok=True, skip=True`。
    """
    data = _post("wxwork/CheckCode", {"uuid": uuid, "qrcodeKey": key, "code": code})
    body = _norm(data)
    # 协议文档 typo：qrode_not need verify；同时兼容 qrcode_not need verify / not need verify
    errmsg = str(body.get("errmsg", "") or data.get("errmsg", "") or body.get("msg", "") or data.get("msg", "")).lower()
    if "qrode_not need verify" in errmsg or "qrcode_not need verify" in errmsg or "not need verify" in errmsg:
        return {"ok": True, "skip": True}
    # 真实协议用 errcode/errmsg 表示结果；_post 已对非 0 errcode 抛 IPadProtocolError，能走到这里说明 errcode 为 0
    errcode = body.get("errcode") if isinstance(body, dict) else data.get("errcode")
    ok = errcode in (0, "0") or (errcode is None and "ok" in errmsg)
    return {"ok": ok, "skip": False}


def get_run_client_info(uuid: str) -> dict:
    """POST `{base}/wxwork/GetRunClientInfo` → `{loginType, userInfo, longLinkState}`。

    兼容协议文档定义的两种返回格式：
    1) `data` 直接含字段：
       `{"data": {"loginType": 2, "userInfo": {...}, "longLinkState": "CONNECTED"}}`
    2) `data.runClientList` 数组（多账号托管场景）：
       `{"data": {"runClientList": [{"loginType": 2, "userInfo": {...},
        "longLinkState": "CONNECTED"}]}}`

    第 2 种格式下，取 `runClientList` 第一个非空元素作为 `clientInfo` 解析源；
    否则直接以 `body` 为解析源。最终始终输出 `loginType`/`userInfo`/`longLinkState`
    （保持 snake_case 字段 `login_type`/`user_info`/`long_link_state` 兼容）。
    """
    data = _post("wxwork/GetRunClientInfo", {"uuid": uuid})
    body = _norm(data)

    # 兼容 data.runClientList 数组格式：取第一个非空（非空 dict）元素作为 clientInfo。
    run_client_list = body.get("runClientList") if isinstance(body, dict) else None
    if isinstance(run_client_list, list) and run_client_list:
        client_info = next(
            (item for item in run_client_list if isinstance(item, dict) and item),
            run_client_list[0],
        )
    else:
        client_info = body

    return {
        "loginType": int(
            client_info.get("loginType", client_info.get("login_type", 1))
        ),
        "userInfo": client_info.get("userInfo") or client_info.get("user_info"),
        "longLinkState": (
            client_info.get("longLinkState")
            or client_info.get("long_link_state")
            or "CONNECTING"
        ),
    }


def automatic_login(uuid: str) -> dict:
    """POST `{base}/wxwork/automaticLogin` → 自动登录续传（init(vid) 后调用）。

    返回 `{"ok": bool, "errmsg": str}`。`errcode==0`（errmsg 多为「登陆成功」）视为成功；
    _post 已对非 0 errcode 抛 IPadProtocolError，能走到这里说明 errcode 为 0。
    """
    data = _post("wxwork/automaticLogin", {"uuid": uuid})
    body = _norm(data)
    errcode = body.get("errcode") if isinstance(body, dict) else data.get("errcode")
    ok = errcode in (None, 0, "0")
    errmsg = str(body.get("errmsg", "") or data.get("errmsg", "") or "")
    return {"ok": ok, "errmsg": errmsg}


# ---------------------------------------------------------------------------
# iPad 协议：渠道会话 + 客户管理同步（T01）
# 沿用 _post/_norm，失败统一抛 IPadProtocolError；由同步服务捕获处理（决策 #7）。
# ---------------------------------------------------------------------------
def get_inner_contacts(uuid: str, str_seq: str = "", limit: int = 100) -> dict:
    """POST `{base}/wxwork/GetInnerContacts` → 内部联系人列表（游标 `strSeq`）。

    返回 `{list, strSeq}`，`strSeq` 为下一页游标（服务端透传；为空表示末页）。
    `is_department=1` 的部门条目由同步服务过滤，不在此处处理。
    """
    data = _post(
        "wxwork/GetInnerContacts",
        {"uuid": uuid, "limit": limit, "strSeq": str_seq},
    )
    body = _norm(data)
    return {
        "list": body.get("list") or [],
        "strSeq": body.get("strSeq", "") or "",
    }


def get_external_contacts(uuid: str, seq: int = 0, limit: int = 100) -> dict:
    """POST `{base}/wxwork/GetExternalContacts` → 外部联系人（客户）列表（游标 `seq`）。

    返回 `{list, seq}`，`seq` 为下一页游标（整数）。
    """
    data = _post(
        "wxwork/GetExternalContacts",
        {"uuid": uuid, "limit": limit, "seq": int(seq)},
    )
    body = _norm(data)
    return {
        "list": body.get("list") or [],
        "seq": int(body.get("seq", 0) or 0),
    }


def get_session_list(uuid: str, star_index: int = 0, limit: int = 100) -> dict:
    """POST `{base}/wxwork/GetSessionList` → 会话列表（游标 `star_index`）。

    返回 `{room_list, star_index}`，`room_list[]` 每项含
    `sessionid`/`msgtype`(0好友1群聊3app6开放平台)/`unreadcnt`/`beginmsgseq`。
    """
    data = _post(
        "wxwork/GetSessionList",
        {"uuid": uuid, "limit": limit, "star_index": int(star_index)},
    )
    body = _norm(data)
    return {
        "room_list": body.get("room_list") or [],
        "star_index": int(body.get("star_index", 0) or 0),
    }


def get_chatroom_members(uuid: str, star_index: int = 0, limit: int = 100) -> dict:
    """POST `{base}/wxwork/GetChatroomMembers` → 客户群列表（游标 `star_index`）。

    返回 `{room_list, star_index}`，`room_list[]` 每项含
    `room_id`/`nickname`/`total`/`roomUrl`/`create_time`/`update_time`。
    P0 统一以 `group_type='customer_group'` 落库（决策 #10）。
    """
    data = _post(
        "wxwork/GetChatroomMembers",
        {"uuid": uuid, "limit": limit, "star_index": int(star_index)},
    )
    body = _norm(data)
    return {
        "room_list": body.get("room_list") or [],
        "star_index": int(body.get("star_index", 0) or 0),
    }


def get_session_room_list(uuid: str, star_index: int = 0, limit: int = 100) -> dict:
    """POST `{base}/wxwork/GetSessionRoomList` → 会话列表中的群聊（游标 `star_index`）。

    真实 iPad 服务对该账号的 `GetChatroomMembers` 可能返回 0 条，而本接口返回
    真实群数据（如「教育培训部」「医林通早会群」）。因此同步服务以本接口为主群
    数据源，`GetChatroomMembers` 作为兜底/补充。

    返回 `{room_list, star_index}`，`room_list[]` 每项字段兼容：
    `room_id`/`roomId`、`nickname`、`total`、`roomurl`/`roomUrl`、
    `managers`、`image_url`/`imageUrl`/`room_url`、`is_external`。
    """
    data = _post(
        "wxwork/GetSessionRoomList",
        {"uuid": uuid, "limit": int(limit), "star_index": int(star_index)},
    )
    body = _norm(data)
    return {
        "room_list": body.get("room_list") or [],
        "star_index": int(body.get("star_index", 0) or 0),
    }


def get_room_user_list(uuid: str, room_id: str) -> dict:
    """POST `{base}/wxwork/GetRoomUserList` → 群成员详情（T04）。

    返回 `{room_id, nickname, total, notice_content, member_list[]}`，
    `member_list[]` 每项含 `nickname`/`realname`/`avatar`/`uin`/`room_nickname`/
    `sex`/`mobile`/`jointime`。
    """
    data = _post("wxwork/GetRoomUserList", {"uuid": uuid, "roomid": room_id})
    body = _norm(data)
    member_list = body.get("member_list") or body.get("memberList") or []
    return {
        "room_id": body.get("room_id") or body.get("roomId") or room_id,
        "nickname": body.get("nickname", ""),
        "total": int(body.get("total", 0) or 0),
        "notice_content": body.get("notice_content") or body.get("noticeContent") or "",
        "member_list": member_list,
    }


def send_text_msg(
    uuid: str,
    send_userid: str,
    is_room: bool,
    content: str,
    kf_id: int = 0,
) -> dict:
    """POST `{base}/wxwork/SendTextMsg` → 发送文本消息。

    入参 `send_userid` 为好友 `user_id` 或群 `room_id`；`is_room` 标识群消息；
    `kf_id` 默认 0。失败抛 `IPadProtocolError`（路由层据模式转 502/降级）。
    """
    data = _post(
        "wxwork/SendTextMsg",
        {
            "uuid": uuid,
            "send_userid": send_userid,
            "isRoom": bool(is_room),
            "content": content,
            "kf_id": int(kf_id),
        },
    )
    body = _norm(data)
    # 真实服务可能在 HTTP 200 下返回业务错误（errcode != 0），例如
    # 「uuid 失效 / 实例不存在」。必须显式检查，否则会被静默当成成功，
    # 上层返回 ok:true 却发不出消息（见任务 Issue #4 复盘）。
    if isinstance(body, dict):
        errcode = body.get("errcode", body.get("err_code"))
        if errcode not in (None, 0, "0", "ok"):
            errmsg = body.get("errmsg") or body.get("err_msg") or "未知业务错误"
            raise IPadProtocolError(f"iPad 发送失败: {errmsg} (errcode={errcode})")
    return {
        # 真实服务返回 int/None，统一转 str 以适配 SendTextResultDTO（str 字段），
        # 避免上游响应 schema 校验失败（见任务 Issue #4）。
        "msg_id": str(body.get("msg_id") or body.get("msgId") or ""),
        "server_id": str(body.get("server_id") or body.get("serverId") or ""),
        "content": body.get("content", ""),
        "sendtime": body.get("sendtime") or body.get("sendTime") or "",
        "sender": body.get("sender", ""),
        "receiver": body.get("receiver", ""),
    }


def create_chatroom(uuid: str, wxids: list[str], room_name: str = "") -> dict:
    """POST `{base}/wxwork/CreateChatRoom` → 创建群聊。

    入参 `wxids` 为好友 user_id 列表；`room_name` 可选群名。
    返回 `{room_id, ok, mock}`；`real` 模式失败抛 `IPadProtocolError`，
    `auto`/`mock` 模式失败则降级 mock，保证前端 UI 不阻塞。
    """
    if not wxids:
        raise IPadProtocolError("创建群聊成员列表为空")

    mode = _mode()
    if mode == "real":
        data = _post(
            "wxwork/CreateChatRoom",
            {"uuid": uuid, "wxids": wxids, "roomName": room_name or ""},
        )
        body = _norm(data)
        return {
            "room_id": str(body.get("room_id") or body.get("roomId") or ""),
            "ok": True,
            "mock": False,
        }
    if mode == "auto":
        try:
            data = _post(
                "wxwork/CreateChatRoom",
                {"uuid": uuid, "wxids": wxids, "roomName": room_name or ""},
            )
            body = _norm(data)
            return {
                "room_id": str(body.get("room_id") or body.get("roomId") or ""),
                "ok": True,
                "mock": False,
            }
        except IPadProtocolError as exc:
            logger.warning("CreateChatRoom 真实调用失败，降级 mock: %s", exc)
    # auto 失败降级 / mock 模式：本地生成 room_id
    return {
        "room_id": f"mock_room_{uuid.uuid4().hex[:8]}",
        "ok": True,
        "mock": True,
    }


# ---------------------------------------------------------------------------
# 高层封装（前端真正调用）
# ---------------------------------------------------------------------------
def _mock_qr(team_id: str, name: Optional[str], channel_type: str) -> dict:
    """生成 mock 扫码响应，并把上下文写入 `MockState`。"""
    gen_uuid = str(uuid.uuid4())
    MockState[gen_uuid] = {
        "team_id": team_id,
        "name": name,
        "channel_type": channel_type,
        "verified": False,
    }
    return {
        "uuid": gen_uuid,
        "qrcode": None,
        "qrcode_data": _MOCK_QRCODE_DATA,
        "ttl": 600,
        "qrcode_key": "MOCKKEY",
        "mock": True,
    }


def start_wecom(
    team_id: str, name: Optional[str] = None, channel_type: str = "wecom"
) -> dict:
    """发起托管扫码：真实 `init`+`getQrCode`，失败降级 mock。

    - `real`：真实失败抛 `IPadProtocolError`。
    - `auto`：真实失败转 mock。
    - `mock`：直接走 mock。
    所有模式均把 `team_id / name / channel_type` 落入 `MockState` 供 `poll` 取用。
    """
    mode = _mode()
    if mode == "real":
        init_res = init()
        qr = get_qrcode(init_res["uuid"])
        MockState[init_res["uuid"]] = {
            "team_id": team_id,
            "name": name,
            "channel_type": channel_type,
            "verified": False,
        }
        return {
            "uuid": init_res["uuid"],
            "qrcode": qr.get("qrcode"),
            "qrcode_data": qr.get("qrcode_data"),
            "ttl": qr.get("ttl", 600),
            "qrcode_key": qr.get("qrcode_key", ""),
            "mock": False,
        }
    if mode == "auto":
        try:
            init_res = init()
            qr = get_qrcode(init_res["uuid"])
            MockState[init_res["uuid"]] = {
                "team_id": team_id,
                "name": name,
                "channel_type": channel_type,
                "verified": False,
            }
            return {
                "uuid": init_res["uuid"],
                "qrcode": qr.get("qrcode"),
                "qrcode_data": qr.get("qrcode_data"),
                "ttl": qr.get("ttl", 600),
                "qrcode_key": qr.get("qrcode_key", ""),
                "mock": False,
            }
        except IPadProtocolError:
            # 降级 mock
            pass
    return _mock_qr(team_id, name, channel_type)


def verify_wecom(uuid: str, key: str, code: str) -> dict:
    """校验验证码：真实 `CheckCode`，失败降级 mock（标记 `verified=True`）。"""
    mode = _mode()
    if mode == "real":
        return check_code(uuid, key, code)
    if mode == "auto":
        try:
            return check_code(uuid, key, code)
        except IPadProtocolError:
            pass
    state = MockState.get(uuid)
    if state is not None:
        state["verified"] = True
    return {"ok": True}


def _mock_poll(uuid: str) -> dict:
    """mock 轮询：verified 后返回 loginType=2 合成信息，否则 CONNECTING。"""
    state = MockState.get(uuid, {})
    if state.get("verified"):
        return {
            "loginType": 2,
            "userInfo": {
                "nickname": "演示账号",
                "corpName": "演示企业",
                "avatar": "",
                "userId": "",
                "corpId": "",
            },
            "longLinkState": "CONNECTED",
            "mock": True,
        }
    return {
        "loginType": 1,
        "userInfo": None,
        "longLinkState": "CONNECTING",
        "mock": True,
    }


def poll_wecom(uuid: str) -> dict:
    """轮询登录态：真实 `GetRunClientInfo`，失败降级 mock。"""
    mode = _mode()
    if mode == "real":
        info = get_run_client_info(uuid)
        return {
            "loginType": info.get("loginType", 1),
            "userInfo": info.get("userInfo"),
            "longLinkState": info.get("longLinkState", "CONNECTING"),
            "mock": False,
        }
    if mode == "auto":
        try:
            info = get_run_client_info(uuid)
            return {
                "loginType": info.get("loginType", 1),
                "userInfo": info.get("userInfo"),
                "longLinkState": info.get("longLinkState", "CONNECTING"),
                "mock": False,
            }
        except IPadProtocolError:
            pass
    return _mock_poll(uuid)


# ---------------------------------------------------------------------------
# iPad 协议：multipart 上传（P2-3 富媒体 CDN 上传，后端代理）
# ---------------------------------------------------------------------------
def _post_multipart(path: str, files: dict, data: dict | None = None) -> dict:
    """multipart 调用 iPad 协议服务（CDN 上传场景），失败抛 `IPadProtocolError`。"""
    url = f"{_base_url()}/{path.lstrip('/')}"
    try:
        resp = httpx.post(url, files=files, data=data or {}, timeout=10.0)
    except (httpx.HTTPError, OSError) as exc:
        raise IPadProtocolError(f"iPad 协议服务调用失败: {url} ({exc})")
    if resp.status_code != 200:
        raise IPadProtocolError(
            f"iPad 协议服务返回非 200: HTTP {resp.status_code} ({url})"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise IPadProtocolError("iPad 协议服务返回非 JSON 响应") from exc


# ---------------------------------------------------------------------------
# iPad 协议：渠道会话 + 客户管理（P1 标签 / 搜索添加 / 已读；P2 历史 / 富媒体 / 回调）
# 沿用 _post / _norm / _post_multipart / IPadProtocolError，不补 mock 分支（决策 #7）。
# ---------------------------------------------------------------------------
def get_label_list(uuid: str, index: int = 0, sync_type: int = 1) -> dict:
    """POST `{base}/wxwork/GetLabelListReq` → iPad 标签列表（游标 `index`）。

    返回 `{list, index}`，`list[]` 每项含
    `id`/`name`/`label_type`/`label_groupid`；`index` 为下一页游标（空表示末页）。
    `sync_type` 1=企业标签 2=个人标签。
    """
    data = _post(
        "wxwork/GetLabelListReq",
        {"uuid": uuid, "index": int(index), "sync_type": int(sync_type)},
    )
    body = _norm(data)
    return {
        "list": body.get("list") or body.get("labelList") or [],
        "index": int(body.get("index", 0) or 0),
    }


def user_add_labels(uuid: str, userid: str, labelid_list: list[str]) -> dict:
    """POST `{base}/wxwork/UserAddLabelsReq` → 给联系人增减标签（一个用户多个标签）。"""
    data = _post(
        "wxwork/UserAddLabelsReq",
        {"uuid": uuid, "userid": userid, "labelid_list": list(labelid_list)},
    )
    return _norm(data)


def search_contact(uuid: str, phoneNumber: str) -> dict:
    """POST `{base}/wxwork/SearchContact` → 搜索外部联系人（手机号/关键词）。

    返回 `{list, userList[]}`，`userList[]` 每项含
    `user_id`/`name`/`sex`/`headImg`/`ticket`/`openId`/`corp_id`/`state`。
    """
    data = _post("wxwork/SearchContact", {"uuid": uuid, "phoneNumber": phoneNumber})
    body = _norm(data)
    return {
        "list": body.get("list") or body.get("userList") or [],
        "userList": body.get("userList") or body.get("list") or [],
    }


def add_search(
    uuid: str,
    vid: str,
    openId: str,
    phone: str,
    content: str,
    ticket: str,
) -> dict:
    """POST `{base}/wxwork/AddSearch` → 发送好友申请（搜索添加外部联系人主路径）。"""
    data = _post(
        "wxwork/AddSearch",
        {
            "uuid": uuid,
            "vid": vid,
            "openId": openId,
            "phone": phone,
            "content": content,
            "ticket": ticket,
        },
    )
    return _norm(data)


def add_wx_user(uuid: str, vid: str, content: str) -> dict:
    """POST `{base}/wxwork/AddWxUser` → 直接添加（仅限曾被删除过的场景，兜底路径）。"""
    data = _post("wxwork/AddWxUser", {"uuid": uuid, "vid": vid, "content": content})
    return _norm(data)


def agree_user(uuid: str, corpid: str, vid: str) -> dict:
    """POST `{base}/wxwork/AgreeUser` → 同意添加（vid 来自回调）。

    前端一般不直调，由回调链路在收到「对方通过申请」事件时调用。
    """
    data = _post("wxwork/AgreeUser", {"uuid": uuid, "corpid": corpid, "vid": vid})
    return _norm(data)


def get_group_msg_list(uuid: str) -> dict:
    """POST `{base}/wxwork/GetGroupMsgList` → 群消息历史（文档示例仅 `{uuid}`）。

    返回 `{list, listdata[]}`，`listdata[]` 每项含 `id`/`seq`/`content[]`/`file_id`/
    `aes_key` 等多类型；由同步服务解析后落 `messages`（决策 #2：room 参数待联调确认）。
    """
    data = _post("wxwork/GetGroupMsgList", {"uuid": uuid})
    body = _norm(data)
    return {
        "list": body.get("list") or body.get("listdata") or [],
        "listdata": body.get("listdata") or body.get("list") or [],
    }


def sync_all_data(uuid: str, limit: int = 100, seq: int = 0) -> dict:
    """POST `{base}/wxwork/SyncAllData` → 触发离线消息回填。

    返回提示「消息已分发到消息回填事件，请在回调中处理」——实际 1:1 历史经
    `SetCallbackUrl` 注册的回调推送，非 HTTP 直接返回（P2-1 与 P2-4 强耦合）。
    `seq` 为最后 `server_id`（游标）。
    """
    data = _post(
        "wxwork/SyncAllData",
        {"uuid": uuid, "limit": int(limit), "seq": int(seq)},
    )
    return _norm(data)


def mark_as_read(uuid: str, send_userid: str, isRoom: bool) -> dict:
    """POST `{base}/wxwork/MarkAsRead` → 已读回执（清除 iPad 侧未读小红点）。

    `send_userid` 群聊传群 id、1:1 传用户 id；`isRoom` 标识群。
    返回含 `server_id`（已读回执消息 id）。
    """
    data = _post(
        "wxwork/MarkAsRead",
        {"uuid": uuid, "send_userid": send_userid, "isRoom": bool(isRoom)},
    )
    body = _norm(data)
    return {
        "server_id": body.get("server_id") or body.get("serverId") or "",
        "ok": bool(body.get("ok", True)),
    }


# ---------------------------------------------------------------------------
# 群操作系列（协议文档 2026-07-23）
# 全部走 _post + _norm，失败抛 IPadProtocolError；由 ipad_sync 服务层按模式
# auto/real/mock 降级处理。
#
# roomid 在协议中为整数，客户端统一 str 化传出。
# vid / vids（user_id）在协议中为整数，客户端按入参类型逐项 int 化。
# ---------------------------------------------------------------------------
def _to_int_id(val: Any) -> int:
    """将 user_id 转为协议期望的整数。"""
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


# ---- 创建群聊（对接真实协���） ----
def create_room_nei(uuid: str, vids: list[Any], room_name: str = "") -> dict:
    """创建内部群聊 POST wxwork/CreateRoomNei。"""
    data = _post(
        "wxwork/CreateRoomNei",
        {"uuid": uuid, "vids": [_to_int_id(v) for v in vids], "roomName": room_name},
    )
    body = _norm(data)
    return {
        "room_id": str(body.get("roomid") or body.get("room_id") or ""),
        "room_name": body.get("roomname") or room_name,
        "ok": True,
        "mock": False,
    }


def create_room_wx(uuid: str, vids: list[Any], room_name: str = "") -> dict:
    """创建外部群聊 POST wxwork/CreateRoomWx。"""
    data = _post(
        "wxwork/CreateRoomWx",
        {"uuid": uuid, "vids": [_to_int_id(v) for v in vids], "roomName": room_name},
    )
    body = _norm(data)
    return {
        "room_id": str(body.get("roomid") or body.get("room_id") or ""),
        "room_name": body.get("roomname") or room_name,
        "ok": True,
        "mock": False,
    }


def create_chatroom(uuid: str, wxids: list[str], room_name: str = "", is_inner: bool = False) -> dict:
    """
    建群（带 auto/real/mock 降级，兼容旧调用方）。
    内部群走 CreateRoomNei，外部群走 CreateRoomWx。
    """
    fn = create_room_nei if is_inner else create_room_wx
    mode = _mode()
    if mode == "real":
        return fn(uuid, wxids, room_name)
    if mode == "auto":
        try:
            return fn(uuid, wxids, room_name)
        except IPadProtocolError as exc:
            logger.warning("建群真实失败，降级 mock: %s", exc)
    import secrets
    return {
        "room_id": f"mock_room_{secrets.token_hex(4)}",
        "room_name": room_name,
        "ok": True,
        "mock": True,
    }


# ---- 群公告 ----
def send_notice(uuid: str, room_id: Any, msg: str) -> dict:
    """发送群公告 POST wxwork/SendNotice。"""
    data = _post(
        "wxwork/SendNotice",
        {"uuid": uuid, "roomid": _to_int_id(room_id), "msg": msg},
    )
    _norm(data)
    return {"ok": True, "room_id": str(room_id)}


# ---- 修改群名 ----
def update_room_name(uuid: str, room_id: Any, room_name: str) -> dict:
    """修改群名 POST wxwork/UpdateRoomName。"""
    data = _post(
        "wxwork/UpdateRoomName",
        {"uuid": uuid, "roomid": _to_int_id(room_id), "roomname": room_name},
    )
    body = _norm(data)
    return {"room_id": str(body.get("roomid") or room_id), "room_name": room_name, "ok": True}


# ---- 直接邀请进群 ----
def invitation_to_room(uuid: str, room_id: Any, vids: list[Any]) -> dict:
    """直接邀请进群 POST wxwork/InvitationToRoom。"""
    data = _post(
        "wxwork/InvitationToRoom",
        {"uuid": uuid, "roomid": _to_int_id(room_id), "vids": [_to_int_id(v) for v in vids]},
    )
    _norm(data)
    return {"ok": True, "room_id": str(room_id), "added": len(vids)}


# ---- 移除群成员 ----
def del_room_users(uuid: str, room_id: Any, vids: list[Any]) -> dict:
    """移除群成员 POST wxwork/DelRoomUsers。"""
    data = _post(
        "wxwork/DelRoomUsers",
        {"uuid": uuid, "roomid": _to_int_id(room_id), "vids": [_to_int_id(v) for v in vids]},
    )
    _norm(data)
    return {"ok": True, "room_id": str(room_id), "removed": len(vids)}


# ---- 转让群主 ----
def transfer_chatroom_owner(uuid: str, room_id: Any, vid: Any) -> dict:
    """转让群主 POST wxwork/TransferChatroomOwner。"""
    data = _post(
        "wxwork/TransferChatroomOwner",
        {"uuid": uuid, "roomid": _to_int_id(room_id), "vid": _to_int_id(vid)},
    )
    _norm(data)
    return {"ok": True, "room_id": str(room_id), "new_owner_vid": str(vid)}


# ---- 解散群 ----
def dissolution_room(uuid: str, room_id: Any) -> dict:
    """解散群 POST wxwork/DissolutionRoom。"""
    data = _post(
        "wxwork/DissolutionRoom",
        {"uuid": uuid, "roomid": _to_int_id(room_id)},
    )
    _norm(data)
    return {"ok": True, "room_id": str(room_id)}


# ---- 获取群二维码 ----
def wx_room_invite(uuid: str, room_id: Any) -> dict:
    """获取群二维码 POST wxwork/WxRoomInvite。"""
    data = _post(
        "wxwork/WxRoomInvite",
        {"uuid": uuid, "roomid": _to_int_id(room_id)},
    )
    body = _norm(data)
    return {
        "room_id": str(body.get("roomid") or room_id),
        "qr_code_path": body.get("QrCodePath") or body.get("qr_code_path") or "",
    }


# ---- 媒体上传辅助 ----
def cdn_upload_img(file_bytes: bytes, file_name: str, uuid: str) -> dict:
    """POST `{base}/wxwork/CdnUploadImg`（multipart） → 图片 CDN 上传。

    返回 `cdn_key`/`aes_key`/`md5`/`width`/`height`/`size`。
    """
    files = {"file": (file_name or "image.png", file_bytes, "application/octet-stream")}
    data = _post_multipart("wxwork/CdnUploadImg", files=files, data={"uuid": uuid})
    body = _norm(data)
    return {
        "cdn_key": body.get("cdn_key") or body.get("cdnKey") or "",
        "aes_key": body.get("aes_key") or body.get("aesKey") or "",
        "md5": body.get("md5") or "",
        "width": int(body.get("width", 0) or 0),
        "height": int(body.get("height", 0) or 0),
        "size": int(body.get("size", 0) or 0),
    }


def cdn_upload_file(file_bytes: bytes, file_name: str, uuid: str) -> dict:
    """POST `{base}/wxwork/CdnUploadFile`（multipart） → 文件 CDN 上传。

    返回 `aes_key`/`fileid`/`md5`/`size`（`fileid` 作为 `SendCDNFileMsg` 的 `cdnKey`）。
    """
    files = {"file": (file_name or "file.bin", file_bytes, "application/octet-stream")}
    data = _post_multipart("wxwork/CdnUploadFile", files=files, data={"uuid": uuid})
    body = _norm(data)
    return {
        "aes_key": body.get("aes_key") or body.get("aesKey") or "",
        "fileid": body.get("fileid") or body.get("fileId") or "",
        "md5": body.get("md5") or "",
        "size": int(body.get("size", 0) or 0),
    }


def send_cdn_img_msg(
    uuid: str,
    send_userid: str,
    isRoom: bool,
    cdnkey: str,
    aeskey: str,
    md5: str,
    fileSize: int,
    width: int = 0,
    height: int = 0,
) -> dict:
    """POST `{base}/wxwork/SendCDNImgMsg` → 发送 CDN 图片消息。

    返回含 `server_id`/`msg_id`（发送回执，用于乐观追加气泡与去重）。
    """
    payload = {
        "uuid": uuid,
        "send_userid": send_userid,
        "isRoom": bool(isRoom),
        "cdnkey": cdnkey,
        "aeskey": aeskey,
        "md5": md5,
        "fileSize": int(fileSize),
        "width": int(width),
        "height": int(height),
    }
    data = _post("wxwork/SendCDNImgMsg", payload)
    body = _norm(data)
    return {
        "server_id": body.get("server_id") or body.get("serverId") or "",
        "msg_id": body.get("msg_id") or body.get("msgId") or "",
        "ok": True,
    }


def send_cdn_file_msg(
    uuid: str,
    send_userid: str,
    isRoom: bool,
    cdnKey: str,
    aesKey: str,
    md5: str,
    file_name: str,
    fileSize: int,
) -> dict:
    """POST `{base}/wxwork/SendCDNFileMsg` → 发送 CDN 文件消息。

    `cdnKey` 取 `CdnUploadFile` 返回的 `fileid`（PRD §5 #4 工程映射）。
    返回含 `server_id`/`msg_id`（发送回执）。
    """
    payload = {
        "uuid": uuid,
        "send_userid": send_userid,
        "isRoom": bool(isRoom),
        "cdnKey": cdnKey,
        "aesKey": aesKey,
        "md5": md5,
        "file_name": file_name,
        "fileSize": int(fileSize),
    }
    data = _post("wxwork/SendCDNFileMsg", payload)
    body = _norm(data)
    return {
        "server_id": body.get("server_id") or body.get("serverId") or "",
        "msg_id": body.get("msg_id") or body.get("msgId") or "",
        "ok": True,
    }


def set_callback_url(uuid: str, url: str, callbackType: str = "HTTP") -> dict:
    """POST `{base}/wxwork/SetCallbackUrl` → 注册实时回调地址（P2-4）。

    `callbackType` HTTP（默认）| RABBITMQ。注册成功后 iPad 服务将新消息
    POST 推送到 `url`（Morphix 公网可达端点 `/wxwork/callback`）。
    """
    data = _post(
        "wxwork/SetCallbackUrl",
        {"uuid": uuid, "url": url, "callbackType": callbackType},
    )
    return _norm(data)


# ---------------------------------------------------------------------------
# 企业应用 / vid 身份解析（wecom_app_display T01）
#
# 沿用 _post + _norm，**不修改 `_post`**、**不补 mock 分支**（架构文档 §8.4）；
# 失败一律抛 `IPadProtocolError`，由 `ipad_sync` 分路 try/except 降级。
#
# ⚠️ 精度约定（架构文档 §8.2）：`appId` / `appOpenId` / `corpid` / `vid` 在协议
# 中均为 Long（最长 17 位，如 13102694783555467 已超 JS
# Number.MAX_SAFE_INTEGER = 9007199254740991）。解析后**立即 str() 化**，
# DB / DTO / TS 全链路以字符串传递，避免前端 JSON 反序列化静默丢精度。
# 唯一例外是 `GetUserInfoByVids` 的**请求体** vids 必须是整型数组，
# 该转换只在本模块内部完成，不外泄。
# ---------------------------------------------------------------------------
# `GetUserInfoByVids` 单批 vid 上限（协议约定，架构文档 §8.4）。
VIDS_BATCH_LIMIT = 100


def _id_str(val: Any) -> str:
    """把协议 Long 型 ID 归一化为字符串；None / 空 / 非法 → 空串。"""
    if val is None or isinstance(val, bool):
        return ""
    if isinstance(val, float):
        # 少数 JSON 实现会把 Long 反序列化成 float，取整避免出现 "1.3e+16"
        try:
            return str(int(val))
        except (OverflowError, ValueError):
            return ""
    text = str(val).strip()
    return "" if text.lower() in ("none", "null", "nan") else text


def _safe_int(val: Any, default: int = 0) -> int:
    """宽松 int 转换：失败返回 `default`（协议字段可能是 str/None）。"""
    if val is None or isinstance(val, bool):
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return default


# 应用条目中已被显式映射的字段；其余原样进 `extra`（不丢信息）。
_WX_APP_KNOWN_KEYS = frozenset(
    {
        "appId", "app_id", "appOpenId", "app_open_id",
        "corpid", "corpId", "corp_id",
        "name", "imgId", "img_id", "logo",
        "appType", "app_type",
        "desc", "description",
        "homeInfo", "home_info",
        "lastModTime", "last_mod_time",
    }
)


def _norm_wx_app(item: dict) -> dict:
    """归一化单个应用条目，键名与 `channel_apps` 列语义一一对齐。

    Args:
        item: `wxAppList[]` 中的原始条目。

    Returns:
        dict: `{appId, appOpenId, corpid, name, avatar, appType, description,
        homeInfo, lastModTime, extra}`；所有 ID 均为 `str`。
        `imgId` 刻意映射为 `avatar`、`desc` 刻意映射为 `description`
        （`desc` 是 SQL 保留字，见架构文档 §3.1 字段映射表）。
    """
    if not isinstance(item, dict):
        return {}
    extra = {k: v for k, v in item.items() if k not in _WX_APP_KNOWN_KEYS}
    # extra 中可能仍含 Long ID（groupId / businessId），一并字符串化
    for long_key in ("groupId", "businessId", "group_id", "business_id"):
        if long_key in extra:
            extra[long_key] = _id_str(extra[long_key])
    return {
        "appId": _id_str(item.get("appId") if item.get("appId") is not None else item.get("app_id")),
        "appOpenId": _id_str(
            item.get("appOpenId") if item.get("appOpenId") is not None else item.get("app_open_id")
        ),
        "corpid": _id_str(item.get("corpid") or item.get("corpId") or item.get("corp_id")),
        "name": str(item.get("name") or ""),
        "avatar": str(item.get("imgId") or item.get("img_id") or item.get("logo") or ""),
        "appType": _safe_int(item.get("appType") if item.get("appType") is not None else item.get("app_type")),
        "description": str(item.get("desc") or item.get("description") or ""),
        "homeInfo": str(item.get("homeInfo") or item.get("home_info") or ""),
        "lastModTime": _safe_int(
            item.get("lastModTime") if item.get("lastModTime") is not None else item.get("last_mod_time")
        ),
        "extra": extra,
    }


def get_corp_wx_app(uuid: str) -> list[dict]:
    """POST `{base}/wxwork/getCorpWxApp` → 企业应用（微信应用）列表。

    协议返回 `{"data": {"wxAppList": [...]}, "errcode": 0}`，条目字段含
    `appId` / `appOpenId` / `corpid` / `name` / `imgId` / `appType` /
    `desc` / `homeInfo` / `lastModTime` 等。

    Args:
        uuid: iPad 协议实例 uuid。

    Returns:
        list[dict]: 归一化后的应用列表（见 `_norm_wx_app`）；
        `appId` 与 `appOpenId` 均为空的脏条目会被丢弃。

    Raises:
        IPadProtocolError: 服务不可达 / 非 200 / 非 JSON / errcode 非 0。
            ⚠️ 生产实例 `47.94.7.218:9912` 当前对该路径返回 **HTTP 404**
            （协议服务版本缺口，见架构文档 §9-U1），因此本函数抛异常
            **是当前的预期行为**；调用方（`ipad_sync._sync_corp_apps`）
            必须捕获并降级，不得阻断其余同步路。
    """
    data = _post("wxwork/getCorpWxApp", {"uuid": uuid})
    body = _norm(data)
    raw_list = (
        body.get("wxAppList")
        or body.get("wx_app_list")
        or body.get("appList")
        or body.get("list")
        or []
    )
    if not isinstance(raw_list, list):
        return []
    apps: list[dict] = []
    for item in raw_list:
        normalized = _norm_wx_app(item)
        # 双键至少有一个非空才可作为自然键落库（架构文档 §3.1）
        if normalized and (normalized.get("appId") or normalized.get("appOpenId")):
            apps.append(normalized)
    return apps


def _norm_vid_user(item: dict) -> dict:
    """归一化 `GetUserInfoByVids` 单条身份，键名与 `channel_contacts` 对齐。"""
    if not isinstance(item, dict):
        return {}
    user_id = _id_str(
        item.get("user_id")
        if item.get("user_id") is not None
        else (item.get("userId") if item.get("userId") is not None else item.get("vid"))
    )
    name = str(item.get("name") or item.get("realname") or item.get("realName") or "")
    nickname = str(item.get("nickname") or item.get("nickName") or "") or name
    return {
        "user_id": user_id,
        "name": name or nickname,
        "nickname": nickname,
        "avatar": str(
            item.get("avatar") or item.get("headUrl") or item.get("head_url") or item.get("imgUrl") or ""
        ),
        "corpid": _id_str(item.get("corpid") or item.get("corpId") or item.get("corp_id")),
        "acctid": _id_str(item.get("acctid") or item.get("acctId") or item.get("acct_id")),
        "raw": item,
    }


def get_user_info_by_vids(uuid: str, vids: list[str]) -> list[dict]:
    """POST `{base}/wxwork/GetUserInfoByVids` → 按 vid 批量解析身份。

    对拍验证（架构文档 §1.2）：
    - 请求体 `vids` **必须是整型数组**，传字符串数组服务端不识别；
    - 响应体 `data` 是**顶层 list**，不是 `{"list": [...]}`；
    - 未命中的 vid 不会出现在返回中（请求 16 个可能只回 2 个）。

    Args:
        uuid: iPad 协议实例 uuid。
        vids: 待解析的 vid 列表（字符串；内部按 `VIDS_BATCH_LIMIT` 分批）。

    Returns:
        list[dict]: 命中的身份列表，每项含
        `{user_id, name, nickname, avatar, corpid, acctid, raw}`，
        `user_id` 为字符串。未命中的 vid 不在返回中。

    Raises:
        IPadProtocolError: 服务不可达 / 非 200 / errcode 非 0（任一批次失败
            即向上抛，由 `ipad_sync._backfill_unknown_vids` 捕获降级）。
    """
    # 去重 + 过滤非数字（协议 vid 恒为数字串），保持入参顺序
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_vid in vids or []:
        text = _id_str(raw_vid)
        if not text or not text.isdigit() or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    if not cleaned:
        return []

    results: list[dict] = []
    for start in range(0, len(cleaned), VIDS_BATCH_LIMIT):
        batch = cleaned[start : start + VIDS_BATCH_LIMIT]
        data = _post(
            "wxwork/GetUserInfoByVids",
            {"uuid": uuid, "vids": [int(v) for v in batch]},
        )
        # data 形如 {"data": [...], "errcode": 0}；_norm 只处理 dict 信封，
        # 这里的 data 是 list，需单独取。
        payload = data.get("data") if isinstance(data, dict) else None
        if isinstance(payload, dict):
            payload = payload.get("list") or payload.get("userList") or payload.get("user_list") or []
        if not isinstance(payload, list):
            payload = []
        for item in payload:
            normalized = _norm_vid_user(item)
            if normalized.get("user_id"):
                results.append(normalized)
    return results
