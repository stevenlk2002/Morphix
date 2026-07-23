"""「渠道会话 + 客户管理」iPad 协议同步与发消息 —— 测试套件。

覆盖：
1. 协议函数单测（mock `_post`）：字段正常化、envelope 兼容、错误抛 `IPadProtocolError`。
2. 同步服务单测（mock 协议函数）：is_department 过滤、游标续查、5000 上限、
   串行互斥、自然键 upsert、状态写入、降级。
3. 发消息目标解析单测（FakeRepo）：contact/room/session 映射、应用会话 400。
4. 路由集成测（FastAPI TestClient，mock iPad）：sync 触发、sync-status、groups、
   group members、send-text、空 ipad_uuid 拒绝。
5. 真实服务回归（服务可达时）：对 6 个协议函数发真实请求。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_ipad_sync.py -q -p no:cacheprovider
"""
from __future__ import annotations

import os
import threading
import time

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import httpx
import pytest

from app import ipad_client, ipad_sync
from app import schema as schema_mod
from app.database import SQLiteBackend, set_backend
import app.database as _db_mod
from app.repositories import ChannelMgmtRepository

# --------------------------------------------------------------------------- #
# 测试夹具
# --------------------------------------------------------------------------- #
@pytest.fixture
def backend(tmp_path):
    """隔离的临时 SQLite 库，注入为全局后端，避免污染开发库。"""
    be = SQLiteBackend(tmp_path / "morphix_test.db")
    schema_mod.init_schema(be)
    prev = _db_mod._backend
    set_backend(be)
    yield be
    set_backend(prev)


@pytest.fixture(autouse=True)
def _reset_sync_state():
    """清理进程内互斥状态，避免测试间相互干扰。"""
    ipad_sync._sync_active.clear()
    yield
    ipad_sync._sync_active.clear()


@pytest.fixture
def account(backend):
    """注入一个已托管（ipad_uuid 非空）的测试账号。"""
    repo = ChannelMgmtRepository(backend)
    acc = repo.create_account_with_ipad(
        channel_type="wecom",
        protocol="ipad",
        team_id="team-initial",
        name="QA测试账号",
        ipad_uuid="qa-uuid-0001",
        ipad_user_info={},
        host_status="hosted",
    )
    return acc


# --------------------------------------------------------------------------- #
# 行构造辅助
# --------------------------------------------------------------------------- #
def _contact_row(account_id: str, user_id: str, ctype: str = "customer", **over) -> dict:
    return {
        "id": f"{account_id}:{user_id}",
        "account_id": account_id,
        "channel": "企业微信",
        "channel_type": "wecom",
        "name": over.get("name", user_id),
        "nickname": over.get("nickname", user_id),
        "type": ctype,
        "status": over.get("status", "online"),
        "remark": "",
        "description": "",
        "add_time": "",
        "source": "",
        "user_id": user_id,
        "label_ids": over.get("label_ids", "[]"),
        "raw_status": over.get("raw_status", ""),
        "extra_json": "{}",
    }


def _session_row(account_id: str, sid: str, msg_type: int, **over) -> dict:
    return {
        "id": f"{account_id}:{sid}",
        "account_id": account_id,
        "contact_id": over.get("contact_id"),
        "name": over.get("name", sid),
        "channel": "企业微信",
        "channel_type": "wecom",
        "last_message": "",
        "last_time": "",
        "unread_count": 0,
        "read_status": "unread",
        "hosted_status": "unhosted",
        "hosted_bot_id": None,
        "owner": "",
        "online_status": "online",
        "session_type": over.get("session_type", ""),
        "external_tag": over.get("external_tag", ""),
        "add_time": "",
        "hosting_chain": "-",
        "remote_session_id": over.get("remote_session_id", sid),
        "msg_type": msg_type,
        "begin_msg_seq": over.get("begin_msg_seq", ""),
    }


def _group_row(account_id: str, room_id: str, **over) -> dict:
    return {
        "id": f"{account_id}:{room_id}",
        "account_id": account_id,
        "room_id": room_id,
        "group_type": over.get("group_type", "customer_group"),
        "nickname": over.get("nickname", room_id),
        "total": over.get("total", 0),
        "room_url": over.get("room_url", ""),
        "notice_content": over.get("notice_content", ""),
        "create_time": over.get("create_time", ""),
        "update_time": over.get("update_time", ""),
        "extra_json": "{}",
    }


def _patch_post(monkeypatch, payload):
    """将 `ipad_client._post` 替换为直接返回给定 payload。"""
    monkeypatch.setattr(ipad_client, "_post", lambda path, p=None: payload)


def _mock_all_lists_empty(monkeypatch):
    """把 5 个列表协议函数都 mock 成空返回，便于隔离单路测试。"""
    monkeypatch.setattr(ipad_client, "get_inner_contacts", lambda *a, **k: {"list": [], "strSeq": ""})
    monkeypatch.setattr(ipad_client, "get_external_contacts", lambda *a, **k: {"list": [], "seq": 0})
    monkeypatch.setattr(ipad_client, "get_chatroom_members", lambda *a, **k: {"room_list": [], "star_index": 0})
    monkeypatch.setattr(ipad_client, "get_session_room_list", lambda *a, **k: {"room_list": [], "star_index": 0})
    monkeypatch.setattr(ipad_client, "get_session_list", lambda *a, **k: {"room_list": [], "star_index": 0})


# --------------------------------------------------------------------------- #
# 1. 协议函数单测（mock `_post`）
# --------------------------------------------------------------------------- #
class TestProtocolFunctions:
    # ---- GetInnerContacts ----
    def test_inner_contacts_bare_envelope(self, monkeypatch):
        _patch_post(monkeypatch, {
            "list": [{"user_id": "u1", "nickname": "n1", "is_department": 0, "labelid": ["a"]}],
            "strSeq": "s1",
        })
        r = ipad_client.get_inner_contacts("uuid")
        assert r["strSeq"] == "s1"
        assert r["list"][0]["user_id"] == "u1"
        assert r["list"][0]["labelid"] == ["a"]

    def test_inner_contacts_wrapped_envelope(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"list": [{"user_id": "u1"}], "strSeq": "s2"}})
        r = ipad_client.get_inner_contacts("uuid")
        assert r["strSeq"] == "s2"
        assert r["list"][0]["user_id"] == "u1"

    def test_inner_contacts_empty(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {}})
        r = ipad_client.get_inner_contacts("uuid")
        assert r["list"] == []
        assert r["strSeq"] == ""

    # ---- GetExternalContacts ----
    def test_external_contacts_seq_passthrough(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"list": [{"user_id": "e1", "labelid": [1, 2]}], "seq": 7}})
        r = ipad_client.get_external_contacts("uuid")
        assert r["seq"] == 7  # seq 整数透传
        assert r["list"][0]["labelid"] == [1, 2]

    # ---- GetSessionList ----
    def test_session_list_normalization(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {
            "room_list": [{"sessionid": "s1", "msgtype": 1, "unreadcnt": 3, "beginmsgseq": "b1"}],
            "star_index": 2,
        }})
        r = ipad_client.get_session_list("uuid")
        assert r["star_index"] == 2
        assert r["room_list"][0]["sessionid"] == "s1"
        assert r["room_list"][0]["msgtype"] == 1

    # ---- GetChatroomMembers ----
    def test_chatroom_members_normalization(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {
            "room_list": [{"room_id": "r1", "nickname": "g1", "total": 10, "roomUrl": "u", "create_time": "c"}],
            "star_index": 3,
        }})
        r = ipad_client.get_chatroom_members("uuid")
        assert r["star_index"] == 3
        assert r["room_list"][0]["room_id"] == "r1"
        assert r["room_list"][0]["roomUrl"] == "u"

    # ---- GetRoomUserList ----
    def test_room_user_list_normalization(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {
            "room_id": "r1", "nickname": "g", "total": 5,
            "notice_content": "nc",
            "member_list": [{"uin": "1", "nickname": "m"}],
        }})
        r = ipad_client.get_room_user_list("uuid", "r1")
        assert r["room_id"] == "r1"
        assert r["notice_content"] == "nc"
        assert r["member_list"][0]["uin"] == "1"

    def test_room_user_list_camelcase(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {
            "roomId": "r1", "nickname": "g", "total": 5,
            "noticeContent": "nc", "memberList": [{"uin": "1", "nickname": "m"}],
        }})
        r = ipad_client.get_room_user_list("uuid", "r1")
        assert r["room_id"] == "r1"
        assert r["notice_content"] == "nc"
        assert r["member_list"][0]["uin"] == "1"

    # ---- SendTextMsg ----
    def test_send_text_msg_normalization(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {
            "msg_id": "M1", "server_id": "S1", "content": "c",
        }})
        r = ipad_client.send_text_msg("uuid", "u", False, "c")
        assert r["msg_id"] == "M1"
        assert r["server_id"] == "S1"

    def test_send_text_msg_camelcase(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {
            "msgId": "M", "serverId": "S", "content": "c",
        }})
        r = ipad_client.send_text_msg("uuid", "u", False, "c")
        assert r["msg_id"] == "M"
        assert r["server_id"] == "S"

    # ---- `_post` 错误处理（错误码约定 #3：非 200 / 超时 / JSON 异常 → IPadProtocolError）----
    def test_post_non_200_raises(self, monkeypatch):
        class _Resp:
            status_code = 500

            def json(self):
                return {}

        monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: _Resp())
        with pytest.raises(ipad_client.IPadProtocolError):
            ipad_client._post("wxwork/x", {})

    def test_post_bad_json_raises(self, monkeypatch):
        class _Resp:
            status_code = 200

            def json(self):
                raise ValueError("bad")

        monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: _Resp())
        with pytest.raises(ipad_client.IPadProtocolError):
            ipad_client._post("wxwork/x", {})

    def test_post_timeout_raises(self, monkeypatch):
        def _raise(url, json=None, timeout=None):
            raise httpx.ConnectTimeout("timeout")

        monkeypatch.setattr(httpx, "post", _raise)
        with pytest.raises(ipad_client.IPadProtocolError):
            ipad_client._post("wxwork/x", {})

    def test_function_propagates_protocol_error(self, monkeypatch):
        def _boom(path, p=None):
            raise ipad_client.IPadProtocolError("boom")

        monkeypatch.setattr(ipad_client, "_post", _boom)
        with pytest.raises(ipad_client.IPadProtocolError):
            ipad_client.get_inner_contacts("uuid")


# --------------------------------------------------------------------------- #
# 2. 同步服务单测（mock 协议函数）
# --------------------------------------------------------------------------- #
class TestFullSync:
    def test_filters_department(self, backend, account, monkeypatch):
        inner = [
            {"user_id": "u1", "nickname": "n1", "is_department": 0},
            {"user_id": "dept", "nickname": "d", "is_department": 1},
            {"user_id": "u2", "nickname": "n2", "is_department": 0},
        ]
        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_inner_contacts",
                             lambda *a, **k: {"list": inner, "strSeq": ""})
        res = ipad_sync.run_full_sync(account["id"])
        assert res["counts"]["inner"] == 2
        repo = ChannelMgmtRepository(backend)
        ids = [r["id"] for r in repo.list_contacts(account["id"], type_="internal")]
        assert f"{account['id']}:dept" not in ids
        assert f"{account['id']}:u1" in ids

    def test_cursor_pagination_continues(self, backend, account, monkeypatch):
        calls = {"n": 0}

        def fake(uuid, str_seq="", limit=100):
            calls["n"] += 1
            if calls["n"] == 1:
                # 满页（>=100）才会续查
                return {"list": [{"user_id": f"u{i}", "is_department": 0} for i in range(100)],
                        "strSeq": "x1"}
            # 第二页不足 100 → 视为末页，停止
            return {"list": [{"user_id": f"v{i}", "is_department": 0} for i in range(50)],
                    "strSeq": ""}

        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_inner_contacts", fake)
        res = ipad_sync.run_full_sync(account["id"])
        assert res["counts"]["inner"] == 150
        assert calls["n"] == 2  # 续查第二页后停止（不足 100 视为末页）

    def test_total_cap_5000(self, backend, account, monkeypatch):
        calls = {"n": 0}

        def fake(uuid, str_seq="", limit=100):
            calls["n"] += 1
            return {"list": [{"user_id": f"u{calls['n']}-{i}", "is_department": 0}
                             for i in range(100)], "strSeq": "x"}

        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_inner_contacts", fake)
        res = ipad_sync.run_full_sync(account["id"])
        assert res["counts"]["inner"] == 5000
        assert res["total"] == 5000
        assert calls["n"] == 50  # 恰好在第 50 页（5000 条）处停止，未无限循环

    def test_external_status_mapping_and_labelid(self, backend, account, monkeypatch):
        ext = [
            {"user_id": "e1", "nickname": "客1", "status": "2049", "labelid": [1, 2],
             "add_customer_time": "2024-01-01"},
            {"user_id": "e2", "nickname": "客2", "status": "2", "labelid": []},
        ]
        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_external_contacts",
                             lambda *a, **k: {"list": ext, "seq": 0})
        res = ipad_sync.run_full_sync(account["id"])
        assert res["counts"]["external"] == 2
        repo = ChannelMgmtRepository(backend)
        c1 = repo.get_contact_by_id(f"{account['id']}:e1")
        assert c1["status"] == "offline"  # 2049 -> offline
        assert c1["raw_status"] == "2049"
        assert c1["label_ids"] == "[1, 2]"
        detail = repo.get_contact_detail(f"{account['id']}:e1")
        assert detail["profile"]["tags"] == [1, 2]  # labelid 原样存 customer_profiles.tags
        c2 = repo.get_contact_by_id(f"{account['id']}:e2")
        assert c2["status"] == "online"  # status=2 -> online

    def test_sessions_upsert_and_mapping(self, backend, account, monkeypatch):
        sess = [
            {"sessionid": "s1", "msgtype": 1, "unreadcnt": 3, "beginmsgseq": "b1"},
            {"sessionid": "s2", "msgtype": 0, "unreadcnt": 0, "beginmsgseq": ""},
        ]
        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_session_list",
                             lambda *a, **k: {"room_list": sess, "star_index": 0})
        res = ipad_sync.run_full_sync(account["id"])
        assert res["counts"]["sessions"] == 2
        repo = ChannelMgmtRepository(backend)
        s1 = repo.get_session_by_id(f"{account['id']}:s1")
        assert s1["msg_type"] == 1
        assert s1["session_type"] == "群聊"
        assert s1["remote_session_id"] == "s1"
        s2 = repo.get_session_by_id(f"{account['id']}:s2")
        assert s2["msg_type"] == 0
        assert s2["session_type"] == "好友"

    def test_groups_upsert_natural_key_idempotent(self, backend, account, monkeypatch):
        rooms = [
            {"room_id": "r1", "nickname": "群1", "total": 3},
            {"room_id": "r2", "nickname": "群2", "total": 5},
        ]
        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_chatroom_members",
                             lambda *a, **k: {"room_list": rooms, "star_index": 0})
        ipad_sync.run_full_sync(account["id"])
        ipad_sync.run_full_sync(account["id"])  # 重复同步幂等
        repo = ChannelMgmtRepository(backend)
        groups = repo.list_groups(account["id"])
        assert len(groups) == 2
        assert {g["roomId"] for g in groups} == {"r1", "r2"}
        # 自然键 id = {account_id}:{room_id}
        assert all(g["id"] == f"{account['id']}:{g['roomId']}" for g in groups)

    def test_success_status_written(self, backend, account, monkeypatch):
        _mock_all_lists_empty(monkeypatch)
        ipad_sync.run_full_sync(account["id"])
        repo = ChannelMgmtRepository(backend)
        acc = repo.get_account_by_id(account["id"])
        assert acc["syncStatus"] == "success"
        assert acc["lastSyncAt"] != ""

    def test_skip_when_account_missing(self, backend, monkeypatch):
        _mock_all_lists_empty(monkeypatch)
        res = ipad_sync.run_full_sync("nonexistent-account")
        assert res.get("skipped") is True
        assert res["error"]

    def test_skip_when_ipad_uuid_empty(self, backend, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        acc = repo.create_account_with_ipad(
            "wecom", "ipad", "team-initial", "空uuid账号", ipad_uuid="",
            ipad_user_info={}, host_status="pending")
        _mock_all_lists_empty(monkeypatch)
        res = ipad_sync.run_full_sync(acc["id"])
        assert res.get("skipped") is True

    def test_degraded_on_protocol_error(self, backend, account, monkeypatch):
        def _boom(*a, **k):
            raise ipad_client.IPadProtocolError("boom")

        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_inner_contacts", _boom)
        res = ipad_sync.run_full_sync(account["id"])
        assert res["degraded"] is True
        assert res["error"]
        repo = ChannelMgmtRepository(backend)
        acc = repo.get_account_by_id(account["id"])
        # auto 模式 -> 标记 degraded（不崩）
        assert acc["syncStatus"] in ("degraded", "error")


# --------------------------------------------------------------------------- #
# 2b. 单账号串行互斥
# --------------------------------------------------------------------------- #
class TestSyncMutex:
    def test_begin_end_sync_atomic(self):
        acc = "mutex-acc"
        assert ipad_sync._begin_sync(acc) is True
        assert ipad_sync._begin_sync(acc) is False  # 已在进行中
        ipad_sync._end_sync(acc)
        assert ipad_sync._begin_sync(acc) is True
        ipad_sync._end_sync(acc)

    def test_trigger_sync_returns_false_when_active(self, backend, account, monkeypatch):
        # 用 no-op 替换 run_full_sync，隔离互斥逻辑
        monkeypatch.setattr(ipad_sync, "run_full_sync",
                             lambda aid: {"counts": {}, "degraded": False, "error": None, "total": 0})
        assert ipad_sync._begin_sync(account["id"]) is True
        assert ipad_sync.trigger_sync(account["id"]) is False  # 正在同步 -> 跳过
        ipad_sync._end_sync(account["id"])
        assert ipad_sync.trigger_sync(account["id"]) is True

    def test_concurrent_triggers_no_cross_write(self, backend, account, monkeypatch):
        """两次并发触发：第二次应被互斥拦截（不交叉写）。"""
        state = {"running": False}

        def fake_run(aid):
            state["running"] = True
            time.sleep(0.05)
            state["running"] = False
            return {"counts": {}, "degraded": False, "error": None, "total": 0}

        monkeypatch.setattr(ipad_sync, "run_full_sync", fake_run)
        first = ipad_sync.trigger_sync(account["id"])
        # 第一次触发后立刻再次触发：应被互斥拦截
        second = ipad_sync.trigger_sync(account["id"])
        assert first is True
        assert second is False
        # 等待后台线程结束
        for _ in range(40):
            if not ipad_sync.get_sync_status(account["id"])["syncing"]:
                break
            time.sleep(0.05)


# --------------------------------------------------------------------------- #
# 3. 发消息目标解析单测（FakeRepo，隔离 DB）
# --------------------------------------------------------------------------- #
class _FakeRepo:
    def __init__(self, contacts=None, groups=None, sessions=None):
        self._contacts = {c["id"]: c for c in (contacts or [])}
        self._groups = {g["id"]: g for g in (groups or [])}
        self._group_room = {g["room_id"]: g for g in (groups or [])}
        self._sessions = {s["id"]: s for s in (sessions or [])}

    def get_contact_by_id(self, cid):
        return self._contacts.get(cid)

    def get_group_by_room_id(self, account_id, room_id):
        return self._group_room.get(room_id)

    def get_group_by_id(self, gid):
        return self._groups.get(gid)

    def get_session_by_id(self, sid):
        return self._sessions.get(sid)


class TestResolveTarget:
    def test_contact(self):
        repo = _FakeRepo(contacts=[{"id": "acc:c1", "user_id": "u1"}])
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "contact", "acc:c1")
        assert uid == "u1" and is_room is False

    def test_room_by_group_id(self):
        repo = _FakeRepo(groups=[{"id": "acc:r1", "room_id": "r1"}])
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "room", "acc:r1")
        assert uid == "r1" and is_room is True

    def test_room_by_room_id(self):
        repo = _FakeRepo(groups=[{"id": "acc:r1", "room_id": "r1"}])
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "room", "r1")
        assert uid == "r1" and is_room is True

    def test_session_room(self):
        repo = _FakeRepo(sessions=[{"id": "acc:s1", "msg_type": 1, "remote_session_id": "rs1"}])
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "session", "acc:s1")
        assert uid == "rs1" and is_room is True

    def test_session_contact(self):
        repo = _FakeRepo(
            contacts=[{"id": "acc:c1", "user_id": "u1"}],
            sessions=[{"id": "acc:s2", "msg_type": 0, "remote_session_id": "x", "contact_id": "acc:c1"}],
        )
        uid, is_room = ipad_sync._resolve_target(repo, "acc", "session", "acc:s2")
        assert uid == "u1" and is_room is False

    def test_session_app_raises(self):
        repo = _FakeRepo(sessions=[{"id": "acc:s3", "msg_type": 3, "remote_session_id": "", "contact_id": None}])
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync._resolve_target(repo, "acc", "session", "acc:s3")

    def test_unknown_target_raises(self):
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync._resolve_target(_FakeRepo(), "acc", "weird", "x")

    def test_send_text_message_internal(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_contact(_contact_row(account["id"], "u1"))
        monkeypatch.setattr(ipad_client, "send_text_msg",
                             lambda *a, **k: {"msg_id": "M9", "server_id": "S9",
                                             "content": "", "sendtime": "", "sender": "", "receiver": ""})
        res = ipad_sync.send_text_message(account["id"], "contact", f"{account['id']}:u1", "hi")
        assert res["msgId"] == "M9" and res["ok"] is True

    def test_send_text_message_missing_account(self, backend, monkeypatch):
        monkeypatch.setattr(ipad_client, "send_text_msg", lambda *a, **k: {})
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.send_text_message("nonexistent", "contact", "x", "hi")


# --------------------------------------------------------------------------- #
# 4. 路由集成测（FastAPI TestClient，mock iPad）
# --------------------------------------------------------------------------- #
class TestRouters:
    def test_sync_trigger_and_status_flow(self, backend, account, monkeypatch):
        """sync 触发返回 started；进行中状态可见；结束后 success。"""
        block = threading.Event()

        def fake_inner(uuid, str_seq="", limit=100):
            block.wait(timeout=10)
            return {"list": [], "strSeq": ""}

        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_inner_contacts", fake_inner)

        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post(f"/api/channels/{account['id']}/sync")
            assert r.status_code == 200  # 实际实现返回 200 + started
            assert r.json()["started"] is True
            time.sleep(0.1)  # 等待后台线程置 syncing 标志
            st = client.get(f"/api/channels/{account['id']}/sync-status")
            assert st.status_code == 200
            assert st.json()["syncing"] is True
            block.set()
            # 等待后台同步结束
            for _ in range(100):
                if not ipad_sync.get_sync_status(account["id"])["syncing"]:
                    break
                time.sleep(0.05)
            st2 = client.get(f"/api/channels/{account['id']}/sync-status")
            assert st2.json()["syncStatus"] == "success"

    def test_sync_status_404_for_missing_account(self, backend, monkeypatch):
        _mock_all_lists_empty(monkeypatch)
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get("/api/channels/nope/sync-status")
            assert r.status_code == 404

    def test_groups_endpoint(self, backend, account, monkeypatch):
        rooms = [
            {"room_id": "r1", "nickname": "群1", "total": 3},
            {"room_id": "r2", "nickname": "群2", "total": 5},
        ]
        _mock_all_lists_empty(monkeypatch)
        monkeypatch.setattr(ipad_client, "get_chatroom_members",
                             lambda *a, **k: {"room_list": rooms, "star_index": 0})
        ipad_sync.run_full_sync(account["id"])  # 先同步落库

        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get(f"/api/channels/{account['id']}/groups")
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 2
            assert {g["roomId"] for g in data} == {"r1", "r2"}

    def test_groups_404_for_missing_account(self, backend, monkeypatch):
        _mock_all_lists_empty(monkeypatch)
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get("/api/channels/nope/groups")
            assert r.status_code == 404

    def test_group_members_endpoint(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_group(_group_row(account["id"], "r1", nickname="群1"))
        monkeypatch.setattr(ipad_client, "get_room_user_list",
                             lambda uuid, room_id: {
                                 "room_id": room_id, "nickname": "群1", "total": 2,
                                 "notice_content": "公告",
                                 "member_list": [{"uin": "u1", "nickname": "成员1"},
                                                 {"uin": "u2", "nickname": "成员2"}],
                             })
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get(f"/api/channels/{account['id']}/group/r1/members")
            assert r.status_code == 200
            body = r.json()
            assert body["total"] == 2
            assert len(body["members"]) == 2
            assert body["noticeContent"] == "公告"

    def test_send_text_contact_success(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_contact(_contact_row(account["id"], "u1"))
        monkeypatch.setattr(ipad_client, "send_text_msg",
                             lambda *a, **k: {"msg_id": "M1", "server_id": "S1",
                                             "content": "", "sendtime": "", "sender": "", "receiver": ""})
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post(f"/api/channels/{account['id']}/send-text",
                            json={"targetType": "contact", "targetId": f"{account['id']}:u1",
                                  "content": "你好"})
            assert r.status_code == 200
            assert r.json()["msgId"] == "M1"

    def test_send_text_app_session_400(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s3", 3))
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post(f"/api/channels/{account['id']}/send-text",
                            json={"targetType": "session", "targetId": f"{account['id']}:s3",
                                  "content": "x"})
            assert r.status_code == 400

    def test_send_text_empty_target_400(self, backend, account, monkeypatch):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post(f"/api/channels/{account['id']}/send-text",
                            json={"targetType": "contact", "targetId": "", "content": "x"})
            assert r.status_code == 400

    def test_sync_empty_ipad_uuid_404(self, backend, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        acc = repo.create_account_with_ipad(
            "wecom", "ipad", "team-initial", "空uuid账号", ipad_uuid="",
            ipad_user_info={}, host_status="pending")
        _mock_all_lists_empty(monkeypatch)
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post(f"/api/channels/{acc['id']}/sync")
            assert r.status_code == 404

    def test_send_text_empty_ipad_uuid_400(self, backend, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        acc = repo.create_account_with_ipad(
            "wecom", "ipad", "team-initial", "空uuid账号", ipad_uuid="",
            ipad_user_info={}, host_status="pending")
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.post(f"/api/channels/{acc['id']}/send-text",
                            json={"targetType": "contact", "targetId": "x", "content": "y"})
            assert r.status_code == 400


# --------------------------------------------------------------------------- #
# 5. 真实服务回归（服务可达时运行）
# --------------------------------------------------------------------------- #
def _probe_reachable() -> bool:
    try:
        return bool(ipad_client.init("ipad").get("uuid"))
    except Exception:
        return False


REAL_REACHABLE = _probe_reachable()
_skip_real = pytest.mark.skipif(not REAL_REACHABLE, reason="真实 iPad 服务不可达，跳过真实回归")


class TestRealService:
    @_skip_real
    def test_real_get_inner_contacts(self):
        uuid = ipad_client.init("ipad")["uuid"]
        r = ipad_client.get_inner_contacts(uuid)
        assert isinstance(r, dict) and "list" in r and "strSeq" in r
        assert isinstance(r["list"], list)

    @_skip_real
    def test_real_get_external_contacts(self):
        uuid = ipad_client.init("ipad")["uuid"]
        r = ipad_client.get_external_contacts(uuid)
        assert isinstance(r, dict) and "list" in r and "seq" in r

    @_skip_real
    def test_real_get_session_list(self):
        uuid = ipad_client.init("ipad")["uuid"]
        r = ipad_client.get_session_list(uuid)
        assert isinstance(r, dict) and "room_list" in r and "star_index" in r

    @_skip_real
    def test_real_get_chatroom_members(self):
        uuid = ipad_client.init("ipad")["uuid"]
        r = ipad_client.get_chatroom_members(uuid)
        assert isinstance(r, dict) and "room_list" in r and "star_index" in r

    @_skip_real
    def test_real_get_room_user_list(self):
        uuid = ipad_client.init("ipad")["uuid"]
        r = ipad_client.get_room_user_list(uuid, "fake-room")
        assert isinstance(r, dict) and "member_list" in r

    @_skip_real
    def test_real_send_text_msg(self):
        # 仅做连通性探测：未登录账号不会真实投递，验证返回体结构即可。
        uuid = ipad_client.init("ipad")["uuid"]
        r = ipad_client.send_text_msg(uuid, "fake-userid", False, "qa-connectivity-probe")
        assert isinstance(r, dict) and "msg_id" in r
