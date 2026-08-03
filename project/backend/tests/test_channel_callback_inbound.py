"""实时回调入站消息落库修复 —— 测试套件（Bug：入站消息聊天框不显示）。

根因：`handle_callback` 落库的 `conversation_id` 未对齐会话主键
`channel_sessions.id`（`{account_id}:{remote_session_id}`），导致前端
`GET /sessions/{session_id}/messages`（`list_session_messages`）查不到消息。

覆盖（payload 均按 IPad协议API文档「下发-消息接收」真实形态构造）：
1. 1:1 文本消息（snake_case：sender/receiver/is_room/server_id/referid）
   → conversation_id == 会话 id，且 list_session_messages 可查到；
2. 群消息（is_room=1 + room_conversation_id）→ 落到群会话 id；
3. referid != 0 的操作类回调（如已读）→ 跳过，不产生新消息；
4. camelCase 字段变体（roomId/fromUser/msgId/createTime）→ 兼容解析；
5. 手机端自发消息（sender == 账号 vid）→ direction=outbound、不加未读；
6. 路由端到端：外层 {uuid, json, type} 且 json 为字符串 → 二次解码落库；
7. 无本地会话时兜底 conversation_id = {account_id}:{remote_id}。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_channel_callback_inbound.py -q
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest

from app import ipad_sync
from app import schema as schema_mod
import app.database as _db_mod
from app.database import SQLiteBackend, set_backend
from app.repositories import ChannelMgmtRepository

# 与线上形态一致的远程 id（数字串）。
ACCOUNT_VID = "1688850473951280"
FRIEND_ID = "7881302555913738"
ROOM_ID = "10817857038351957"
IPAD_UUID = "cb-uuid-0001"


@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端。"""
    be = SQLiteBackend(tmp_path / "morphix_test_callback.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture
def account(backend):
    """已托管账号（vid = 本账号远程 id，用于方向判定）。"""
    repo = ChannelMgmtRepository(backend)
    return repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="team-cb",
        name="回调测试账号",
        ipad_uuid=IPAD_UUID,
        ipad_user_info={"userId": ACCOUNT_VID},
        host_status="hosted",
    )


def _session_row(account_id: str, remote_id: str, msg_type: int, **over) -> dict:
    """构造 channel_sessions 行（id = {account_id}:{remote_id}，与生产约定一致）。"""
    return {
        "id": f"{account_id}:{remote_id}",
        "account_id": account_id,
        "contact_id": over.get("contact_id"),
        "name": over.get("name", remote_id),
        "channel": "企业微信",
        "channel_type": "wecom",
        "last_message": "",
        "last_time": "",
        "unread_count": over.get("unread_count", 0),
        "read_status": "read",
        "hosted_status": "unhosted",
        "hosted_bot_id": None,
        "owner": "",
        "online_status": "online",
        "session_type": "群聊" if msg_type == 1 else "好友",
        "external_tag": "外部",
        "add_time": "",
        "hosting_chain": "-",
        "remote_session_id": remote_id,
        "msg_type": msg_type,
        "begin_msg_seq": "",
    }


def _friend_session(repo: ChannelMgmtRepository, account_id: str) -> str:
    sid = f"{account_id}:{FRIEND_ID}"
    repo.upsert_channel_session(_session_row(account_id, FRIEND_ID, 0))
    return sid


def _room_session(repo: ChannelMgmtRepository, account_id: str) -> str:
    sid = f"{account_id}:{ROOM_ID}"
    repo.upsert_channel_session(_session_row(account_id, ROOM_ID, 1))
    return sid


def _text_payload(**over) -> dict:
    """真实协议 1:1 文本消息体（文档「1. 文本消息接收」示例形态）。"""
    payload = {
        "flag": 16777216,
        "receiver": int(ACCOUNT_VID),
        "sender_name": "",
        "is_room": 0,
        "server_id": 7130717,
        "content": "你好，在吗",
        "issync": False,
        "send_time": 1724024152,
        "sender": int(FRIEND_ID),
        "referid": 0,
        "app_info": "3304183318011621608",
        "readuinscount": 0,
        "msg_id": 1011720,
        "msgType": 2,
        "atList": [],
    }
    payload.update(over)
    return payload


class TestInbound1v1:
    def test_conversation_id_equals_session_id(self, backend, account):
        """1:1 入站消息：conversation_id 必须等于会话 id，前端才能查到。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        res = ipad_sync.handle_callback(IPAD_UUID, _text_payload(), "102000")
        assert res["ok"] is True and res["upserted"] == 1
        # 前端拉取路径：list_session_messages(session_id) 必须命中
        msgs = repo.list_session_messages(sid)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "你好，在吗"
        assert msgs[0]["conversationId"] == sid

    def test_inbound_fields_and_unread(self, backend, account):
        """direction/sender_id/server_id/is_read 正确，且会话未读 +1。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        ipad_sync.handle_callback(IPAD_UUID, _text_payload(), "102000")
        row = repo._db.query_one("SELECT * FROM messages WHERE conversation_id = ?", (sid,))
        assert row["direction"] == "inbound"
        assert row["sender_type"] == "user"
        assert row["sender_id"] == FRIEND_ID
        assert row["server_id"] == "7130717"
        assert int(row["is_read"]) == 0
        sess = repo._db.query_one(
            "SELECT unread_count, read_status FROM channel_sessions WHERE id = ?", (sid,)
        )
        assert sess["unread_count"] == 1 and sess["read_status"] == "unread"

    def test_idempotent_on_server_id(self, backend, account):
        """同一 server_id 重复回调不重复落库。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        assert ipad_sync.handle_callback(IPAD_UUID, _text_payload(), "102000")["upserted"] == 1
        assert ipad_sync.handle_callback(IPAD_UUID, _text_payload(), "102000")["upserted"] == 0
        assert len(repo.list_session_messages(sid)) == 1


class TestInboundRoom:
    def test_room_message_lands_on_room_session(self, backend, account):
        """群消息（is_room=1 + room_conversation_id）→ 落到群会话 id。"""
        repo = ChannelMgmtRepository(backend)
        sid = _room_session(repo, account["id"])
        payload = _text_payload(
            receiver=0,
            is_room=1,
            room_conversation_id=ROOM_ID,
            content="群里通知一下",
            server_id=7752608,
        )
        res = ipad_sync.handle_callback(IPAD_UUID, payload, "102000")
        assert res["upserted"] == 1
        msgs = repo.list_session_messages(sid)
        assert len(msgs) == 1 and msgs[0]["content"] == "群里通知一下"
        # 群消息发送者是群成员而非群 id
        row = repo._db.query_one("SELECT sender_id FROM messages WHERE conversation_id = ?", (sid,))
        assert row["sender_id"] == FRIEND_ID


class TestReferidDedup:
    def test_operation_callback_skipped(self, backend, account):
        """referid != 0（对原消息的操作，如已读）不产生新消息。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        res = ipad_sync.handle_callback(
            IPAD_UUID, _text_payload(referid=7130717, server_id=7130999), "102000"
        )
        assert res["upserted"] == 0 and res["skipped"] == 1
        assert repo.list_session_messages(sid) == []


class TestControlEventNotPersisted:
    """回归：控制/回执类事件禁止落库（Bug：聊天框刷出成片只有时间戳的空气泡）。

    根因：`msgType=2001`（MarkAsRead 已读回执）的 `referid` 恰为 0，绕过了
    `referid != 0` 那道闸门，被当普通消息 INSERT，前端无条件 map 渲染成空气泡。
    """

    @pytest.mark.parametrize("msg_type", [2001, 2118, 2131])
    def test_control_event_skipped(self, backend, account, msg_type):
        """2001/2118/2131 即便 referid=0 也不落库，计入 skipped。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        res = ipad_sync.handle_callback(
            IPAD_UUID,
            _text_payload(content="", msgType=msg_type, server_id=7131000 + msg_type),
            "102000",
        )
        assert res["ok"] is True
        assert res["upserted"] == 0 and res["skipped"] == 1
        assert repo.list_session_messages(sid) == []

    def test_control_event_with_garbage_protobuf_skipped(self, backend, account):
        """2118 携带 protobuf 裸字节正文 → 清洗后为空，同样不落库。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        res = ipad_sync.handle_callback(
            IPAD_UUID,
            _text_payload(content="\n\x06\x08\x00\x12\x02\n\x00", msgType=2118, server_id=7131900),
            "102000",
        )
        assert res["upserted"] == 0 and res["skipped"] == 1
        assert repo.list_session_messages(sid) == []

    def test_blank_content_unknown_msgtype_skipped(self, backend, account):
        """未文档化的空正文事件（1002/1023/2055/2063 等）由通用闸门兜底拦截。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        for idx, msg_type in enumerate((1002, 1003, 1023, 2055, 2063)):
            res = ipad_sync.handle_callback(
                IPAD_UUID,
                _text_payload(content="", msgType=msg_type, server_id=7132000 + idx),
                "102000",
            )
            assert res["upserted"] == 0 and res["skipped"] == 1
        assert repo.list_session_messages(sid) == []

    def test_control_event_does_not_bump_unread(self, backend, account):
        """控制事件不得把会话染成未读（旧实现每条已读回执都 +1）。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        ipad_sync.handle_callback(
            IPAD_UUID, _text_payload(content="", msgType=2001, server_id=7133000), "102000"
        )
        sess = repo._db.query_one(
            "SELECT unread_count, read_status FROM channel_sessions WHERE id = ?", (sid,)
        )
        assert sess["unread_count"] == 0 and sess["read_status"] == "read"

    def test_control_event_with_media_still_persisted(self, backend, account):
        """2001 若真带了表情图片 URL → 仍按图片气泡落库（不误伤动画表情）。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        res = ipad_sync.handle_callback(
            IPAD_UUID,
            _text_payload(
                content="",
                msgType=2001,
                server_id=7134000,
                cdnurl="https://wework.qpic.cn/wwpic3az/emoticon.gif",
            ),
            "102000",
        )
        assert res["upserted"] == 1
        msgs = repo.list_session_messages_ext(sid)
        assert len(msgs) == 1
        assert msgs[0]["contentType"] == "image"
        assert msgs[0]["mediaUrl"] == "https://wework.qpic.cn/wwpic3az/emoticon.gif"

    def test_normal_text_still_persisted(self, backend, account):
        """正常文本消息不受影响（防过度过滤）。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        assert ipad_sync.handle_callback(IPAD_UUID, _text_payload(), "102000")["upserted"] == 1
        assert len(repo.list_session_messages(sid)) == 1

    def test_has_visible_content_matrix(self):
        """`_has_visible_content` 判定矩阵（媒体优先、控制类恒不可见）。"""
        assert ipad_sync._has_visible_content(
            {"msg_type": 2, "content": "你好", "media_url": ""}
        ) is True
        assert ipad_sync._has_visible_content(
            {"msg_type": 101, "content": "", "media_url": "https://x/a.png"}
        ) is True
        assert ipad_sync._has_visible_content(
            {"msg_type": 2, "content": "   ", "media_url": ""}
        ) is False
        assert ipad_sync._has_visible_content(
            {"msg_type": 2001, "content": "[表情]", "media_url": ""}
        ) is False
        assert ipad_sync._has_visible_content(
            {"msg_type": 1011, "content": "已提醒成员填写汇报", "media_url": ""}
        ) is True


class TestCamelCaseCompat:
    def test_camel_case_room_message(self, backend, account):
        """camelCase 变体（roomId/fromUser/msgId/createTime）也能正确解析。"""
        repo = ChannelMgmtRepository(backend)
        sid = _room_session(repo, account["id"])
        payload = {
            "roomId": ROOM_ID,
            "fromUser": FRIEND_ID,
            "msgId": "9988776655",
            "content": "camelCase 群消息",
            "createTime": 1724024152,
            "msgType": 2,
            "referid": 0,
        }
        assert ipad_sync.handle_callback(IPAD_UUID, payload, "102000")["upserted"] == 1
        msgs = repo.list_session_messages(sid)
        assert len(msgs) == 1 and msgs[0]["content"] == "camelCase 群消息"


class TestOutboundSync:
    def test_self_sent_message_is_outbound_no_unread(self, backend, account):
        """sender == 账号 vid（手机端自发）→ outbound、归到对方会话、不加未读。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        payload = _text_payload(
            sender=int(ACCOUNT_VID),
            receiver=int(FRIEND_ID),
            content="我在手机上回复的",
            server_id=7130800,
        )
        assert ipad_sync.handle_callback(IPAD_UUID, payload, "102000")["upserted"] == 1
        row = repo._db.query_one("SELECT * FROM messages WHERE conversation_id = ?", (sid,))
        assert row["direction"] == "outbound" and int(row["is_read"]) == 1
        sess = repo._db.query_one(
            "SELECT unread_count FROM channel_sessions WHERE id = ?", (sid,)
        )
        assert sess["unread_count"] == 0


class TestRouterEndToEnd:
    def test_callback_route_with_json_string(self, backend, account):
        """路由端到端：外层 {uuid, json, type} 且 json 为字符串（真实协议形态）。"""
        from fastapi.testclient import TestClient
        from app.main import app

        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        wrapper = {
            "uuid": IPAD_UUID,
            "json": json.dumps(_text_payload(content="字符串负载消息"), ensure_ascii=False),
            "type": "102000",
        }
        with TestClient(app) as client:
            r = client.post("/wxwork/callback", json=wrapper)
            assert r.status_code == 200
            assert r.json()["upserted"] == 1
        msgs = repo.list_session_messages(sid)
        assert len(msgs) == 1 and msgs[0]["content"] == "字符串负载消息"


class TestFallbackWithoutSession:
    def test_unknown_remote_falls_back_to_convention_id(self, backend, account):
        """本地暂无会话行时，兜底 conversation_id = {account_id}:{remote_id}。

        待会话同步补齐同 id 会话行后，历史消息即自然可见（键约定一致）。
        """
        repo = ChannelMgmtRepository(backend)
        stranger = "7881309999999999"
        payload = _text_payload(sender=int(stranger), server_id=7131000, content="新好友消息")
        assert ipad_sync.handle_callback(IPAD_UUID, payload, "102000")["upserted"] == 1
        expected = f"{account['id']}:{stranger}"
        row = repo._db.query_one(
            "SELECT conversation_id FROM messages WHERE server_id = ?", ("7131000",)
        )
        assert row["conversation_id"] == expected


# ---------------------------------------------------------------------------
# QA 补充边界用例（会话隔离 / 字段缺失降级 / 内容边界 / 批量与异常负载）
# ---------------------------------------------------------------------------
class TestSessionIsolation:
    """会话归属隔离：群消息绝不能串到发送者的 1:1 会话。"""

    def test_room_message_does_not_leak_into_sender_1v1_session(self, backend, account):
        """同一好友既有 1:1 会话又在群里发言 → 消息只入群会话，1:1 会话保持干净。"""
        repo = ChannelMgmtRepository(backend)
        friend_sid = _friend_session(repo, account["id"])
        room_sid = _room_session(repo, account["id"])
        payload = _text_payload(
            receiver=0, is_room=1, room_conversation_id=ROOM_ID,
            content="群内发言", server_id=7752900,
        )
        assert ipad_sync.handle_callback(IPAD_UUID, payload, "102000")["upserted"] == 1
        assert len(repo.list_session_messages(room_sid)) == 1
        assert repo.list_session_messages(friend_sid) == []
        # 未读只加在群会话上
        friend = repo._db.query_one(
            "SELECT unread_count FROM channel_sessions WHERE id = ?", (friend_sid,)
        )
        room = repo._db.query_one(
            "SELECT unread_count FROM channel_sessions WHERE id = ?", (room_sid,)
        )
        assert friend["unread_count"] == 0 and room["unread_count"] == 1

    def test_1v1_and_room_same_server_id_are_independent(self, backend, account):
        """不同会话下的相同 server_id 互不幂等抵消（幂等键含 conversation_id）。"""
        repo = ChannelMgmtRepository(backend)
        friend_sid = _friend_session(repo, account["id"])
        room_sid = _room_session(repo, account["id"])
        ipad_sync.handle_callback(IPAD_UUID, _text_payload(server_id=6001), "102000")
        ipad_sync.handle_callback(
            IPAD_UUID,
            _text_payload(
                server_id=6001, receiver=0, is_room=1,
                room_conversation_id=ROOM_ID, content="群同号消息",
            ),
            "102000",
        )
        assert len(repo.list_session_messages(friend_sid)) == 1
        assert len(repo.list_session_messages(room_sid)) == 1


class TestFieldDegradation:
    """字段缺失/异常时必须安全降级，不得抛异常、不得误杀真实消息。"""

    def test_message_without_referid_is_ingested(self, backend, account):
        """回调不带 referid 字段（真实推送常见）→ 视为新消息落库，不被过滤误杀。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        payload = _text_payload(server_id=7131100, content="无 referid 字段")
        payload.pop("referid")
        assert ipad_sync.handle_callback(IPAD_UUID, payload, "102000")["upserted"] == 1
        assert len(repo.list_session_messages(sid)) == 1

    def test_missing_send_time_falls_back_to_now(self, backend, account):
        """send_time 缺失 → created_at 回退当前时间而非空串（列表排序依赖该列）。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        payload = _text_payload(server_id=7131200)
        payload.pop("send_time")
        ipad_sync.handle_callback(IPAD_UUID, payload, "102000")
        row = repo._db.query_one(
            "SELECT created_at FROM messages WHERE conversation_id = ?", (sid,)
        )
        assert row["created_at"]

    def test_wrapper_without_json_field_degrades(self, backend, account):
        """外层包裹缺失 json 字段 → 不抛异常，返回 upserted=0。"""
        res = ipad_sync.handle_callback(IPAD_UUID, {"uuid": IPAD_UUID, "type": "102000"}, "102000")
        assert res["ok"] is True and res["upserted"] == 0

    def test_invalid_json_string_payload_degrades(self, backend, account):
        """负载为非法 JSON 字符串 → 安全降级，不抛异常。"""
        res = ipad_sync.handle_callback(IPAD_UUID, "not-a-json-{{", "102000")
        assert res["ok"] is True and res["upserted"] == 0

    def test_non_dict_payload_degrades(self, backend, account):
        """负载为 list/None 等非 dict 形态 → 安全降级。"""
        assert ipad_sync.handle_callback(IPAD_UUID, [1, 2, 3], "102000")["upserted"] == 0
        assert ipad_sync.handle_callback(IPAD_UUID, None, "102000")["upserted"] == 0

    def test_unknown_uuid_returns_not_ok(self, backend, account):
        """未知 uuid（非本系统托管账号）→ ok=False，不落库。"""
        res = ipad_sync.handle_callback("uuid-not-exists", _text_payload(), "102000")
        assert res["ok"] is False and res["upserted"] == 0

    def test_message_without_any_party_is_skipped(self, backend, account):
        """既无 sender 也无 receiver/room → 无法归属会话，跳过而非落到脏 key。"""
        payload = {"content": "孤儿消息", "server_id": 7131300, "referid": 0, "msgType": 2}
        res = ipad_sync.handle_callback(IPAD_UUID, payload, "102000")
        assert res["upserted"] == 0 and res["skipped"] == 1


class TestContentBoundary:
    """内容边界：空内容不落库（空气泡 Bug），超大内容需完整落库。"""

    def test_empty_content_message_skipped(self, backend, account):
        """空 content 且无媒体 → 不落库（旧行为落库成只有时间戳的空气泡）。

        原用例断言 `upserted == 1`，钉的是 Bug 行为本身；修复后语义反转为
        「无可见内容不生成气泡」，同时保留「不抛异常」的边界保护意图。
        """
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        res = ipad_sync.handle_callback(
            IPAD_UUID, _text_payload(content="", server_id=7131400), "102000"
        )
        assert res["ok"] is True
        assert res["upserted"] == 0 and res["skipped"] == 1
        assert repo.list_session_messages(sid) == []

    def test_large_content_persisted_intact(self, backend, account):
        """超大文本（50k 字符）无截断、无异常。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        big = "长" * 50000
        ipad_sync.handle_callback(IPAD_UUID, _text_payload(content=big, server_id=7131500), "102000")
        msgs = repo.list_session_messages(sid)
        assert len(msgs) == 1 and len(msgs[0]["content"]) == 50000

    def test_special_characters_preserved(self, backend, account):
        """含引号/换行/emoji/JSON 片段的内容原样保存（防二次解码破坏）。"""
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        tricky = '他说："{\\"a\\":1}"\n换行\t制表 😀'
        ipad_sync.handle_callback(
            IPAD_UUID, _text_payload(content=tricky, server_id=7131600), "102000"
        )
        assert repo.list_session_messages(sid)[0]["content"] == tricky


class TestBatchPayload:
    """批量包裹形态：一次回调多条消息全部落库。"""

    def test_list_wrapped_messages_all_ingested(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        sid = _friend_session(repo, account["id"])
        payload = {
            "list": [
                _text_payload(content="第一条", server_id=7131700),
                _text_payload(content="第二条", server_id=7131701),
            ]
        }
        assert ipad_sync.handle_callback(IPAD_UUID, payload, "102000")["upserted"] == 2
        assert len(repo.list_session_messages(sid)) == 2


class TestContentRendering:
    """msgType → 可读摘要：非文本消息必须显示占位/摘要，避免空气泡。"""

    def test_text_msgtype_uses_content(self):
        assert ipad_sync._render_message_content({"content": "hi"}, 2) == "hi"

    def test_image_msgtype_shows_placeholder(self):
        assert ipad_sync._render_message_content({"file_id": "abc"}, 101) == "[图片]"
        assert ipad_sync._render_message_content({"file_id": "abc"}, 14) == "[图片]"

    def test_gif_msgtype_shows_placeholder(self):
        assert ipad_sync._render_message_content({"url": "http://gif"}, 104) == "[动画表情]"

    def test_control_event_msgtype_yields_empty(self):
        """2001/2118/2131 是多端同步信令而非聊天消息，摘要恒为空串。

        旧断言 `_render_message_content({}, 2001) == "[表情]"` 是历史误判（把已读
        回执当表情），已被 `CONTROL_EVENT_MSG_TYPES` 语义取代（见 test_emoji_render
        同名用例），这里同步纠正，避免两份测试互相矛盾。
        """
        assert ipad_sync._render_message_content({}, 2001) == ""
        assert ipad_sync._render_message_content({}, 2131) == ""
        # 2118 线上会下发 protobuf 裸字节，清洗后同样为空
        assert ipad_sync._render_message_content({"msg": "\n\x06\x08\x00\x12\x02\n\x00"}, 2118) == ""

    def test_file_msgtype_uses_filename(self):
        assert (
            ipad_sync._render_message_content({"file_name": "report.pdf"}, 102)
            == "[文件] report.pdf"
        )

    def test_location_msgtype_uses_address(self):
        assert (
            ipad_sync._render_message_content({"detailed_address": "北京市朝阳区"}, 6)
            == "[位置] 北京市朝阳区"
        )

    def test_redpacket_msgtype_uses_msg_field(self):
        assert (
            ipad_sync._render_message_content({"msg": "恭喜发财，大吉大利"}, 1011)
            == "恭喜发财，大吉大利"
        )

    def test_system_msgtype_uses_msg_field(self):
        assert (
            ipad_sync._render_message_content({"msg": "已提醒成员填写汇报"}, 1611)
            == "已提醒成员填写汇报"
        )

    def test_revoke_msgtype(self):
        assert ipad_sync._render_message_content({}, 10002) == "[撤回了一条消息]"

    def test_card_msgtype_uses_nickname(self):
        assert (
            ipad_sync._render_message_content(
                {"nickname": "张三", "enterpriseName": "腾讯"}, 41
            )
            == "[名片] 张三 / 腾讯"
        )

    def test_link_msgtype_uses_title(self):
        assert (
            ipad_sync._render_message_content({"title": "新闻标题", "url": "http://x"}, 13)
            == "[链接] 新闻标题"
        )

    def test_miniprogram_msgtype_uses_title_first(self):
        assert (
            ipad_sync._render_message_content({"appName": "京东购物", "title": "商品"}, 78)
            == "[小程序] 商品"
        )

    def test_miniprogram_msgtype_falls_back_to_app_name(self):
        assert (
            ipad_sync._render_message_content({"appName": "京东购物"}, 78)
            == "[小程序] 京东购物"
        )

    def test_unknown_msgtype_falls_back_to_content(self):
        assert (
            ipad_sync._render_message_content({"content": "兜底文本"}, 99999)
            == "兜底文本"
        )
