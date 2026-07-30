"""聊天框消息头像（`MessageExtDTO.senderAvatar`）—— 测试套件。

需求：企业微信托管聊天的聊天框里，每条消息都要显示发送者头像。
实现：`ChannelMgmtRepository._resolve_sender_avatar` 从已同步入库的头像列解析，
并在 `row_to_message_ext` 中输出为 `senderAvatar`：

- outbound（本账号发出）        → `channel_accounts.avatar`
- inbound 群消息                → `channel_group_members.avatar`（按 room_id 定位群）
- inbound 1:1 消息              → `channel_contacts.avatar`
- 未同步 / 无头像               → `""`（前端回退首字占位）

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_message_avatar.py -q
"""
from __future__ import annotations

import os

os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest

from app import schema as schema_mod
import app.database as _db_mod
from app.database import SQLiteBackend, set_backend
from app.repositories import ChannelMgmtRepository

ACCOUNT_VID = "1688850473951280"
FRIEND_ID = "7881302555913738"
STRANGER_ID = "7881309999999999"
ROOM_ID = "10817857038351957"
MEMBER_ID = "7881302577712345"
IPAD_UUID = "avatar-uuid-0001"

ACCOUNT_AVATAR = "https://wework.qpic.cn/avatar/account.png"
CONTACT_AVATAR = "https://wework.qpic.cn/avatar/friend.png"
MEMBER_AVATAR = "https://wework.qpic.cn/avatar/member.png"


@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端。"""
    be = SQLiteBackend(tmp_path / "morphix_test_avatar.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def repo(backend) -> ChannelMgmtRepository:
    return ChannelMgmtRepository(backend)


@pytest.fixture
def account(repo) -> dict:
    """已托管账号（含真实头像，供 outbound 消息使用）。"""
    return repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="team-avatar",
        name="头像测试账号",
        ipad_uuid=IPAD_UUID,
        ipad_user_info={"userId": ACCOUNT_VID},
        host_status="hosted",
        avatar=ACCOUNT_AVATAR,
    )


def _contact_row(account_id: str, user_id: str, avatar: str) -> dict:
    """构造 channel_contacts 行（自然键 id = {account_id}:{user_id}）。"""
    return {
        "id": f"{account_id}:{user_id}",
        "account_id": account_id,
        "channel": "企业微信",
        "channel_type": "wecom",
        "name": f"好友{user_id[-4:]}",
        "nickname": f"好友{user_id[-4:]}",
        "type": "customer",
        "status": "online",
        "remark": "",
        "description": "",
        "add_time": "",
        "source": "sync",
        "user_id": user_id,
        "label_ids": "[]",
        "raw_status": "",
        "extra_json": "{}",
        "avatar": avatar,
    }


def _message_row(
    account_id: str,
    conversation_id: str,
    msg_id: str,
    direction: str,
    sender_id: str,
    content: str,
) -> dict:
    """构造 messages 行（字段与 upsert_channel_message 约定一致）。"""
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "sender_type": "user",
        "content": content,
        "created_at": "2025-01-01T10:00:00",
        "server_id": msg_id,
        "msg_type": 0,
        "sender_id": sender_id,
        "direction": direction,
        "content_type": "text",
        "media_url": "",
        "media_meta": "{}",
        "is_read": 1,
        "channel_account_id": account_id,
    }


@pytest.fixture
def friend_conv(repo, account) -> str:
    """1:1 会话：好友已同步且有头像。"""
    account_id = account["id"]
    repo.upsert_channel_contact(_contact_row(account_id, FRIEND_ID, CONTACT_AVATAR))
    return f"{account_id}:{FRIEND_ID}"


@pytest.fixture
def room_conv(repo, account) -> str:
    """群会话：群 + 群成员均已同步，成员有头像。"""
    account_id = account["id"]
    group_id = f"{account_id}:{ROOM_ID}"
    repo.upsert_channel_group(
        {
            "id": group_id,
            "account_id": account_id,
            "room_id": ROOM_ID,
            "nickname": "客户群A",
            "total": 2,
        }
    )
    repo.upsert_channel_group_member(
        {
            "id": f"{group_id}:{MEMBER_ID}",
            "group_id": group_id,
            "uin": MEMBER_ID,
            "user_id": MEMBER_ID,
            "nickname": "群成员小王",
            "avatar": MEMBER_AVATAR,
        }
    )
    return group_id


class TestOutboundAvatar:
    """outbound 消息使用本账号头像。"""

    def test_outbound_uses_account_avatar(self, repo, account, friend_conv):
        repo.upsert_channel_message(
            _message_row(account["id"], friend_conv, "m-out-1", "outbound", ACCOUNT_VID, "我回复的")
        )
        msgs = repo.list_session_messages_ext(friend_conv)
        assert len(msgs) == 1
        assert msgs[0]["senderAvatar"] == ACCOUNT_AVATAR

    def test_outbound_without_sender_id_still_resolves(self, repo, account, friend_conv):
        """发送侧落库常留空 sender_id → 仍应按 direction 命中账号头像。"""
        repo.upsert_channel_message(
            _message_row(account["id"], friend_conv, "m-out-2", "outbound", "", "无 sender_id")
        )
        assert repo.list_session_messages_ext(friend_conv)[0]["senderAvatar"] == ACCOUNT_AVATAR

    def test_outbound_falls_back_to_conversation_prefix_account(self, repo, account, friend_conv):
        """旧数据 channel_account_id 为空 → 由 conversation_id 前缀兜底解析账号。"""
        row = _message_row(account["id"], friend_conv, "m-out-3", "outbound", "", "旧数据")
        row["channel_account_id"] = ""
        repo.upsert_channel_message(row)
        assert repo.list_session_messages_ext(friend_conv)[0]["senderAvatar"] == ACCOUNT_AVATAR


class TestInbound1v1Avatar:
    """inbound 1:1 消息使用联系人头像。"""

    def test_inbound_uses_contact_avatar(self, repo, account, friend_conv):
        repo.upsert_channel_message(
            _message_row(account["id"], friend_conv, "m-in-1", "inbound", FRIEND_ID, "你好，在吗")
        )
        assert repo.list_session_messages_ext(friend_conv)[0]["senderAvatar"] == CONTACT_AVATAR

    def test_unknown_sender_returns_empty(self, repo, account):
        """陌生人（联系人未同步）→ 空串，由前端回退占位。"""
        conv = f"{account['id']}:{STRANGER_ID}"
        repo.upsert_channel_message(
            _message_row(account["id"], conv, "m-in-2", "inbound", STRANGER_ID, "新好友消息")
        )
        assert repo.list_session_messages_ext(conv)[0]["senderAvatar"] == ""

    def test_contact_without_avatar_returns_empty(self, repo, account):
        """联系人已同步但 avatar 为空串 → 返回空串而非 None。"""
        account_id = account["id"]
        repo.upsert_channel_contact(_contact_row(account_id, STRANGER_ID, ""))
        conv = f"{account_id}:{STRANGER_ID}"
        repo.upsert_channel_message(
            _message_row(account_id, conv, "m-in-3", "inbound", STRANGER_ID, "无头像好友")
        )
        assert repo.list_session_messages_ext(conv)[0]["senderAvatar"] == ""


class TestInboundRoomAvatar:
    """inbound 群消息使用群成员头像。"""

    def test_inbound_room_uses_group_member_avatar(self, repo, account, room_conv):
        repo.upsert_channel_message(
            _message_row(account["id"], room_conv, "m-room-1", "inbound", MEMBER_ID, "群里发言")
        )
        assert repo.list_session_messages_ext(room_conv)[0]["senderAvatar"] == MEMBER_AVATAR

    def test_group_member_avatar_wins_over_contact(self, repo, account, room_conv):
        """同一人既是好友又是群成员 → 群会话内优先取群成员头像。"""
        account_id = account["id"]
        repo.upsert_channel_contact(_contact_row(account_id, MEMBER_ID, CONTACT_AVATAR))
        repo.upsert_channel_message(
            _message_row(account_id, room_conv, "m-room-2", "inbound", MEMBER_ID, "群里发言")
        )
        assert repo.list_session_messages_ext(room_conv)[0]["senderAvatar"] == MEMBER_AVATAR

    def test_unsynced_member_falls_back_to_contact(self, repo, account, room_conv):
        """群成员未同步但此人是好友 → 回落联系人头像，避免空白。"""
        account_id = account["id"]
        repo.upsert_channel_contact(_contact_row(account_id, FRIEND_ID, CONTACT_AVATAR))
        repo.upsert_channel_message(
            _message_row(account_id, room_conv, "m-room-3", "inbound", FRIEND_ID, "新成员发言")
        )
        assert repo.list_session_messages_ext(room_conv)[0]["senderAvatar"] == CONTACT_AVATAR

    def test_member_without_avatar_returns_empty(self, repo, account, room_conv):
        """群成员已同步但无头像且非好友 → 空串。"""
        account_id = account["id"]
        repo.upsert_channel_group_member(
            {
                "id": f"{room_conv}:{STRANGER_ID}",
                "group_id": room_conv,
                "uin": STRANGER_ID,
                "user_id": STRANGER_ID,
                "nickname": "无头像成员",
                "avatar": "",
            }
        )
        repo.upsert_channel_message(
            _message_row(account_id, room_conv, "m-room-4", "inbound", STRANGER_ID, "无头像发言")
        )
        assert repo.list_session_messages_ext(room_conv)[0]["senderAvatar"] == ""

    def test_other_account_group_not_matched(self, repo, account, room_conv):
        """群按 account_id + room_id 定位 → 不会串到其他账号的同号群。"""
        other_account_id = "acc_other"
        other_group_id = f"{other_account_id}:{ROOM_ID}"
        repo.upsert_channel_group(
            {
                "id": other_group_id,
                "account_id": other_account_id,
                "room_id": ROOM_ID,
                "nickname": "他人同号群",
                "total": 1,
            }
        )
        repo.upsert_channel_group_member(
            {
                "id": f"{other_group_id}:{STRANGER_ID}",
                "group_id": other_group_id,
                "uin": STRANGER_ID,
                "user_id": STRANGER_ID,
                "nickname": "他人群成员",
                "avatar": "https://wework.qpic.cn/avatar/other.png",
            }
        )
        repo.upsert_channel_message(
            _message_row(account["id"], room_conv, "m-room-5", "inbound", STRANGER_ID, "串号测试")
        )
        assert repo.list_session_messages_ext(room_conv)[0]["senderAvatar"] == ""


class TestDtoContract:
    """DTO 契约：字段恒存在、类型恒为 str，前端可直接消费。"""

    def test_sender_avatar_key_always_present(self, repo, account, friend_conv):
        repo.upsert_channel_message(
            _message_row(account["id"], friend_conv, "m-c-1", "inbound", FRIEND_ID, "hi")
        )
        dto = repo.list_session_messages_ext(friend_conv)[0]
        assert "senderAvatar" in dto and isinstance(dto["senderAvatar"], str)

    def test_existing_fields_unchanged(self, repo, account, friend_conv):
        """新增字段不得破坏既有 DTO 字段（回归保护）。"""
        repo.upsert_channel_message(
            _message_row(account["id"], friend_conv, "m-c-2", "inbound", FRIEND_ID, "hi")
        )
        dto = repo.list_session_messages_ext(friend_conv)[0]
        for key in (
            "id", "conversationId", "senderType", "content", "createdAt",
            "serverId", "msgType", "senderId", "direction", "contentType",
            "mediaUrl", "mediaMeta", "isRead", "channelAccountId",
        ):
            assert key in dto, f"缺失既有 DTO 字段：{key}"
        assert dto["conversationId"] == friend_conv
        assert dto["senderId"] == FRIEND_ID

    def test_mixed_conversation_each_message_resolved(self, repo, account, friend_conv):
        """同一会话内收发混合 → 逐条头像各自正确。"""
        account_id = account["id"]
        repo.upsert_channel_message(
            _message_row(account_id, friend_conv, "m-x-1", "inbound", FRIEND_ID, "在吗")
        )
        repo.upsert_channel_message(
            _message_row(account_id, friend_conv, "m-x-2", "outbound", ACCOUNT_VID, "在的")
        )
        msgs = repo.list_session_messages_ext(friend_conv)
        avatars = {m["id"]: m["senderAvatar"] for m in msgs}
        assert avatars["m-x-1"] == CONTACT_AVATAR
        assert avatars["m-x-2"] == ACCOUNT_AVATAR


class TestHttpResponseModel:
    """HTTP 层契约：`response_model=list[MessageExtDTO]` 不得丢弃 senderAvatar。

    背景 Bug：repositories 已输出 `senderAvatar`，但 `app/schemas.py` 的
    `MessageExtDTO` 未声明该字段 → FastAPI/Pydantic 序列化时静默丢弃，
    仓储层单测全绿而线上 HTTP 响应缺字段。本组用例走 TestClient 端到端
    覆盖 `GET /api/channels/{account_id}/messages` 的真实序列化路径。
    """

    def test_http_response_contains_sender_avatar(self, repo, account, friend_conv):
        """HTTP 响应 JSON 中 senderAvatar 存在且值正确（inbound + outbound）。"""
        from fastapi.testclient import TestClient
        from app.main import app

        account_id = account["id"]
        repo.upsert_channel_message(
            _message_row(account_id, friend_conv, "m-h-1", "inbound", FRIEND_ID, "在吗")
        )
        repo.upsert_channel_message(
            _message_row(account_id, friend_conv, "m-h-2", "outbound", ACCOUNT_VID, "在的")
        )
        with TestClient(app) as client:
            r = client.get(
                f"/api/channels/{account_id}/messages",
                params={"conversationId": friend_conv},
            )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        by_id = {m["id"]: m for m in body}
        # 关键断言：schema 声明缺失时此 key 会被序列化层整体丢弃。
        assert "senderAvatar" in by_id["m-h-1"], "HTTP 响应丢失 senderAvatar 字段"
        assert by_id["m-h-1"]["senderAvatar"] == CONTACT_AVATAR
        assert by_id["m-h-2"]["senderAvatar"] == ACCOUNT_AVATAR

    def test_http_response_avatar_empty_string_for_unknown_sender(self, repo, account):
        """陌生发送者 → HTTP 响应中 senderAvatar 为空串（而非缺 key / null）。"""
        from fastapi.testclient import TestClient
        from app.main import app

        account_id = account["id"]
        conv = f"{account_id}:{STRANGER_ID}"
        repo.upsert_channel_message(
            _message_row(account_id, conv, "m-h-3", "inbound", STRANGER_ID, "陌生消息")
        )
        with TestClient(app) as client:
            r = client.get(
                f"/api/channels/{account_id}/messages",
                params={"conversationId": conv},
            )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["senderAvatar"] == ""

    def test_schema_dto_declares_sender_avatar(self):
        """schemas.MessageExtDTO 必须声明 senderAvatar（防止未来回归误删）。"""
        from app.schemas import MessageExtDTO

        fields = MessageExtDTO.model_fields
        assert "senderAvatar" in fields, "schemas.MessageExtDTO 缺少 senderAvatar 声明"
        assert fields["senderAvatar"].default == ""


class TestEdgeCases:
    """QA 补充边界：脏数据/旧数据/极端形态均不得抛异常（防御性回归）。"""

    def test_legacy_conv_without_colon_no_exception(self, repo):
        """旧消息：channel_account_id 空且 conversation_id 无冒号前缀 → 空串不抛异常。"""
        assert repo._resolve_sender_avatar("", "inbound", "someone", "legacy-conv") == ""

    @pytest.mark.parametrize("conv", ["", None])
    def test_empty_or_none_conversation_id_safe(self, repo, conv):
        """conversation_id 为空/None → 安全返回空串。"""
        assert repo._resolve_sender_avatar("", "inbound", "x", conv) == ""
        assert repo._resolve_sender_avatar("", "outbound", "", conv) == ""

    def test_multi_colon_conversation_id_safe(self, repo):
        """conversation_id 含多个冒号 → split(maxsplit=1) 只切首段，不抛异常。"""
        assert repo._resolve_sender_avatar("", "inbound", "x", "a:b:c:d") == ""

    def test_inbound_sender_equals_account_vid_in_room(self, repo, account, room_conv):
        """极端：inbound 且 sender_id 恰为本账号 vid（自己在群发言被记 inbound）
        → 按群成员表命中，不误取账号头像。"""
        account_id = account["id"]
        self_avatar = "https://wework.qpic.cn/avatar/self-in-room.png"
        repo.upsert_channel_group_member(
            {
                "id": f"{room_conv}:{ACCOUNT_VID}",
                "group_id": room_conv,
                "uin": ACCOUNT_VID,
                "user_id": ACCOUNT_VID,
                "nickname": "我自己",
                "avatar": self_avatar,
            }
        )
        repo.upsert_channel_message(
            _message_row(account_id, room_conv, "m-e-1", "inbound", ACCOUNT_VID, "自发群言")
        )
        assert repo.list_session_messages_ext(room_conv)[0]["senderAvatar"] == self_avatar

    def test_relative_or_dirty_avatar_returned_as_is(self, repo, account):
        """头像列为相对路径/含空格串 → 后端原样返回 str（安全渲染由前端 onError 兜底）。"""
        account_id = account["id"]
        dirty = "/relative/broken path.png"
        repo.upsert_channel_contact(_contact_row(account_id, STRANGER_ID, dirty))
        conv = f"{account_id}:{STRANGER_ID}"
        repo.upsert_channel_message(
            _message_row(account_id, conv, "m-e-2", "inbound", STRANGER_ID, "脏头像")
        )
        got = repo.list_session_messages_ext(conv)[0]["senderAvatar"]
        assert got == dirty and isinstance(got, str)
