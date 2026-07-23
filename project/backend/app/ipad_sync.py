"""iPad 协议同步服务层（T02）。

职责（分层：Router → Service(本模块) → Client(ipad_client) → Repository）：
- `run_full_sync(account_id)`：四路游标分页拉取（内部/外部联系人、群、会话），
  去重 upsert 到 channel_contacts / customer_profiles / channel_groups / channel_sessions；
  单账号串行互斥（进程内 `_sync_active` 标志 + 守护线程）；单次同步 5000 条上限保护；
  同步状态写入 `channel_accounts.sync_status` / `last_sync_at`。
- `send_text_message(...)`：后端反查 `user_id` / `room_id` + `isRoom`，调用协议发送；
  应用类会话（msg_type==3）抛 `IPadSyncError`（路由转 400）；协议失败抛
  `IPadProtocolError`（路由转 502 / 降级）。
- `trigger_sync(account_id)` / `get_sync_status(account_id)`：手动/自动触发入口与状态查询。

降级约定（见 docs/ipad-sync-design.md 共享知识 #2/#7）：
- 同步任务捕获 `IPadProtocolError`：auto 模式标记 `degraded` 不崩、不补 mock；
  real 模式标记 `error`。均不向外抛出未捕获异常（守护线程内兜底记录日志）。
- 新协议函数**不**含 mock 分支（决策 #7）。
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any

from . import ipad_client
from .config import settings
from .database import get_backend
from .repositories import ChannelMgmtRepository

logger = logging.getLogger(__name__)

# 单账号同步串行互斥：进程内标志（守护线程模型，重启后失效，可接受）。
_sync_guard = threading.Lock()
_sync_active: dict[str, bool] = {}

# 单账号单次同步累计上限（决策 #4）。
SYNC_TOTAL_CAP = 5000

# msg_type 映射（0 好友 / 1 群聊 / 3 应用 / 6 开放平台）。
_MSG_TYPE_LABEL = {0: "好友", 1: "群聊", 3: "应用", 6: "开放平台"}


class IPadSyncError(ValueError):
    """同步/发送的目标解析或参数错误（路由层转 400）。"""


def _now() -> str:
    """当前时间（秒级 ISO，与前端 createdAt 格式对齐）。"""
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 互斥与触发编排
# ---------------------------------------------------------------------------
def _begin_sync(account_id: str) -> bool:
    """原子地标记账号同步进行中；已进行中返回 False。"""
    with _sync_guard:
        if _sync_active.get(account_id):
            return False
        _sync_active[account_id] = True
        return True


def _end_sync(account_id: str) -> None:
    with _sync_guard:
        _sync_active.pop(account_id, None)


def trigger_sync(account_id: str) -> bool:
    """触发后台全量同步（守护线程，不阻塞调用方）。

    返回 True 表示已启动；False 表示该账号正在同步中（调用方可据此返 409）。
    """
    if not _begin_sync(account_id):
        return False
    t = threading.Thread(target=_run_worker, args=(account_id,), daemon=True)
    t.start()
    return True


def _run_worker(account_id: str) -> None:
    """后台工作线程：执行同步并兜底异常处理，结束后清除互斥标志。"""
    try:
        run_full_sync(account_id)
    except Exception:  # noqa: BLE001 - 守护线程内绝不允许异常外泄
        logger.exception("iPad 全量同步异常 account=%s", account_id)
        try:
            ChannelMgmtRepository(get_backend()).set_account_sync_status(
                account_id, "error", _now()
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        _end_sync(account_id)


def get_sync_status(account_id: str) -> dict | None:
    """查询账号同步状态（含进程内进行中标志）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if account is None:
        return None
    with _sync_guard:
        syncing = _sync_active.get(account_id, False)
    return {
        "accountId": account_id,
        "syncStatus": account.get("syncStatus", ""),
        "lastSyncAt": account.get("lastSyncAt", ""),
        "syncing": bool(syncing),
    }


# ---------------------------------------------------------------------------
# 群聊 / 已读（T04 UI 改造新增）
# ---------------------------------------------------------------------------
def create_group(account_id: str, member_ids: list[str], room_name: str = "") -> dict:
    """创建群聊：解析联系人 user_id → 调 iPad 建群 → 落库 → 返回 GroupDTO。

    mock-first：真实协议失败或 mock 模式均本地生成 room_id 并落库，前端不阻塞。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    uuid = account.get("ipadUuid", "")
    if not uuid:
        raise IPadSyncError("账号未托管 iPad")
    if not member_ids:
        raise IPadSyncError("至少选择一位好友")

    channel = account.get("channel", "企业微信")
    channel_type = account.get("channel_type", "wecom")

    wxids: list[str] = []
    nicknames: list[str] = []
    for cid in member_ids:
        contact = repo.get_contact_by_id(cid)
        if not contact:
            continue
        user_id = str(contact.get("user_id") or "")
        if user_id:
            wxids.append(user_id)
            nicknames.append(str(contact.get("nickname") or contact.get("name") or "未知"))
    if len(wxids) < 1:
        raise IPadSyncError("未能解析到有效的好友 user_id")

    room_name = room_name or (
        "、".join(nicknames[:3]) + (" 等" if len(nicknames) > 3 else "") + " 的群聊"
    )

    result = ipad_client.create_chatroom(uuid, wxids, room_name)
    room_id = str(result.get("room_id") or "")
    if not room_id:
        raise IPadSyncError("iPad 建群返回 room_id 为空")

    gid = f"{account_id}:{room_id}"
    now = _now()
    repo.upsert_channel_group(
        {
            "id": gid,
            "account_id": account_id,
            "room_id": room_id,
            "group_type": "customer_group",
            "nickname": room_name,
            "total": len(wxids),
            "room_url": "",
            "notice_content": "",
            "create_time": now,
            "update_time": now,
            "extra_json": "{}",
        }
    )
    # 同时写一条 channel_sessions，支撑「直接点击聊天」
    repo.create_session_for_room(account_id, room_id, room_name, channel, channel_type)
    return repo.get_group_by_room_id(account_id, room_id)


# ---------------------------------------------------------------------------
# 群成员管理 / 群公告 / 转让群主 / 解散群（mock-first，T04）
# ---------------------------------------------------------------------------
def _resolve_group(account_id: str, room_id: str) -> dict:
    """按 (account_id, room_id) 查群，不存在抛 IPadSyncError。"""
    repo = ChannelMgmtRepository(get_backend())
    g = repo.get_group_by_room_id(account_id, room_id)
    if not g:
        raise IPadSyncError("群不存在")
    return g


def add_group_members(
    account_id: str, room_id: str, member_ids: list[str]
) -> dict:
    """添加群成员：先调真实协议 InvitationToRoom，成功后再落库。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    g = _resolve_group(account_id, room_id)
    if not member_ids:
        raise IPadSyncError("成员列表为空")
    uuid = account.get("ipadUuid", "")

    wxids: list[str] = []
    for cid in member_ids:
        contact = repo.get_contact_by_id(cid)
        if not contact:
            continue
        user_id = str(contact.get("user_id") or "")
        if user_id:
            wxids.append(user_id)
    if not wxids:
        raise IPadSyncError("未能解析到有效的好友 user_id")

    # 先调真实协议邀请进群（auto 模式降级不影响落库）
    if uuid:
        try:
            ipad_client.invitation_to_room(uuid, room_id, wxids)
        except ipad_client.IPadProtocolError as exc:
            logger.warning("InvitationToRoom 失败: %s, 继续落库", exc)

    added = 0
    for cid in member_ids:
        contact = repo.get_contact_by_id(cid)
        if not contact:
            continue
        uin = str(contact.get("user_id") or "")
        mid = f"{g['id']}:{uin or contact.get('nickname', '')}"
        repo.upsert_channel_group_member(
            {
                "id": mid,
                "group_id": g["id"],
                "uin": uin,
                "user_id": uin,
                "nickname": str(contact.get("nickname") or contact.get("name") or ""),
                "realname": str(contact.get("name") or ""),
                "avatar": str(contact.get("avatar") or ""),
                "room_nickname": "",
                "sex": 0,
                "mobile": "",
                "join_time": _now(),
            }
        )
        added += 1
    new_total = repo.count_group_members(g["id"])
    repo.upsert_channel_group(_group_dto_to_row(g, total=new_total))
    return {"added": added, "groupId": g["id"], "total": new_total}


def remove_group_member(
    account_id: str, room_id: str, member_id: str
) -> dict:
    """移除群成员：先调真实协议 DelRoomUsers，成功后再从本地删。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    g = _resolve_group(account_id, room_id)
    contact = repo.get_contact_by_id(member_id)
    uin = str(contact.get("user_id") or "") if contact else str(member_id)

    uuid = account.get("ipadUuid", "")
    if uuid and uin:
        try:
            ipad_client.del_room_users(uuid, room_id, [uin])
        except ipad_client.IPadProtocolError as exc:
            logger.warning("DelRoomUsers 失败: %s, 继续本地删", exc)

    deleted = repo.delete_channel_group_member(g["id"], uin)
    new_total = repo.count_group_members(g["id"])
    repo.upsert_channel_group(_group_dto_to_row(g, total=new_total))
    return {"deleted": deleted, "groupId": g["id"], "total": new_total}


def set_group_notice(account_id: str, room_id: str, notice: str) -> dict:
    """更新群公告：先调真实协议 SendNotice，成功后再落库。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    g = _resolve_group(account_id, room_id)

    uuid = account.get("ipadUuid", "")
    if uuid:
        try:
            ipad_client.send_notice(uuid, room_id, notice)
        except ipad_client.IPadProtocolError as exc:
            logger.warning("SendNotice 失败: %s, 继续落库", exc)

    repo.upsert_channel_group(_group_dto_to_row(g, notice_content=notice))
    return {"groupId": g["id"], "noticeContent": notice}


def transfer_group_owner(
    account_id: str, room_id: str, new_owner_user_id: str
) -> dict:
    """转让群主：先调真实协议 TransferChatroomOwner，成功后再落库。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    g = _resolve_group(account_id, room_id)

    uuid = account.get("ipadUuid", "")
    if uuid:
        try:
            ipad_client.transfer_chatroom_owner(uuid, room_id, new_owner_user_id)
        except ipad_client.IPadProtocolError as exc:
            logger.warning("TransferChatroomOwner 失败: %s, 继续落库", exc)

    import json as _json
    extra = g.get("extra") or {}
    if not isinstance(extra, dict):
        try:
            extra = _json.loads(extra)
        except Exception:
            extra = {}
    extra["ownerUserId"] = new_owner_user_id
    repo.upsert_channel_group(
        _group_dto_to_row(g, extra_json=_json.dumps(extra, ensure_ascii=False))
    )
    return {"groupId": g["id"], "ownerUserId": new_owner_user_id}


def _group_dto_to_row(g: dict, **overrides) -> dict:
    """将 row_to_group 返回的 camelCase DTO 转为 upsert_channel_group 期望的 snake_case 行。"""
    import json as _json
    extra = g.get("extra")
    if isinstance(extra, dict):
        extra_json = _json.dumps(extra, ensure_ascii=False)
    elif isinstance(extra, str):
        extra_json = extra
    else:
        extra_json = "{}"
    row = {
        "id": g["id"],
        "account_id": g["accountId"],
        "room_id": g["roomId"],
        "group_type": g.get("groupType", "customer_group"),
        "nickname": g.get("name", ""),
        "total": int(g.get("total", 0)),
        "room_url": g.get("roomUrl", ""),
        "notice_content": g.get("noticeContent", ""),
        "create_time": g.get("createTime", ""),
        "update_time": g.get("updateTime", ""),
        "extra_json": extra_json,
    }
    # snake_case 覆盖优先
    key_map = {
        "noticeContent": "notice_content",
        "createTime": "create_time",
        "updateTime": "update_time",
        "roomUrl": "room_url",
        "groupType": "group_type",
    }
    for k, v in overrides.items():
        snake = key_map.get(k, k)
        row[snake] = v
    return row


def dismiss_group(account_id: str, room_id: str) -> dict:
    """解散群：先调真实协议 DissolutionRoom，成功后再从本地删。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    g = _resolve_group(account_id, room_id)

    uuid = account.get("ipadUuid", "")
    if uuid:
        try:
            ipad_client.dissolution_room(uuid, room_id)
        except ipad_client.IPadProtocolError as exc:
            logger.warning("DissolutionRoom 失败: %s, 继续本地删", exc)

    repo.delete_all_channel_group_members(g["id"])
    repo.delete_session_for_room(account_id, room_id)
    repo.delete_channel_group(g["id"])
    return {"dismissed": True, "groupId": g["id"]}


def mark_sessions_read_local(
    account_id: str, session_ids: list[str] | None = None
) -> dict:
    """仅本地清零未读（不调用 iPad mark_as_read），返回更新行数。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    updated = repo.mark_sessions_read_local(account_id, session_ids)
    return {"updated": updated}


# ---------------------------------------------------------------------------
# 全量同步核心
# ---------------------------------------------------------------------------
def run_full_sync(account_id: str) -> dict:
    """执行一次全量同步（四路拉取 + 游标分页 + 5000 上限 + 状态写入）。

    返回 `{"counts": {...}, "degraded": bool, "error": str|None, "total": int}`。
    互斥由调用方（trigger_sync / 自动触发）保证；本函数只做业务编排。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        return {
            "counts": {},
            "degraded": False,
            "error": "账号不存在或未托管 iPad",
            "total": 0,
            "skipped": True,
        }
    uuid: str = account["ipadUuid"]
    channel: str = account.get("channel", "企业微信")
    channel_type: str = account.get("channelType", "wecom")

    counts: dict[str, int] = {"inner": 0, "external": 0, "groups": 0, "sessions": 0}
    total = 0
    repo.set_account_sync_status(account_id, "syncing", _now())

    try:
        # 1) 内部联系人（游标 strSeq）
        str_seq = ""
        while total < SYNC_TOTAL_CAP:
            res = ipad_client.get_inner_contacts(uuid, str_seq, 100)
            lst = res["list"]
            if not lst:
                break
            for item in lst:
                # 决策 #9：is_department=1 的部门节点不落库
                # 真实协议字段大小写不一致（is_Department / is_department），两者都判定。
                if _is_department_node(item):
                    continue
                _upsert_inner_contact(repo, account_id, channel, channel_type, item)
                counts["inner"] += 1
                total += 1
                if total >= SYNC_TOTAL_CAP:
                    break
            if len(lst) < 100:
                break
            nxt = res.get("strSeq", "")
            if not nxt:
                break
            str_seq = nxt

        # 2) 外部联系人 / 客户（游标 seq）
        seq = 0
        while total < SYNC_TOTAL_CAP:
            res = ipad_client.get_external_contacts(uuid, seq, 100)
            lst = res["list"]
            if not lst:
                break
            for item in lst:
                _upsert_external_contact(repo, account_id, channel, channel_type, item)
                counts["external"] += 1
                total += 1
                if total >= SYNC_TOTAL_CAP:
                    break
            if len(lst) < 100:
                break
            nxt = int(res.get("seq", 0) or 0)
            if not nxt:
                break
            seq = nxt

        # 3) 客户群：以 GetSessionRoomList（会话列表中的群聊）为「主数据源」，
        #    GetChatroomMembers（客户群）作为「兜底/补充」。
        #    真实 iPad 服务对该账号 GetChatroomMembers 返回 0 条，而 GetSessionRoomList
        #    返回真实群数据（如「教育培训部」「医林通早会群」）。
        #    两来源以 room_id 为键去重（同一账号内），避免重复落库（决策 #10）。
        seen_room_ids: set[str] = set()

        # 3.1 主来源：会话列表中的群聊（GetSessionRoomList）
        star = 0
        while total < SYNC_TOTAL_CAP:
            res = ipad_client.get_session_room_list(uuid, star, 100)
            lst = res["room_list"]
            if not lst:
                break
            for item in lst:
                room_id = str(item.get("room_id") or item.get("roomId") or "")
                if not room_id or room_id in seen_room_ids:
                    continue
                seen_room_ids.add(room_id)
                _upsert_group(repo, account_id, item)
                counts["groups"] += 1
                total += 1
                if total >= SYNC_TOTAL_CAP:
                    break
            if len(lst) < 100:
                break
            nxt = int(res.get("star_index", 0) or 0)
            if not nxt:
                break
            star = nxt

        # 3.2 兜底/补充来源：客户群（GetChatroomMembers，可能为空）
        star = 0
        while total < SYNC_TOTAL_CAP:
            res = ipad_client.get_chatroom_members(uuid, star, 100)
            lst = res["room_list"]
            if not lst:
                break
            for item in lst:
                room_id = str(item.get("room_id") or item.get("roomId") or "")
                if not room_id or room_id in seen_room_ids:
                    continue
                seen_room_ids.add(room_id)
                _upsert_group(repo, account_id, item)
                counts["groups"] += 1
                total += 1
                if total >= SYNC_TOTAL_CAP:
                    break
            if len(lst) < 100:
                break
            nxt = int(res.get("star_index", 0) or 0)
            if not nxt:
                break
            star = nxt

        # 4) 会话（游标 star_index，依赖 contact/group 名称，放最后）
        star = 0
        while total < SYNC_TOTAL_CAP:
            res = ipad_client.get_session_list(uuid, star, 100)
            lst = res["room_list"]
            if not lst:
                break
            for item in lst:
                _upsert_session(repo, account_id, channel, channel_type, item)
                counts["sessions"] += 1
                total += 1
                if total >= SYNC_TOTAL_CAP:
                    break
            if len(lst) < 100:
                break
            nxt = int(res.get("star_index", 0) or 0)
            if not nxt:
                break
            star = nxt

    except ipad_client.IPadProtocolError as exc:
        mode = (settings.ipad_protocol_mode or "auto").lower()
        # 决策 #7：auto 降级不崩；real 标记 error（由状态呈现）
        repo.set_account_sync_status(
            account_id, "error" if mode == "real" else "degraded", _now()
        )
        logger.warning("iPad 同步协议失败 account=%s mode=%s: %s", account_id, mode, exc)
        return {
            "counts": counts,
            "degraded": True,
            "error": str(exc),
            "total": total,
        }

    repo.set_account_sync_status(account_id, "success", _now())
    return {"counts": counts, "degraded": False, "error": None, "total": total}


# ---------------------------------------------------------------------------
# 发送文本消息
# ---------------------------------------------------------------------------
def send_text_message(
    account_id: str, target_type: str, target_id: str, content: str
) -> dict:
    """向联系人 / 群 / 会话发送文本消息（后端反查 user_id/room_id + isRoom）。

    成功返回 `{"msgId", "serverId", "ok": True}`；
    目标解析失败抛 `IPadSyncError`（400）；协议失败抛 `IPadProtocolError`（502）。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    send_userid, is_room = _resolve_target(repo, account_id, target_type, target_id)
    result = ipad_client.send_text_msg(uuid, send_userid, is_room, content, kf_id=0)
    # 真实服务 msg_id/server_id 可能为 int 或 null；SendTextResultDTO 的字段为
    # str 类型（Pydantic v2 不自动把 int/None 转 str），需在此统一转 str，
    # 否则响应 schema 校验失败 → ResponseValidationError → 500（见任务 Issue #4）。
    return {
        "msgId": str(result.get("msg_id") or ""),
        "serverId": str(result.get("server_id") or ""),
        "ok": True,
    }


def _resolve_target(
    repo: ChannelMgmtRepository, account_id: str, target_type: str, target_id: str
) -> tuple[str, bool]:
    """解析发送目标 → (send_userid, is_room)。

    - contact：查 channel_contacts.user_id，isRoom=false
    - room：查 channel_groups.room_id（兼容按群 id 反查），isRoom=true
    - session：msg_type==1 → remote_session_id + isRoom=true；
      msg_type==3 → 400（应用会话禁发）；否则 contact_id→user_id + isRoom=false
    """
    if target_type == "contact":
        c = repo.get_contact_by_id(target_id)
        if not c or not c.get("user_id"):
            raise IPadSyncError("联系人不存在或缺少 user_id")
        return c["user_id"], False
    if target_type == "room":
        g = repo.get_group_by_room_id(account_id, target_id) or repo.get_group_by_id(
            target_id
        )
        # 兼容 DTO(camelCase: roomId) 与单测 FakeRepo(snake_case: room_id)
        room_id = g.get("roomId") or g.get("room_id") if g else None
        if not g or not room_id:
            raise IPadSyncError("群不存在或缺少 room_id")
        return room_id, True
    if target_type == "session":
        s = repo.get_session_by_id(target_id)
        if not s:
            raise IPadSyncError("会话不存在")
        msg_type = _as_int(s.get("msg_type"))
        if msg_type == 3:
            raise IPadSyncError("应用类会话不支持发送消息")
        if msg_type == 1:
            remote = s.get("remote_session_id") or ""
            if not remote:
                raise IPadSyncError("群会话缺少 room_id")
            return remote, True
        contact_id = s.get("contact_id")
        if not contact_id:
            raise IPadSyncError("会话缺少关联联系人")
        c = repo.get_contact_by_id(contact_id)
        if not c or not c.get("user_id"):
            raise IPadSyncError("关联联系人缺少 user_id")
        return c["user_id"], False
    raise IPadSyncError("未知的发送目标类型")


# ---------------------------------------------------------------------------
# 实体 upsert 辅助
# ---------------------------------------------------------------------------
def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_department_node(item: dict) -> bool:
    """判断内部联系人条目是否为部门节点（不应落库为联系人）。

    真实协议字段大小写不一致：可能为 `is_Department`（大写 D）或
    `is_department`（小写）。两字段任一等于 1 即视为部门节点（决策 #9）。
    """
    for key in ("is_Department", "is_department"):
        if _as_int(item.get(key)) == 1:
            return True
    return False


def _upsert_inner_contact(
    repo: ChannelMgmtRepository,
    account_id: str,
    channel: str,
    channel_type: str,
    item: dict,
) -> None:
    user_id = str(item.get("user_id") or "")
    if not user_id:
        return
    cid = f"{account_id}:{user_id}"
    name = item.get("nickname") or item.get("realname") or ""
    extra = {
        "corpid": item.get("corpid"),
        "partyid": item.get("partyid"),
        "english_name": item.get("english_name"),
        "position": item.get("position"),
        "SelfAttrInfo": item.get("SelfAttrInfo"),
    }
    repo.upsert_channel_contact(
        {
            "id": cid,
            "account_id": account_id,
            "channel": channel,
            "channel_type": channel_type,
            "name": name,
            "nickname": item.get("nickname") or "",
            "type": "internal",
            "status": "online",
            "remark": item.get("remark") or "",
            "description": "",
            "add_time": "",
            "source": "",
            "user_id": user_id,
            "label_ids": "[]",
            "raw_status": "",
            "avatar": item.get("avatar") or "",
            "extra_json": json.dumps(extra, ensure_ascii=False),
        }
    )


def _upsert_external_contact(
    repo: ChannelMgmtRepository,
    account_id: str,
    channel: str,
    channel_type: str,
    item: dict,
) -> None:
    user_id = str(item.get("user_id") or "")
    if not user_id:
        return
    cid = f"{account_id}:{user_id}"
    raw_status = str(item.get("status", ""))
    label_ids = item.get("labelid") or item.get("label_ids") or []
    name = item.get("nickname") or item.get("realname") or ""
    # status 展示映射：0/1/2049 视为失效关系 → offline，其余 online
    status = "offline" if raw_status in ("0", "1", "2049") else "online"
    repo.upsert_channel_contact(
        {
            "id": cid,
            "account_id": account_id,
            "channel": channel,
            "channel_type": channel_type,
            "name": name,
            "nickname": item.get("nickname") or "",
            "type": "customer",
            "status": status,
            "remark": item.get("company_remark") or item.get("remarks") or "",
            "description": "",
            "add_time": item.get("add_customer_time") or "",
            "source": item.get("source") or "",
            "user_id": user_id,
            "label_ids": json.dumps(label_ids, ensure_ascii=False),
            "raw_status": raw_status,
            "avatar": item.get("avatar") or "",
            "extra_json": json.dumps(
                {
                    "source_info": item.get("source_info"),
                    "mobile": item.get("mobile"),
                },
                ensure_ascii=False,
            ),
        }
    )
    # 决策 #2：外部联系人 labelid[] 原样存 customer_profiles.tags
    repo.upsert_customer_profile_for_contact(
        cid,
        {
            "phone": item.get("mobile") or "",
            "company": "",
            "position": "",
            "remark": item.get("company_remark") or "",
            "add_time": item.get("add_customer_time") or "",
            "add_channel": channel,
            "tags": label_ids,
        },
    )


def _upsert_group(repo: ChannelMgmtRepository, account_id: str, item: dict) -> None:
    room_id = str(item.get("room_id") or item.get("roomId") or "")
    if not room_id:
        return
    gid = f"{account_id}:{room_id}"
    # 兼容两种来源的头像/链接字段：
    # - GetSessionRoomList：roomurl / roomUrl / image_url / imageUrl / room_url
    # - GetChatroomMembers：roomUrl
    room_url = (
        item.get("roomUrl")
        or item.get("room_url")
        or item.get("roomurl")
        or item.get("image_url")
        or item.get("imageUrl")
        or ""
    )
    extra = {
        "managers": item.get("managers"),
        "is_external": item.get("is_external"),
    }
    repo.upsert_channel_group(
        {
            "id": gid,
            "account_id": account_id,
            "room_id": room_id,
            "group_type": "customer_group",  # 决策 #10：P0 统一客户群
            "nickname": item.get("nickname") or "",
            "total": _as_int(item.get("total")),
            "room_url": room_url,
            "notice_content": "",
            "create_time": item.get("create_time") or "",
            "update_time": item.get("update_time") or "",
            "extra_json": json.dumps(extra, ensure_ascii=False),
        }
    )


def _upsert_session(
    repo: ChannelMgmtRepository,
    account_id: str,
    channel: str,
    channel_type: str,
    item: dict,
) -> None:
    sessionid = str(item.get("sessionid") or item.get("sessionId") or "")
    if not sessionid:
        return
    msg_type = _as_int(item.get("msgtype", item.get("msgType")))
    sid = f"{account_id}:{sessionid}"
    unreadcnt = _as_int(item.get("unreadcnt", item.get("unreadCnt")))
    beginmsgseq = str(item.get("beginmsgseq", item.get("beginMsgSeq", "")) or "")
    session_type = _MSG_TYPE_LABEL.get(msg_type, "其他")
    external_tag = "外部" if msg_type in (0, 1) else "内部"

    contact_id: str | None = None
    name = sessionid
    if msg_type == 1:
        # 群聊：remote_session_id = room_id；尝试取群名
        grp = repo.get_group_by_room_id(account_id, sessionid)
        if grp:
            # 兼容 DTO(name) 与单测 FakeRepo(nickname)
            name = grp.get("name") or grp.get("nickname") or sessionid
    else:
        # 好友 / 开放平台：contact_id = {account_id}:{sessionid}（假设 sessionid==user_id）
        contact_id = f"{account_id}:{sessionid}"
        c = repo.get_contact_by_id(contact_id)
        if c:
            # 优先取联系人真实昵称（channel_contacts.nickname 已校准）；
            # 避免 name 列为空时落库成 raw sessionid 编号（见任务 Issue #2）。
            name = c.get("nickname") or c.get("name") or sessionid

    repo.upsert_channel_session(
        {
            "id": sid,
            "account_id": account_id,
            "contact_id": contact_id,
            "name": name,
            "channel": channel,
            "channel_type": channel_type,
            "last_message": "",
            "last_time": "",
            "unread_count": unreadcnt,
            "read_status": "unread" if unreadcnt > 0 else "read",
            "hosted_status": "unhosted",
            "hosted_bot_id": None,
            "owner": "",
            "online_status": "online",
            "session_type": session_type,
            "external_tag": external_tag,
            "add_time": "",
            "hosting_chain": "-",
            "remote_session_id": sessionid,
            "msg_type": msg_type,
            "begin_msg_seq": beginmsgseq,
        }
    )


# ---------------------------------------------------------------------------
# P1+P2 增量服务（标签 / 搜索添加 / 已读 / 历史回填 / 富媒体 / 实时回调）
# 沿用分层：Router → 本模块 → ipad_client → Repository；异常统一 IPadSyncError/
# IPadProtocolError（路由层转 400/502）。新协议函数不补 mock 分支（决策 #7）。
# ---------------------------------------------------------------------------
import uuid as _uuid  # noqa: E402  (模块末尾追加服务，保持顶层 import 风格)


def _generate_msg_id(conversation_id: str, server_id: str) -> str:
    """消息 id（幂等键）：chmsg-{conversation_id}:{server_id}（缺失时 uuid 兜底）。"""
    if server_id:
        return f"chmsg-{conversation_id}:{server_id}"
    return f"chmsg-{conversation_id}:{_uuid.uuid4().hex[:10]}"


# ---- P1-1 标签同步 ----
def sync_labels(account_id: str) -> dict:
    """同步 iPad 标签列表（企业=1 + 个人=2，默认两类都同步，决策 #8）到 Morphix 标签体系。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        return {"accountId": account_id, "total": 0, "synced": 0, "skipped": True}
    uuid: str = account["ipadUuid"]
    total = 0
    synced = 0
    for sync_type in (1, 2):
        index = 0
        while total < SYNC_TOTAL_CAP:
            try:
                res = ipad_client.get_label_list(uuid, index, sync_type)
            except ipad_client.IPadProtocolError as exc:
                logger.warning("GetLabelListReq 失败 account=%s sync_type=%s: %s", account_id, sync_type, exc)
                break
            lst = res["list"]
            if not lst:
                break
            for item in lst:
                _upsert_ipad_label(repo, account_id, item, sync_type)
                total += 1
                synced += 1
                if total >= SYNC_TOTAL_CAP:
                    break
            if len(lst) < 100:
                break
            nxt = int(res.get("index", 0) or 0)
            if not nxt:
                break
            index = nxt
    return {"accountId": account_id, "total": total, "synced": synced, "skipped": False}


def _upsert_ipad_label(repo: ChannelMgmtRepository, account_id: str, item: dict, sync_type: int) -> None:
    """把一个 iPad 标签项归一化后 upsert（id/name/label_type/label_groupid）。"""
    label = {
        "id": item.get("id") or item.get("labelId"),
        "name": item.get("name") or item.get("labelName"),
        # 协议常省略/返回 null 的 label_type；用 `or 0` 兜底，避免上游 received None
        "label_type": item.get("label_type") or item.get("labelType") or 0,
        "label_groupid": item.get("label_groupid") or item.get("labelGroupId"),
        "sync_type": sync_type,
    }
    repo.upsert_ipad_label(account_id, label)


# ---- P1-2 搜索 / 添加外部联系人 ----
def search_contact(account_id: str, keyword: str) -> list[dict]:
    """按手机号/关键词搜索企业微信外部联系人（SearchContact）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    try:
        res = ipad_client.search_contact(uuid, keyword)
    except ipad_client.IPadProtocolError as exc:
        raise IPadSyncError(f"iPad 协议服务不可用（SearchContact）：{exc}")
    lst = res.get("list") or res.get("userList") or []
    return [
        {
            "userId": str(item.get("user_id") or item.get("userId") or ""),
            "name": item.get("name") or "",
            "sex": _as_int(item.get("sex")),
            "headImg": item.get("headImg") or item.get("head_img") or "",
            "ticket": item.get("ticket") or "",
            "openId": item.get("openId") or item.get("open_id") or "",
            "corpId": item.get("corp_id") or item.get("corpId") or "",
            "state": str(item.get("state", "") or ""),
        }
        for item in lst
    ]


def set_contact_labels(
    account_id: str, contact_id: str, label_ids: list[str]
) -> dict:
    """编辑联系人 iPad 标签（双写：先 iPad 生效，再 Morphix 落库，决策 #9）。

    - 调 `ipad_client.user_add_labels` 让 iPad 侧先生效（UserAddLabelsReq：增减标签）；
    - 调 `ChannelMgmtRepository.set_contact_ipad_labels` 做 Morphix 侧双写
      （重写 `customer_profiles.tags` 镜像 + 重建 iPad 标签关系，保留非 iPad 标签）。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    contact = repo.get_contact_by_id(contact_id)
    if not contact:
        raise IPadSyncError("联系人不存在")
    uuid: str = account["ipadUuid"]
    user_id: str = contact.get("user_id") or ""
    try:
        # iPad 侧先生效（UserAddLabelsReq：按完整标签集合增减）
        ipad_client.user_add_labels(uuid, user_id, list(label_ids))
    except ipad_client.IPadProtocolError as exc:
        raise IPadSyncError(f"iPad 协议服务不可用（UserAddLabelsReq）：{exc}")
    # Morphix 侧双写（决策 #9：iPad 先生效，再落库）
    repo.set_contact_ipad_labels(account_id, contact_id, list(label_ids))
    return {
        "ok": True,
        "accountId": account_id,
        "contactId": contact_id,
        "labelIds": list(label_ids),
    }


def add_search_contact(account_id: str, payload: dict) -> dict:
    """发送好友申请（AddSearch 主路径 / AddWxUser 兜底）并落库联系人。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    vid = payload.get("vid", "")
    openId = payload.get("openId", "")
    phone = payload.get("phone", "")
    content = payload.get("content", "")
    ticket = payload.get("ticket", "")
    name = payload.get("name", "")
    try:
        if payload.get("useDirectAdd"):
            # 直接添加（仅限曾被删除过的场景）
            ipad_client.add_wx_user(uuid, vid, content)
        else:
            ipad_client.add_search(uuid, vid, openId, phone, content, ticket)
    except ipad_client.IPadProtocolError as exc:
        raise IPadSyncError(f"iPad 协议服务不可用（AddSearch）：{exc}")
    contact_id = repo.add_contact_from_search(
        account_id,
        {
            "user_id": vid,
            "name": name,
            "headImg": payload.get("headImg", ""),
            "ticket": ticket,
            "openId": openId,
            "corp_id": payload.get("corpId", ""),
            "state": payload.get("state", ""),
        },
    )
    return {"ok": True, "contactId": contact_id or "", "vid": vid}


# ---- P2-2 已读 ----
def mark_session_read(account_id: str, session_id: str) -> dict:
    """进入会话时清除 iPad 侧未读（MarkAsRead）并回写本地未读状态。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    session = repo.get_session_by_id(session_id)
    if not session:
        raise IPadSyncError("会话不存在")
    msg_type = _as_int(session.get("msg_type"))
    remote = session.get("remote_session_id") or ""
    if msg_type == 1:
        if not remote:
            raise IPadSyncError("群会话缺少 room_id")
        send_userid, is_room = remote, True
    else:
        contact_id = session.get("contact_id")
        if not contact_id:
            raise IPadSyncError("会话缺少关联联系人")
        c = repo.get_contact_by_id(contact_id)
        if not c or not c.get("user_id"):
            raise IPadSyncError("关联联系人缺少 user_id")
        send_userid, is_room = c["user_id"], False
    try:
        ipad_client.mark_as_read(uuid, send_userid, is_room)
    except ipad_client.IPadProtocolError as exc:
        logger.warning("MarkAsRead 失败 account=%s session=%s: %s", account_id, session_id, exc)
    repo.mark_session_read_db(session_id)
    return {"ok": True, "sessionId": session_id}


# ---- T02 建群（mock-first）+ 一键已读（本地持久化） ----
def create_group(account_id: str, member_ids: list[str], room_name: str = "") -> dict:
    """建群（mock-first）：解析 user_id → create_chatroom → upsert 群 + 群会话。

    返回 GroupDTO(dict)；real 模式协议失败抛 `IPadProtocolError`（路由转 502），
    auto/mock 降级仍落库返回 GroupDTO（决策 #7）。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    channel: str = account.get("channel", "企业微信")
    channel_type: str = account.get("channelType", "wecom")

    # 1) 解析 memberIds → iPad user_id（wxids）
    wxids: list[str] = []
    nicknames: list[str] = []
    for cid in member_ids:
        c = repo.get_contact_by_id(cid)
        if c and c.get("user_id"):
            wxids.append(c["user_id"])
            nicknames.append(c.get("nickname") or c.get("name") or "")

    # 2) 调 iPad 建群（mock-first 降级；real 失败抛异常）
    room = ipad_client.create_chatroom(uuid, wxids, room_name)
    room_id: str = room.get("room_id") or f"mock_room_{uuid[:8]}"
    _ = bool(room.get("mock"))

    # 3) upsert channel_groups（group_type=customer_group）
    #    名称优先 room_name，否则拼接成员昵称 + "的群聊"
    if room_name:
        group_name = room_name
    elif nicknames:
        picked = [n for n in nicknames if n][:3]
        group_name = "、".join(picked)
        if len(nicknames) > 3:
            group_name += "等"
        group_name += "的群聊"
    else:
        group_name = "新建群聊"
    repo.upsert_channel_group(
        {
            "id": f"{account_id}:{room_id}",
            "account_id": account_id,
            "room_id": room_id,
            "group_type": "customer_group",
            "nickname": group_name,
            "total": len(wxids),
            "room_url": "",
            "notice_content": "",
            "create_time": _now(),
            "update_time": _now(),
            "extra_json": "{}",
        }
    )

    # 4) 一并落群会话，支撑「直接点击聊天」
    repo.create_session_for_room(account_id, room_id, group_name, channel, channel_type)

    group = repo.get_group_by_room_id(account_id, room_id)
    if group is None:
        # 兜底（极少见）：直接构造返回
        return {
            "id": f"{account_id}:{room_id}",
            "accountId": account_id,
            "roomId": room_id,
            "groupType": "customer_group",
            "name": group_name,
            "total": len(wxids),
            "roomUrl": "",
            "noticeContent": "",
            "createTime": _now(),
            "updateTime": _now(),
        }
    return group


def mark_sessions_read_local(
    account_id: str, session_ids: list[str] | None = None
) -> dict:
    """仅本地清零未读（不调 iPad）。返回 {"updated": int}。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        raise IPadSyncError("账号不存在")
    updated = repo.mark_sessions_read_local(account_id, session_ids)
    return {"updated": int(updated)}


# ---- P2-1 消息历史回填 ----
def backfill_session_messages(account_id: str, session_id: str) -> dict:
    """按会话回填消息历史。

    - 群聊（msg_type==1）：GetGroupMsgList 拉取并落库；
    - 1:1（msg_type!=1）：SyncAllData 触发，由实时回调（P2-4）推送落库（强耦合）。
    返回 upserted / triggered / message。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    session = repo.get_session_by_id(session_id)
    if not session:
        raise IPadSyncError("会话不存在")
    msg_type = _as_int(session.get("msg_type"))
    upserted = 0

    if msg_type == 1:
        # 群聊历史
        try:
            res = ipad_client.get_group_msg_list(uuid)
        except ipad_client.IPadProtocolError as exc:
            logger.warning("GetGroupMsgList 失败 account=%s: %s", account_id, exc)
            return {
                "accountId": account_id, "sessionId": session_id,
                "upserted": 0, "triggered": False, "message": str(exc),
            }
        for item in res.get("list") or res.get("listdata") or []:
            msg = _parse_group_msg(item, session, account_id)
            if msg and not repo.message_exists(msg["conversation_id"], msg["server_id"]):
                repo.upsert_channel_message(msg)
                upserted += 1
        return {
            "accountId": account_id, "sessionId": session_id,
            "upserted": upserted, "triggered": False, "message": "群聊历史回填完成",
        }

    # 1:1 历史：触发离线消息回填（回调接收）
    try:
        seq = _max_server_seq(repo, session_id)
        ipad_client.sync_all_data(uuid, limit=1000, seq=seq)
        triggered = True
        message = "已触发离线消息回填，新消息将经回调入站"
    except ipad_client.IPadProtocolError as exc:
        logger.warning("SyncAllData 失败 account=%s: %s", account_id, exc)
        triggered = False
        message = str(exc)
    return {
        "accountId": account_id, "sessionId": session_id,
        "upserted": upserted, "triggered": triggered, "message": message,
    }


def _max_server_seq(repo: ChannelMgmtRepository, conversation_id: str) -> int:
    """取会话最大 server_id（整数游标）；非整数返回 0（全量回填）。"""
    row = repo._db.query_one(
        "SELECT server_id FROM messages WHERE conversation_id = ? AND server_id != '' "
        "ORDER BY CAST(server_id AS INTEGER) DESC LIMIT 1",
        (conversation_id,),
    )
    if not row or not row.get("server_id"):
        return 0
    try:
        return int(row["server_id"])
    except (TypeError, ValueError):
        return 0


def _parse_group_msg(item: dict, session: dict, account_id: str) -> dict | None:
    """把 GetGroupMsgList 的 listdata 项归一化为 messages 行。

    协议内容形状待联调（PRD §5 #2），此处做 best-effort：
    - server_id 取 id/seq；
    - content 为列表时拼接文本，含图片/文件字段则标记 content_type；
    - 缺时间用当前时间（避免空值）。
    """
    raw_id = item.get("id") or item.get("seq")
    server_id = str(raw_id) if raw_id is not None else ""
    if not server_id:
        server_id = _uuid.uuid4().hex[:10]
    conversation_id = session["id"]
    sender_id = str(item.get("sender") or item.get("user_id") or session.get("remote_session_id") or "")
    content_parts = item.get("content")
    text_parts: list[str] = []
    content_type = "text"
    media_meta: dict = {}
    if isinstance(content_parts, str):
        text_parts.append(content_parts)
    elif isinstance(content_parts, list):
        for part in content_parts:
            if isinstance(part, dict):
                ptype = str(part.get("type") or part.get("msgType") or "")
                if ptype in ("image", "img", "1", "3") or "img" in ptype.lower():
                    content_type = "image" if "file" not in ptype.lower() else "file"
                    media_meta = {k: part.get(k) for k in ("url", "cdnkey", "aeskey", "md5", "width", "height", "size", "file_id") if part.get(k) is not None}
                else:
                    text_parts.append(str(part.get("content") or part.get("text") or part.get("msg") or ""))
            elif isinstance(part, str):
                text_parts.append(part)
    if item.get("file_id") or item.get("aes_key"):
        content_type = "file" if item.get("file_id") else "image"
        media_meta = {k: item.get(k) for k in ("file_id", "aes_key", "md5", "width", "height", "size", "url") if item.get(k) is not None}
    return {
        "id": _generate_msg_id(conversation_id, server_id),
        "conversation_id": conversation_id,
        "sender_type": "user",
        "content": "\n".join([t for t in text_parts if t]).strip() or (server_id if content_type != "text" else ""),
        "created_at": _now(),
        "server_id": server_id,
        "msg_type": 1,
        "sender_id": sender_id,
        "direction": "inbound",
        "content_type": content_type,
        "media_url": media_meta.get("url") or media_meta.get("file_id") or media_meta.get("cdnkey") or "",
        "media_meta": media_meta,
        "is_read": 0,
        "channel_account_id": account_id,
    }


# ---- P2-3 富媒体发送（后端代理 CDN 上传） ----
def send_media_message(
    account_id: str,
    target_type: str,
    target_id: str,
    file_bytes: bytes,
    file_name: str,
    media_type: str,
) -> dict:
    """向联系人/群/会话发送图片或文件（后端代理 CDN 上传 + 发送）。

    成功返回 SendMediaResultDTO；目标解析失败抛 IPadSyncError（400）；
    协议失败抛 IPadProtocolError（502）。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        raise IPadSyncError("账号不存在或未托管 iPad")
    uuid: str = account["ipadUuid"]
    send_userid, is_room = _resolve_target(repo, account_id, target_type, target_id)
    conversation_id = target_id if target_type == "session" else target_id

    if media_type == "file":
        try:
            up = ipad_client.cdn_upload_file(file_bytes, file_name, uuid)
        except ipad_client.IPadProtocolError as exc:
            raise IPadSyncError(f"iPad 协议服务不可用（CdnUploadFile）：{exc}")
        try:
            res = ipad_client.send_cdn_file_msg(
                uuid, send_userid, is_room, up["fileid"], up["aes_key"], up["md5"], file_name, up["size"]
            )
        except ipad_client.IPadProtocolError as exc:
            raise IPadSyncError(f"iPad 协议服务不可用（SendCDNFileMsg）：{exc}")
        server_id = res.get("server_id", "")
        msg = {
            "id": _generate_msg_id(conversation_id, server_id),
            "conversation_id": conversation_id,
            "sender_type": "user",
            "content": file_name,
            "server_id": server_id,
            "msg_type": 2,
            "sender_id": send_userid,
            "direction": "outbound",
            "content_type": "file",
            "media_url": up["fileid"],
            "media_meta": {"fileName": file_name, "md5": up["md5"], "size": up["size"]},
            "is_read": 1,
            "channel_account_id": account_id,
        }
    else:  # image
        try:
            up = ipad_client.cdn_upload_img(file_bytes, file_name, uuid)
        except ipad_client.IPadProtocolError as exc:
            raise IPadSyncError(f"iPad 协议服务不可用（CdnUploadImg）：{exc}")
        try:
            res = ipad_client.send_cdn_img_msg(
                uuid, send_userid, is_room, up["cdn_key"], up["aes_key"], up["md5"], up["size"], up["width"], up["height"]
            )
        except ipad_client.IPadProtocolError as exc:
            raise IPadSyncError(f"iPad 协议服务不可用（SendCDNImgMsg）：{exc}")
        server_id = res.get("server_id", "")
        msg = {
            "id": _generate_msg_id(conversation_id, server_id),
            "conversation_id": conversation_id,
            "sender_type": "user",
            "content": file_name,
            "server_id": server_id,
            "msg_type": 1,
            "sender_id": send_userid,
            "direction": "outbound",
            "content_type": "image",
            "media_url": up["cdn_key"],
            "media_meta": {"width": up["width"], "height": up["height"], "size": up["size"], "md5": up["md5"]},
            "is_read": 1,
            "channel_account_id": account_id,
        }
    repo.upsert_channel_message(msg)
    return {
        "msgId": res.get("msg_id", ""),
        "serverId": server_id,
        "contentType": media_type,
        "mediaUrl": msg["media_url"],
        "ok": True,
    }


# ---- P2-4 实时回调 ----
def handle_callback(uuid: str, payload: object, type_: str) -> dict:
    """处理 iPad 实时回调推送（POST /wxwork/callback）。

    解析 {uuid, json, type}，按 (conversation_id, server_id) 幂等落库新消息，
    并更新对应会话未读。返回 upserted 计数。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo._db.query_one(
        "SELECT * FROM channel_accounts WHERE ipad_uuid = ?", (uuid,)
    )
    if not account:
        logger.warning("回调账号未找到 uuid=%s", uuid)
        return {"ok": False, "upserted": 0, "message": "未知账号"}
    account_id = account["id"]

    data = payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            data = {}
    if not isinstance(data, dict):
        data = {}

    msgs = _extract_callback_messages(data, type_)
    upserted = 0
    for m in msgs:
        conv = (
            m.get("conversation_id")
            or m.get("room_id")
            or m.get("session_id")
            or m.get("conversationId")
            or uuid
        )
        server_id = str(m.get("server_id") or m.get("id") or m.get("msgId") or m.get("seq") or "")
        if repo.message_exists(conv, server_id):
            continue
        msg = {
            "id": _generate_msg_id(conv, server_id),
            "conversation_id": conv,
            "sender_type": "user",
            "content": m.get("content", ""),
            "server_id": server_id,
            "msg_type": _as_int(m.get("msg_type")),
            "sender_id": str(m.get("sender") or m.get("user_id") or ""),
            "direction": "inbound",
            "content_type": m.get("content_type") or "text",
            "media_url": m.get("media_url") or "",
            "media_meta": m.get("media_meta") or {},
            "is_read": 0,
            "channel_account_id": account_id,
        }
        repo.upsert_channel_message(msg)
        repo.increment_session_unread(conv, account_id)
        upserted += 1
    return {"ok": True, "upserted": upserted}


def _extract_callback_messages(data: dict, type_: str) -> list[dict]:
    """从回调负载中尽力提取消息列表（协议字段形状待联调，做兼容多种形态）。"""
    cands: list = []
    for key in ("msg", "message", "data", "list", "msgs", "messages"):
        v = data.get(key)
        if v is None:
            continue
        if isinstance(v, list):
            cands.extend(v)
        elif isinstance(v, dict):
            cands.append(v)
    if not cands and ("content" in data or "id" in data or "msgId" in data or "seq" in data):
        cands.append(data)
    out: list[dict] = []
    for c in cands:
        if not isinstance(c, dict):
            continue
        out.append(
            {
                "conversation_id": c.get("session_id") or c.get("room_id") or c.get("conversationId"),
                "server_id": c.get("server_id") or c.get("msgId") or c.get("seq"),
                "id": c.get("id") or c.get("server_id") or c.get("msgId") or c.get("seq"),
                "content": c.get("content") or c.get("text") or "",
                "msg_type": c.get("msg_type") or c.get("msgType") or 0,
                "sender": c.get("sender") or c.get("user_id") or c.get("fromUser"),
                "content_type": c.get("content_type") or c.get("contentType") or "text",
                "media_url": c.get("media_url") or c.get("url") or "",
                "media_meta": c.get("media_meta") or {},
            }
        )
    return out


# ---- P2-4 回调注册（托管成功后 best-effort） ----
def register_callback(account_id: str) -> dict:
    """若配置了 IPAD_CALLBACK_PUBLIC_URL，则向 iPad 服务注册实时回调地址。

    未配置时降级为「仅手动同步」并返回 registered=False（PRD §5 #5）。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        return {"ok": False, "registered": False, "message": "账号不存在或未托管 iPad"}
    public_url = (settings.ipad_callback_public_url or "").strip()
    if not public_url:
        return {
            "ok": False,
            "registered": False,
            "message": "未配置 IPAD_CALLBACK_PUBLIC_URL，跳过回调注册（仅手动同步）",
        }
    uuid: str = account["ipadUuid"]
    callback_type = (settings.ipad_callback_type or "HTTP").upper()
    try:
        ipad_client.set_callback_url(uuid, public_url, callback_type)
    except ipad_client.IPadProtocolError as exc:
        logger.warning("SetCallbackUrl 失败 account=%s: %s", account_id, exc)
        return {"ok": False, "registered": False, "message": str(exc)}
    repo.set_account_callback(account_id, public_url, callback_type)
    return {"ok": True, "registered": True, "url": public_url, "callbackType": callback_type}
