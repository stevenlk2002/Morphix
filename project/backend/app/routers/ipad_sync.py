"""iPad 协议同步 / 发送路由（T02）。

统一前缀 `/channels`（由 `api_router` 挂 `/api`），完整路径：
- `POST /api/channels/{account_id}/sync`            手动触发全量同步
- `GET  /api/channels/{account_id}/sync-status`    同步状态查询
- `POST /api/channels/{account_id}/send-text`       发送文本消息（后端反查目标）
- `GET  /api/channels/{account_id}/groups`          群列表
- `GET  /api/channels/{account_id}/group/{room_id}/members`  群成员（T04）

错误码（见 docs/ipad-sync-design.md 共享知识 #3）：
- 400 参数缺失 / 应用会话禁发 / 目标解析失败
- 404 账号不存在或未托管 iPad
- 409 该账号正在同步中
- 502 iPad 协议服务不可用（发送）
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from .. import ipad_client, ipad_sync
from ..database import get_backend
from ..repositories import ChannelMgmtRepository
from ..schemas import (
    AddGroupMembersRequest,
    AddSearchRequest,
    BackfillResultDTO,
    CreateGroupRequest,
    MarkSessionsReadLocalRequest,
    ContactSearchResultDTO,
    GroupDTO,
    GroupDetailDTO,
    GroupMemberDTO,
    LabelDTO,
    LabelSyncResultDTO,
    MessageExtDTO,
    SearchContactRequest,
    SendMediaResultDTO,
    SetContactLabelsRequest,
    SendTextRequest,
    SendTextResultDTO,
    SetGroupNoticeRequest,
    SyncResultDTO,
    SyncStatusDTO,
    TransferGroupOwnerRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["ipad-sync"])


@router.post("/{account_id}/sync")
def trigger_sync(account_id: str) -> dict:
    """手动触发全量同步（后台线程，立即返回 started / skipped）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account or not account.get("ipadUuid"):
        return JSONResponse(status_code=404, content={"message": "账号不存在或未托管 iPad"})
    started = ipad_sync.trigger_sync(account_id)
    if not started:
        return JSONResponse(
            status_code=409,
            content={"skipped": True, "accountId": account_id, "message": "该账号正在同步中"},
        )
    return {"started": True, "accountId": account_id, "message": "同步已启动"}


@router.get("/{account_id}/sync-status", response_model=SyncStatusDTO)
def sync_status(account_id: str):
    """查询账号同步状态。"""
    status = ipad_sync.get_sync_status(account_id)
    if status is None:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    return status


@router.post("/{account_id}/send-text", response_model=SendTextResultDTO)
def send_text(account_id: str, payload: SendTextRequest) -> dict:
    """发送文本消息（后端反查 user_id/room_id + isRoom）。"""
    if not payload.targetId or not payload.content:
        return JSONResponse(status_code=400, content={"message": "缺少 targetId 或 content"})
    try:
        return ipad_sync.send_text_message(
            account_id, payload.targetType, payload.targetId, payload.content
        )
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})
    except ipad_client.IPadProtocolError as exc:
        return JSONResponse(
            status_code=502,
            content={"message": f"iPad 协议服务不可用（SendTextMsg）：{exc}"},
        )


@router.get("/{account_id}/groups", response_model=list[GroupDTO])
def list_groups(account_id: str, groupType: str | None = None):
    """群列表（groupType=customer_group|internal_group，缺省返回全部）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    return repo.list_groups(account_id, groupType)


@router.get("/{account_id}/group/{room_id}/members", response_model=GroupDetailDTO)
def group_members(account_id: str, room_id: str):
    """群成员详情（T04）：实时拉取 GetRoomUserList，失败降级已落库成员。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    group = repo.get_group_by_room_id(account_id, room_id) or repo.get_group_by_id(room_id)
    if not group:
        return JSONResponse(status_code=404, content={"message": "群不存在，请先同步"})

    members = repo.list_group_members(group["id"])
    notice_content = group.get("noticeContent", "")
    total = group.get("total", 0)

    try:
        info = ipad_client.get_room_user_list(account["ipadUuid"], room_id)
        notice_content = info.get("notice_content") or notice_content
        total = info.get("total") or total
        # 实时成员落库（P1 填充），保证后续查询有数据
        for m in info.get("member_list", []):
            uin = str(m.get("uin") or m.get("user_id") or "")
            mid = f"{group['id']}:{uin or m.get('nickname', '')}"
            repo.upsert_channel_group_member(
                {
                    "id": mid,
                    "group_id": group["id"],
                    "uin": uin,
                    "user_id": str(m.get("user_id") or ""),
                    "nickname": m.get("nickname") or "",
                    "realname": m.get("realname") or "",
                    "avatar": m.get("avatar") or "",
                    "room_nickname": m.get("room_nickname") or m.get("roomNickname") or "",
                    "sex": int(m.get("sex", 0) or 0),
                    "mobile": m.get("mobile") or "",
                    "join_time": m.get("jointime") or m.get("joinTime") or "",
                }
            )
        members = repo.list_group_members(group["id"])
    except ipad_client.IPadProtocolError as exc:
        logger.warning("GetRoomUserList 失败，降级返回已落库成员 account=%s: %s", account_id, exc)

    return {
        "group": group,
        "members": members,
        "noticeContent": notice_content,
        "total": total,
    }


# ---------------------------------------------------------------------------
# P1-1 标签同步 / 查询
# ---------------------------------------------------------------------------
@router.post("/{account_id}/labels/sync", response_model=LabelSyncResultDTO)
def sync_labels_endpoint(account_id: str):
    """手动触发 iPad 标签同步（企业标签 + 个人标签，决策 #8）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    return ipad_sync.sync_labels(account_id)


@router.get("/{account_id}/labels", response_model=list[LabelDTO])
def list_labels_endpoint(account_id: str, syncType: int | None = None):
    """查询已同步的 iPad 标签（syncType 可过滤 1=企业 2=个人）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    return repo.get_ipad_labels(account_id, syncType)


@router.get("/{account_id}/contacts/{contact_id}/labels")
def contact_ipad_labels_endpoint(account_id: str, contact_id: str):
    """查询联系人 iPad 标签（真实标签名，来自 ipad_label_map 映射，决策 #2/#9）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    return repo.get_contact_ipad_labels(account_id, contact_id)


@router.post("/{account_id}/contacts/{contact_id}/labels")
def set_contact_labels_endpoint(account_id: str, contact_id: str, payload: SetContactLabelsRequest):
    """编辑联系人 iPad 标签（双写端点，决策 #9）。

    先驱动 iPad 侧 `UserAddLabelsReq` 生效，再落 Morphix 侧双写
    （`set_contact_ipad_labels`：重写 customer_profiles.tags 镜像 + 重建标签关系）。
    错误码统一（见 docs/ipad-sync-design.md 共享知识 #3）：协议错误经服务层
    预包装为 IPadSyncError，返回 400；不再保留不可达的 502 分支。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.set_contact_labels(account_id, contact_id, payload.labelIds or [])
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


# ---------------------------------------------------------------------------
# P1-2 搜索 / 添加外部联系人
# ---------------------------------------------------------------------------
@router.post("/{account_id}/contacts/search", response_model=list[ContactSearchResultDTO])
def search_contact_endpoint(account_id: str, payload: SearchContactRequest):
    """按手机号/关键词搜索企业微信外部联系人（SearchContact）。

    错误码（见 docs/ipad-sync-design.md 共享知识 #3）：协议错误经服务层
    `ipad_sync.search_contact` 预包装为 `IPadSyncError`，统一返回 400；
    不再保留 `except ipad_client.IPadProtocolError → 502` 分支——该分支不可达
    （服务层已将其转译为 IPadSyncError），属统一错误码时清理的死代码。
    """
    if not payload.keyword:
        return JSONResponse(status_code=400, content={"message": "缺少 keyword"})
    try:
        return ipad_sync.search_contact(account_id, payload.keyword)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


@router.post("/{account_id}/contacts/add-search")
def add_search_contact_endpoint(account_id: str, payload: AddSearchRequest):
    """发送好友申请（AddSearch 主路径 / AddWxUser 兜底），并落库联系人。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.add_search_contact(account_id, payload.model_dump())
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


# ---------------------------------------------------------------------------
# P2-2 已读
# ---------------------------------------------------------------------------
@router.post("/{account_id}/sessions/{session_id}/read")
def mark_session_read_endpoint(account_id: str, session_id: str):
    """进入会话时清除未读（MarkAsRead + 回写本地未读状态）。"""
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.mark_session_read(account_id, session_id)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


# ---------------------------------------------------------------------------
# T02 建群（mock-first）+ 一键已读（本地持久化）
# ---------------------------------------------------------------------------
@router.post("/{account_id}/groups", response_model=GroupDTO)
def create_group_endpoint(account_id: str, payload: CreateGroupRequest):
    """建群（mock-first）：memberIds 解析为 iPad user_id → create_chatroom → 落库。

    错误码（共享知识 #3）：404 账号不存在；400 memberIds 空 / 参数解析失败；
    502 real 模式 iPad 协议真实失败。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    if not payload.memberIds:
        return JSONResponse(status_code=400, content={"message": "memberIds 不能为空"})
    try:
        return ipad_sync.create_group(account_id, payload.memberIds, payload.roomName)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})
    except ipad_client.IPadProtocolError as exc:
        return JSONResponse(
            status_code=502,
            content={"message": f"iPad 协议服务不可用（CreateChatRoom）：{exc}"},
        )


@router.post("/{account_id}/sessions/read-local")
def mark_sessions_read_local_endpoint(account_id: str, payload: MarkSessionsReadLocalRequest):
    """一键已读（本地）：仅清本地未读，不调 iPad。

    sessionIds=None 表示清空当前账号全部会话未读。返回 {"updated": int}。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.mark_sessions_read_local(account_id, payload.sessionIds)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


# ---------------------------------------------------------------------------
# P2-1 消息历史回填
# ---------------------------------------------------------------------------
@router.post(
    "/{account_id}/sessions/{session_id}/messages/backfill",
    response_model=BackfillResultDTO,
)
def backfill_session_messages_endpoint(account_id: str, session_id: str):
    """按会话回填消息历史。

    群聊（msg_type==1）走 GetGroupMsgList 直接落库；
    1:1（msg_type!=1）走 SyncAllData 触发，由实时回调（P2-4）推送落库。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.backfill_session_messages(account_id, session_id)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


# ---------------------------------------------------------------------------
# T04 群管理（mock-first）
# ---------------------------------------------------------------------------
@router.post("/{account_id}/group/{room_id}/members")
def add_group_members_endpoint(
    account_id: str, room_id: str, payload: AddGroupMembersRequest
):
    """添加群成员（mock-first：仅落库，不调 iPad 协议）。"""
    repo = ChannelMgmtRepository(get_backend())
    if not repo.get_account_by_id(account_id):
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    if not payload.contactIds:
        return JSONResponse(status_code=400, content={"message": "contactIds 不能为空"})
    try:
        return ipad_sync.add_group_members(account_id, room_id, payload.contactIds)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


@router.delete("/{account_id}/group/{room_id}/members/{member_id}")
def remove_group_member_endpoint(account_id: str, room_id: str, member_id: str):
    """移除群成员。member_id 可为 contactId 或 user_id（前端按 contactId 传）。"""
    repo = ChannelMgmtRepository(get_backend())
    if not repo.get_account_by_id(account_id):
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.remove_group_member(account_id, room_id, member_id)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


@router.put("/{account_id}/group/{room_id}/notice")
def set_group_notice_endpoint(
    account_id: str, room_id: str, payload: SetGroupNoticeRequest
):
    """更新群公告。"""
    repo = ChannelMgmtRepository(get_backend())
    if not repo.get_account_by_id(account_id):
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.set_group_notice(account_id, room_id, payload.notice or "")
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


@router.post("/{account_id}/group/{room_id}/transfer")
def transfer_group_owner_endpoint(
    account_id: str, room_id: str, payload: TransferGroupOwnerRequest
):
    """转让群主（mock-first）。"""
    repo = ChannelMgmtRepository(get_backend())
    if not repo.get_account_by_id(account_id):
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    if not payload.newOwnerUserId:
        return JSONResponse(status_code=400, content={"message": "newOwnerUserId 不能为空"})
    try:
        return ipad_sync.transfer_group_owner(
            account_id, room_id, payload.newOwnerUserId
        )
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


@router.delete("/{account_id}/group/{room_id}")
def dismiss_group_endpoint(account_id: str, room_id: str):
    """解散群（mock-first：删群 + 群成员 + 群会话）。"""
    repo = ChannelMgmtRepository(get_backend())
    if not repo.get_account_by_id(account_id):
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    try:
        return ipad_sync.dismiss_group(account_id, room_id)
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


# ---------------------------------------------------------------------------
# P2-3 富媒体发送（后端代理 CDN 上传）
# ---------------------------------------------------------------------------
@router.post("/{account_id}/send-media", response_model=SendMediaResultDTO)
async def send_media_endpoint(
    account_id: str,
    file: UploadFile = File(...),
    targetType: str = Form(...),
    targetId: str = Form(...),
    mediaType: str = Form("image"),
):
    """发送图片或文件（后端代理 CDN 上传 + 发送）。

    mediaType 仅支持 `image` | `file`；target 解析失败（400）或协议失败（502）
    按共享知识 #3 转对应错误码。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    if not targetType or not targetId:
        return JSONResponse(status_code=400, content={"message": "缺少 targetType 或 targetId"})
    if mediaType not in ("image", "file"):
        return JSONResponse(status_code=400, content={"message": "mediaType 仅支持 image | file"})
    file_bytes = await file.read()
    file_name = file.filename or ("image.png" if mediaType == "image" else "file.bin")
    try:
        return ipad_sync.send_media_message(
            account_id, targetType, targetId, file_bytes, file_name, mediaType
        )
    except ipad_sync.IPadSyncError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})
    except ipad_client.IPadProtocolError as exc:
        return JSONResponse(
            status_code=502,
            content={"message": f"iPad 协议服务不可用（CDN 上传/发送）：{exc}"},
        )


# ---------------------------------------------------------------------------
# P2 扩展消息列表（带光标分页，含富媒体/已读等字段）
# ---------------------------------------------------------------------------
@router.get("/{account_id}/messages", response_model=list[MessageExtDTO])
def list_session_messages_ext_endpoint(
    account_id: str, conversationId: str = "", cursor: str = "", limit: int = 20
):
    """分页加载会话消息（cursor 续查；返回 MessageExtDTO）。

    conversationId 为会话/群 id（即 messages.conversation_id）。
    """
    repo = ChannelMgmtRepository(get_backend())
    account = repo.get_account_by_id(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"message": "账号不存在"})
    if not conversationId:
        return JSONResponse(status_code=400, content={"message": "缺少 conversationId"})
    return repo.list_session_messages_ext(conversationId, cursor, limit)
