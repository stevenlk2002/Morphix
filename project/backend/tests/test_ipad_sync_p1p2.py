"""「渠道会话 + 客户管理」iPad 协议同步 P1 + P2 增量 —— 测试套件。

覆盖范围（对照 docs/ipad-sync-p1p2-prd.md / ipad-sync-p1p2-design.md）：
1. 协议函数单测（mock `_post` / `_post_multipart`）：P1 标签/搜索/已读、P2 历史/富媒体/回调
   共 13 个新 Action 的字段归一化、envelope 兼容、camelCase、错误透传。
2. 仓储方法单测（ChannelMgmtRepository）：标签 upsert/映射/联系人与标签双写、
   消息幂等 upsert/分页/存在性、会话已读回写、未读自增、回调配置、搜索落库。
3. 同步服务单测（mock 协议函数）：sync_labels / search_contact / add_search_contact /
   mark_session_read / backfill_session_messages / send_media_message / handle_callback /
   register_callback 的业务分支与错误路径。
4. 路由集成测（FastAPI TestClient，mock iPad）：labels 同步/查询、联系人标签、
   搜索添加、会话已读、历史回填、富媒体发送、消息列表、/wxwork/callback 回调。

运行：
    cd project/backend && MORPHIX_DEV=1 .venv/bin/python -m pytest tests/test_ipad_sync_p1p2.py -q -p no:cacheprovider
"""
from __future__ import annotations

import json
import os

# 必须在 import app 之前设定协议模式（settings 在 import 时读取一次）。
os.environ.setdefault("IPAD_PROTOCOL_MODE", "auto")

import pytest
from dataclasses import replace

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
    be = SQLiteBackend(tmp_path / "morphix_test_p1p2.db")
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
        "unread_count": over.get("unread_count", 0),
        "read_status": over.get("read_status", "unread"),
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


def _make_contact_with_profile(repo: ChannelMgmtRepository, account_id: str, user_id: str, label_ids) -> str:
    """创建渠道联系人 + 客户档案（tags 镜像 labelid[]），返回 contact id。"""
    cid = f"{account_id}:{user_id}"
    repo.upsert_channel_contact(_contact_row(account_id, user_id))
    repo._db.execute(
        "INSERT OR REPLACE INTO customer_profiles("
        "id, contact_id, phone, email, company, position, region, age, birthday, "
        "remark, add_time, add_channel, signature, ai_summary_enabled, tags) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
        (cid, cid, "", "", "", "", "", None, "", "", "", "search", "", json.dumps(label_ids)),
    )
    return cid


def _patch_post(monkeypatch, payload):
    """将 `ipad_client._post` 替换为直接返回给定 payload。"""
    monkeypatch.setattr(ipad_client, "_post", lambda path, p=None: payload)


# --------------------------------------------------------------------------- #
# 1. 协议函数单测（mock `_post` / `_post_multipart`）
# --------------------------------------------------------------------------- #
class TestProtocolFunctionsP1P2:
    # ---- GetLabelListReq ----
    def test_get_label_list_bare(self, monkeypatch):
        _patch_post(monkeypatch, {"list": [{"id": "L1", "name": "高意向"}], "index": 2})
        r = ipad_client.get_label_list("uuid", 0, 1)
        assert len(r["list"]) == 1
        assert r["index"] == 2

    def test_get_label_list_wrapped_labelList(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"labelList": [{"id": "L1", "name": "高意向"}], "index": 3}})
        r = ipad_client.get_label_list("uuid", 0, 1)
        assert r["list"][0]["id"] == "L1"
        assert r["index"] == 3

    def test_get_label_list_empty(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {}})
        r = ipad_client.get_label_list("uuid", 0, 1)
        assert r["list"] == []
        assert r["index"] == 0

    # ---- UserAddLabelsReq ----
    def test_user_add_labels_returns_norm(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"ok": True}})
        r = ipad_client.user_add_labels("uuid", "u1", ["L1", "L2"])
        assert r.get("ok") is True

    # ---- SearchContact ----
    def test_search_contact_userList_and_list(self, monkeypatch):
        _patch_post(monkeypatch, {"list": [{"user_id": "u9", "name": "张三"}]})
        assert ipad_client.search_contact("uuid", "139")["list"][0]["user_id"] == "u9"
        _patch_post(monkeypatch, {"userList": [{"user_id": "u8", "name": "李四"}]})
        assert ipad_client.search_contact("uuid", "139")["userList"][0]["user_id"] == "u8"

    def test_search_contact_wrapped(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"userList": [{"user_id": "u7", "name": "王五"}]}})
        r = ipad_client.search_contact("uuid", "139")
        assert r["userList"][0]["user_id"] == "u7"

    # ---- AddSearch / AddWxUser / AgreeUser ----
    def test_add_search_returns_norm(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"ok": True}})
        r = ipad_client.add_search("uuid", "vid", "o", "139", "hi", "t")
        assert r.get("ok") is True

    def test_add_wx_user_returns_norm(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"ok": True}})
        assert ipad_client.add_wx_user("uuid", "vid", "hi").get("ok") is True

    def test_agree_user_returns_norm(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"ok": True}})
        assert ipad_client.agree_user("uuid", "corp", "vid").get("ok") is True

    # ---- GetGroupMsgList ----
    def test_get_group_msg_list_listdata_and_list(self, monkeypatch):
        _patch_post(monkeypatch, {"listdata": [{"id": "m1", "content": "a"}]})
        assert ipad_client.get_group_msg_list("uuid")["listdata"][0]["id"] == "m1"
        _patch_post(monkeypatch, {"list": [{"id": "m2"}]})
        assert ipad_client.get_group_msg_list("uuid")["list"][0]["id"] == "m2"

    # ---- SyncAllData ----
    def test_sync_all_data_returns_norm(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"ok": True}})
        r = ipad_client.sync_all_data("uuid", 100, 0)
        assert r.get("ok") is True

    # ---- MarkAsRead ----
    def test_mark_as_read_camelcase(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"serverId": "S1", "ok": True}})
        r = ipad_client.mark_as_read("uuid", "u1", False)
        assert r["server_id"] == "S1"
        assert r["ok"] is True

    def test_mark_as_read_ok_default_true(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {}})
        assert ipad_client.mark_as_read("uuid", "u1", True)["ok"] is True

    # ---- CdnUploadImg (multipart) ----
    def test_cdn_upload_img_normalization(self, monkeypatch):
        monkeypatch.setattr(
            ipad_client, "_post_multipart",
            lambda path, files, data=None: {"cdn_key": "K", "aes_key": "A", "md5": "M", "width": 10, "height": 20, "size": 100},
        )
        r = ipad_client.cdn_upload_img(b"bytes", "a.png", "uuid")
        assert r["cdn_key"] == "K" and r["width"] == 10 and r["size"] == 100

    def test_cdn_upload_img_camelcase(self, monkeypatch):
        monkeypatch.setattr(
            ipad_client, "_post_multipart",
            lambda path, files, data=None: {"cdnKey": "K2", "aesKey": "A2", "md5": "M", "width": 1, "height": 2, "size": 3},
        )
        r = ipad_client.cdn_upload_img(b"x", "a.png", "u")
        assert r["cdn_key"] == "K2" and r["aes_key"] == "A2"

    # ---- CdnUploadFile (multipart) ----
    def test_cdn_upload_file_normalization(self, monkeypatch):
        monkeypatch.setattr(
            ipad_client, "_post_multipart",
            lambda path, files, data=None: {"aes_key": "A", "fileid": "F", "md5": "M", "size": 50},
        )
        r = ipad_client.cdn_upload_file(b"bytes", "d.bin", "uuid")
        assert r["aes_key"] == "A" and r["fileid"] == "F" and r["size"] == 50

    # ---- SendCDNImgMsg ----
    def test_send_cdn_img_msg_camelcase(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"serverId": "S1", "msgId": "M1"}})
        r = ipad_client.send_cdn_img_msg("u", "r", True, "k", "a", "m", 1, 10, 20)
        assert r["server_id"] == "S1" and r["msg_id"] == "M1" and r["ok"] is True

    # ---- SendCDNFileMsg ----
    def test_send_cdn_file_msg_camelcase(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"serverId": "S2", "msgId": "M2"}})
        r = ipad_client.send_cdn_file_msg("u", "r", False, "F", "A", "m", "doc.pdf", 9)
        assert r["server_id"] == "S2" and r["ok"] is True

    # ---- SetCallbackUrl ----
    def test_set_callback_url_returns_norm(self, monkeypatch):
        _patch_post(monkeypatch, {"data": {"ok": True}})
        assert ipad_client.set_callback_url("uuid", "https://cb", "HTTP").get("ok") is True

    # ---- 错误透传 ----
    def test_get_label_list_propagates_protocol_error(self, monkeypatch):
        def _boom(path, p=None):
            raise ipad_client.IPadProtocolError("boom")

        monkeypatch.setattr(ipad_client, "_post", _boom)
        with pytest.raises(ipad_client.IPadProtocolError):
            ipad_client.get_label_list("uuid", 0, 1)


# --------------------------------------------------------------------------- #
# 2. 仓储方法单测
# --------------------------------------------------------------------------- #
class TestRepositoriesP1P2:
    def test_upsert_ipad_label_idempotent_and_group(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "L1", "name": "高意向"})
        repo.upsert_ipad_label(account["id"], {"id": "L1", "name": "高意向V2"})
        rows = repo._db.query("SELECT * FROM ipad_label_map WHERE account_id = ?", (account["id"],))
        assert len(rows) == 1
        assert rows[0]["label_name"] == "高意向V2"
        # 每账号一个 iPad 标签组 + 对应 customer_tags
        g = repo._db.query_one("SELECT * FROM customer_tag_groups WHERE id = ?", (f"tg-ipad-{account['id']}",))
        assert g is not None
        tag = repo._db.query_one("SELECT * FROM customer_tags WHERE id = ?", (f"itag-{account['id']}-L1",))
        assert tag is not None and tag["name"] == "高意向V2"

    def test_get_ipad_labels_sync_type_filter(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "E1", "name": "企业1", "sync_type": 1})
        repo.upsert_ipad_label(account["id"], {"id": "P1", "name": "个人1", "sync_type": 2})
        ent = repo.get_ipad_labels(account["id"], 1)
        per = repo.get_ipad_labels(account["id"], 2)
        assert [l["labelId"] for l in ent] == ["E1"]
        assert [l["labelId"] for l in per] == ["P1"]

    def test_map_labels_to_names_order_and_missing(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "L1", "name": "高意向"})
        repo.upsert_ipad_label(account["id"], {"id": "L2", "name": "已成交"})
        out = repo.map_ipad_labels_to_names(account["id"], ["L2", "L1", "LX"])
        assert [o["labelName"] for o in out] == ["已成交", "高意向", "LX"]

    def test_get_contact_ipad_labels(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "L1", "name": "高意向"})
        repo.upsert_ipad_label(account["id"], {"id": "L2", "name": "已成交"})
        cid = _make_contact_with_profile(repo, account["id"], "u1", ["L1", "L2"])
        names = repo.get_contact_ipad_labels(account["id"], cid)
        assert [n["labelName"] for n in names] == ["高意向", "已成交"]
        assert [n["labelId"] for n in names] == ["L1", "L2"]

    def test_get_contact_ipad_labels_empty_profile(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        assert repo.get_contact_ipad_labels(account["id"], "ghost") == []

    def test_set_contact_ipad_labels_double_write_preserves_manual(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "L1", "name": "高意向"})
        repo.upsert_ipad_label(account["id"], {"id": "L2", "name": "已成交"})
        cid = _make_contact_with_profile(repo, account["id"], "u1", ["L1"])
        # 一个非 iPad 标签关系，须被保留
        repo._db.execute(
            "INSERT OR IGNORE INTO customer_tag_relations(customer_id, tag_id) VALUES (?, ?)",
            (cid, "manual-tag"),
        )
        repo.set_contact_ipad_labels(account["id"], cid, ["L1", "L2"])
        prof = repo._db.query_one("SELECT tags FROM customer_profiles WHERE contact_id = ?", (cid,))
        assert json.loads(prof["tags"]) == ["L1", "L2"]
        rels = {
            r["tag_id"]
            for r in repo._db.query("SELECT tag_id FROM customer_tag_relations WHERE customer_id = ?", (cid,))
        }
        assert rels == {"manual-tag", f"itag-{account['id']}-L1", f"itag-{account['id']}-L2"}

    def test_set_account_callback(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.set_account_callback(account["id"], "https://cb", "HTTP")
        row = repo._db.query_one(
            "SELECT callback_url, callback_type FROM channel_accounts WHERE id = ?", (account["id"],)
        )
        assert row["callback_url"] == "https://cb" and row["callback_type"] == "HTTP"

    def test_add_contact_from_search_persists(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        cid = repo.add_contact_from_search(
            account["id"],
            {"user_id": "u9", "name": "张三", "ticket": "t", "openId": "o", "corp_id": "c", "state": "1", "headImg": "h"},
        )
        assert cid == f"{account['id']}:u9"
        c = repo.get_contact_by_id(cid)
        assert c["name"] == "张三" and c["type"] == "customer"
        extra = json.loads(c["extra_json"])
        assert extra["ticket"] == "t" and extra["openId"] == "o"
        # 无 user_id 返回 None
        assert repo.add_contact_from_search(account["id"], {"name": "x"}) is None

    def test_message_exists(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        assert repo.message_exists("c1", "m1") is False
        repo.upsert_channel_message({"id": "chmsg-c1:m1", "conversation_id": "c1", "content": "x", "server_id": "m1"})
        assert repo.message_exists("c1", "m1") is True
        assert repo.message_exists("c1", "") is False

    def test_upsert_channel_message_idempotent_and_meta(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        msg = {
            "id": "chmsg-c1:m1", "conversation_id": "c1", "sender_type": "user",
            "content": "hi", "server_id": "m1", "msg_type": 1, "sender_id": "u",
            "direction": "inbound", "content_type": "image", "media_url": "u",
            "media_meta": {"w": 1}, "is_read": 0, "channel_account_id": account["id"],
        }
        repo.upsert_channel_message(msg)
        repo.upsert_channel_message(msg)
        rows = repo._db.query("SELECT * FROM messages WHERE conversation_id = ?", ("c1",))
        assert len(rows) == 1
        ext = repo.list_session_messages_ext("c1")
        assert ext[0]["contentType"] == "image"
        assert ext[0]["mediaMeta"] == {"w": 1}

    def test_list_session_messages_ext_pagination(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        for i in range(5):
            repo.upsert_channel_message({
                "id": f"chmsg-c1:m{i}", "conversation_id": "c1", "content": f"m{i}",
                "server_id": f"m{i}", "created_at": f"2024-01-01T00:00:0{i}",
            })
        page = repo.list_session_messages_ext("c1", "", 3)
        assert [p["serverId"] for p in page] == ["m2", "m3", "m4"]  # 升序：次旧→最新
        older = repo.list_session_messages_ext("c1", "m2", 3)
        assert [p["serverId"] for p in older] == ["m0", "m1"]

    def test_mark_session_read_db(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, unread_count=3, read_status="unread"))
        repo.mark_session_read_db(f"{account['id']}:s1")
        row = repo._db.query_one(
            "SELECT unread_count, read_status FROM channel_sessions WHERE id = ?", (f"{account['id']}:s1",)
        )
        assert row["unread_count"] == 0 and row["read_status"] == "read"

    def test_increment_session_unread_by_remote(self, backend, account):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1", unread_count=0))
        repo.increment_session_unread("room1", account["id"])
        row = repo._db.query_one(
            "SELECT unread_count, read_status FROM channel_sessions WHERE id = ?", (f"{account['id']}:s1",)
        )
        assert row["unread_count"] == 1 and row["read_status"] == "unread"


# --------------------------------------------------------------------------- #
# 3. 同步服务单测（mock 协议函数）
# --------------------------------------------------------------------------- #
class TestServicesP1P2:
    # ---- sync_labels ----
    def test_sync_labels_upserts_both_types_and_idempotent(self, backend, account, monkeypatch):
        aid = account["id"]

        def fake(uuid, index=0, sync_type=1):
            return {
                "list": [
                    {"id": f"{aid}-{sync_type}-1", "name": f"T{sync_type}-1"},
                    {"id": f"{aid}-{sync_type}-2", "name": f"T{sync_type}-2"},
                ],
                "index": 0,
            }

        monkeypatch.setattr(ipad_client, "get_label_list", fake)
        res = ipad_sync.sync_labels(aid)
        assert res["total"] == 4 and res["synced"] == 4 and res["skipped"] is False
        repo = ChannelMgmtRepository(backend)
        assert len(repo.get_ipad_labels(aid)) == 4
        # 重复同步幂等，不产生脏数据
        assert ipad_sync.sync_labels(aid)["total"] == 4
        assert len(repo.get_ipad_labels(aid)) == 4

    def test_sync_labels_skip_missing_account(self, backend, monkeypatch):
        monkeypatch.setattr(ipad_client, "get_label_list", lambda *a, **k: {"list": [], "index": 0})
        res = ipad_sync.sync_labels("nope")
        assert res["skipped"] is True and res["total"] == 0

    def test_sync_labels_skip_empty_uuid(self, backend, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        acc = repo.create_account_with_ipad(
            "wecom", "ipad", "team", "空uuid", ipad_uuid="", ipad_user_info={}, host_status="pending"
        )
        monkeypatch.setattr(ipad_client, "get_label_list", lambda *a, **k: {"list": [], "index": 0})
        assert ipad_sync.sync_labels(acc["id"])["skipped"] is True

    # ---- search_contact ----
    def test_search_contact_normalization(self, backend, account, monkeypatch):
        monkeypatch.setattr(
            ipad_client, "search_contact",
            lambda uuid, phoneNumber: {"userList": [{"user_id": "u9", "name": "张三", "ticket": "t", "openId": "o", "corp_id": "c", "state": "1", "sex": 1}]},
        )
        res = ipad_sync.search_contact(account["id"], "139")
        assert res[0]["userId"] == "u9" and res[0]["name"] == "张三" and res[0]["ticket"] == "t"

    def test_search_contact_missing_account_raises(self, backend, monkeypatch):
        monkeypatch.setattr(ipad_client, "search_contact", lambda *a, **k: {"userList": []})
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.search_contact("nope", "139")

    def test_search_contact_protocol_error_wrapped(self, backend, account, monkeypatch):
        def _boom(*a, **k):
            raise ipad_client.IPadProtocolError("x")

        monkeypatch.setattr(ipad_client, "search_contact", _boom)
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.search_contact(account["id"], "139")

    # ---- add_search_contact ----
    def test_add_search_contact_persists(self, backend, account, monkeypatch):
        captured = {}

        def fake_add_search(uuid, vid, openId, phone, content, ticket):
            captured.update(vid=vid, openId=openId)
            return {"ok": True}

        monkeypatch.setattr(ipad_client, "add_search", fake_add_search)
        res = ipad_sync.add_search_contact(
            account["id"], {"vid": "u9", "openId": "o", "phone": "139", "content": "hi", "ticket": "t", "name": "张三"}
        )
        assert res["ok"] is True and res["contactId"] == f"{account['id']}:u9"
        c = ChannelMgmtRepository(backend).get_contact_by_id(f"{account['id']}:u9")
        assert c["name"] == "张三"

    def test_add_search_contact_direct_add_path(self, backend, account, monkeypatch):
        called = {"wx": False}

        def fake_add_wx_user(uuid, vid, content):
            called["wx"] = True
            return {"ok": True}

        monkeypatch.setattr(ipad_client, "add_wx_user", fake_add_wx_user)
        monkeypatch.setattr(ipad_client, "add_search", lambda *a, **k: {"ok": True})
        ipad_sync.add_search_contact(account["id"], {"vid": "u9", "useDirectAdd": True})
        assert called["wx"] is True

    # ---- mark_session_read ----
    def test_mark_session_read_group(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1", unread_count=2))
        captured = {}

        def fake_mark(uuid, send_userid, isRoom):
            captured.update(send_userid=send_userid, isRoom=isRoom)
            return {"server_id": "X", "ok": True}

        monkeypatch.setattr(ipad_client, "mark_as_read", fake_mark)
        res = ipad_sync.mark_session_read(account["id"], f"{account['id']}:s1")
        assert res["ok"] is True
        assert captured["isRoom"] is True and captured["send_userid"] == "room1"
        row = repo._db.query_one("SELECT unread_count FROM channel_sessions WHERE id = ?", (f"{account['id']}:s1",))
        assert row["unread_count"] == 0

    def test_mark_session_read_1to1(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_contact(_contact_row(account["id"], "u1"))
        repo.upsert_channel_session(_session_row(account["id"], "s2", 0, contact_id=f"{account['id']}:u1"))
        captured = {}
        monkeypatch.setattr(
            ipad_client, "mark_as_read",
            lambda uuid, su, ir: captured.update(send_userid=su, isRoom=ir) or {"server_id": "X"},
        )
        ipad_sync.mark_session_read(account["id"], f"{account['id']}:s2")
        assert captured["isRoom"] is False and captured["send_userid"] == "u1"

    def test_mark_session_read_missing_session_raises(self, backend, account, monkeypatch):
        monkeypatch.setattr(ipad_client, "mark_as_read", lambda *a, **k: {"server_id": "X"})
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.mark_session_read(account["id"], f"{account['id']}:missing")

    def test_mark_session_read_missing_contact_userid_raises(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        # 关联联系人存在但 user_id 为空 -> 应抛出 IPadSyncError
        row = _contact_row(account["id"], "u1")  # id = {account_id}:u1
        row["user_id"] = ""  # 关联联系人缺少 user_id
        repo.upsert_channel_contact(row)
        repo.upsert_channel_session(_session_row(account["id"], "s2", 0, contact_id=f"{account['id']}:u1"))
        monkeypatch.setattr(ipad_client, "mark_as_read", lambda *a, **k: {"server_id": "X"})
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.mark_session_read(account["id"], f"{account['id']}:s2")

    # ---- backfill_session_messages ----
    def test_backfill_group_messages_and_dedup(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1"))
        monkeypatch.setattr(
            ipad_client, "get_group_msg_list",
            lambda uuid: {"listdata": [{"id": "m1", "content": "hi", "seq": 1}, {"id": "m2", "content": "yo"}]},
        )
        res = ipad_sync.backfill_session_messages(account["id"], f"{account['id']}:s1")
        assert res["upserted"] == 2 and res["triggered"] is False
        res2 = ipad_sync.backfill_session_messages(account["id"], f"{account['id']}:s1")
        assert res2["upserted"] == 0
        assert len(repo.list_session_messages_ext(f"{account['id']}:s1")) == 2

    def test_backfill_1to1_triggers_sync(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s2", 0))
        captured = {}
        monkeypatch.setattr(
            ipad_client, "sync_all_data",
            lambda uuid, limit=100, seq=0: captured.update(seq=seq, limit=limit) or {"ok": True},
        )
        res = ipad_sync.backfill_session_messages(account["id"], f"{account['id']}:s2")
        assert res["triggered"] is True
        assert captured["limit"] == 1000

    def test_backfill_missing_session_raises(self, backend, account, monkeypatch):
        monkeypatch.setattr(ipad_client, "get_group_msg_list", lambda *a, **k: {"listdata": []})
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.backfill_session_messages(account["id"], f"{account['id']}:missing")

    # ---- send_media_message ----
    def test_send_media_image(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_contact(_contact_row(account["id"], "u1"))
        monkeypatch.setattr(
            ipad_client, "cdn_upload_img",
            lambda *a, **k: {"cdn_key": "K", "aes_key": "A", "md5": "M", "width": 10, "height": 20, "size": 100},
        )
        monkeypatch.setattr(ipad_client, "send_cdn_img_msg", lambda *a, **k: {"server_id": "S", "msg_id": "M1"})
        res = ipad_sync.send_media_message(account["id"], "contact", f"{account['id']}:u1", b"img", "a.png", "image")
        assert res["msgId"] == "M1" and res["serverId"] == "S" and res["contentType"] == "image" and res["mediaUrl"] == "K"
        msgs = repo.list_session_messages_ext(f"{account['id']}:u1")
        assert msgs[0]["contentType"] == "image" and msgs[0]["direction"] == "outbound"

    def test_send_media_file(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_contact(_contact_row(account["id"], "u1"))
        monkeypatch.setattr(
            ipad_client, "cdn_upload_file",
            lambda *a, **k: {"aes_key": "A", "fileid": "F", "md5": "M", "size": 50},
        )
        monkeypatch.setattr(ipad_client, "send_cdn_file_msg", lambda *a, **k: {"server_id": "S2", "msg_id": "M2"})
        res = ipad_sync.send_media_message(account["id"], "contact", f"{account['id']}:u1", b"f", "doc.pdf", "file")
        assert res["contentType"] == "file" and res["mediaUrl"] == "F"

    def test_send_media_app_session_rejected(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s3", 3))
        monkeypatch.setattr(ipad_client, "cdn_upload_img", lambda *a, **k: {})
        with pytest.raises(ipad_sync.IPadSyncError):
            ipad_sync.send_media_message(account["id"], "session", f"{account['id']}:s3", b"x", "a.png", "image")

    # ---- handle_callback ----
    def test_handle_callback_unknown_uuid(self, backend, monkeypatch):
        res = ipad_sync.handle_callback("unknown-uuid", {"content": "x"}, "")
        assert res["ok"] is False and res["upserted"] == 0

    def test_handle_callback_upserts_and_unread_and_idempotent(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1", unread_count=0))
        payload = {"json": {"msg": [{"session_id": "room1", "content": "hello", "server_id": "s1", "msg_type": 1}]}}
        # 直接调用服务层：handle_callback 期望已抽出的 json 内容（路由层已剥离外层 uuid/json/type）
        res = ipad_sync.handle_callback(account["ipadUuid"], payload["json"], "newmsg")
        assert res["ok"] is True and res["upserted"] == 1
        sess = repo._db.query_one("SELECT unread_count FROM channel_sessions WHERE id = ?", (f"{account['id']}:s1",))
        assert sess["unread_count"] == 1
        # 幂等：重复推送不重复落库
        assert ipad_sync.handle_callback(account["ipadUuid"], payload, "newmsg")["upserted"] == 0

    def test_handle_callback_multiple_shapes(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1"))
        payload = {
            "json": {
                "msg": [{"session_id": "room1", "content": "a", "server_id": "a1"}],
                "list": [{"session_id": "room1", "content": "b", "server_id": "b1"}],
            }
        }
        assert ipad_sync.handle_callback(account["ipadUuid"], payload["json"], "newmsg")["upserted"] == 2

    # ---- register_callback ----
    def test_register_callback_skipped_without_url(self, backend, account, monkeypatch):
        # Settings 为 frozen dataclass，需用 dataclasses.replace 替换模块级引用
        monkeypatch.setattr(
            ipad_sync, "settings",
            replace(ipad_sync.settings, ipad_callback_public_url="", ipad_callback_type="HTTP"),
        )
        res = ipad_sync.register_callback(account["id"])
        assert res["registered"] is False and res["ok"] is False

    def test_register_callback_registers(self, backend, account, monkeypatch):
        monkeypatch.setattr(
            ipad_sync, "settings",
            replace(
                ipad_sync.settings,
                ipad_callback_public_url="https://cb.example.com/wxwork/callback",
                ipad_callback_type="HTTP",
            ),
        )
        monkeypatch.setattr(ipad_client, "set_callback_url", lambda *a, **k: {"ok": True})
        res = ipad_sync.register_callback(account["id"])
        assert res["registered"] is True and res["url"] == "https://cb.example.com/wxwork/callback"
        row = ChannelMgmtRepository(backend)._db.query_one(
            "SELECT callback_url, callback_type FROM channel_accounts WHERE id = ?", (account["id"],)
        )
        assert row["callback_url"] == "https://cb.example.com/wxwork/callback"
        assert row["callback_type"] == "HTTP"


# --------------------------------------------------------------------------- #
# 4. 路由集成测（FastAPI TestClient，mock iPad）
# --------------------------------------------------------------------------- #
class TestRoutersP1P2:
    def _client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    # ---- 标签同步 / 查询 / 联系人标签 ----
    def test_labels_sync_endpoint(self, backend, account, monkeypatch):
        def fake(uuid, index=0, sync_type=1):
            return {"list": [{"id": f"{account['id']}-{sync_type}-1", "name": f"T{sync_type}"}], "index": 0}

        monkeypatch.setattr(ipad_client, "get_label_list", fake)
        with self._client() as client:
            r = client.post(f"/api/channels/{account['id']}/labels/sync")
            assert r.status_code == 200
            assert r.json()["synced"] == 2

    def test_labels_sync_404(self, backend, monkeypatch):
        monkeypatch.setattr(ipad_client, "get_label_list", lambda *a, **k: {"list": [], "index": 0})
        with self._client() as client:
            assert client.post("/api/channels/nope/labels/sync").status_code == 404

    def test_labels_list_endpoint(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "E1", "name": "企业", "sync_type": 1})
        with self._client() as client:
            r = client.get(f"/api/channels/{account['id']}/labels")
            assert r.status_code == 200
            assert r.json()[0]["labelName"] == "企业"

    def test_contact_labels_endpoint(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_ipad_label(account["id"], {"id": "L1", "name": "高意向"})
        cid = _make_contact_with_profile(repo, account["id"], "u1", ["L1"])
        with self._client() as client:
            r = client.get(f"/api/channels/{account['id']}/contacts/{cid}/labels")
            assert r.status_code == 200
            assert r.json()[0]["labelName"] == "高意向"

    # ---- 搜索添加 ----
    def test_search_endpoint(self, backend, account, monkeypatch):
        monkeypatch.setattr(
            ipad_client, "search_contact",
            lambda *a, **k: {"userList": [{"user_id": "u9", "name": "张三"}]},
        )
        with self._client() as client:
            r = client.post(f"/api/channels/{account['id']}/contacts/search", json={"keyword": "139"})
            assert r.status_code == 200
            assert r.json()[0]["userId"] == "u9"

    def test_search_endpoint_empty_keyword_400(self, backend, account, monkeypatch):
        monkeypatch.setattr(ipad_client, "search_contact", lambda *a, **k: {"userList": []})
        with self._client() as client:
            assert client.post(f"/api/channels/{account['id']}/contacts/search", json={"keyword": ""}).status_code == 400

    def test_search_endpoint_protocol_error_400(self, backend, account, monkeypatch):
        # search_contact 服务层将 IPadProtocolError 包装为 IPadSyncError -> 路由返回 400
        # （设计共享知识 #3 将 502 限定在「发送」类接口；搜索非发送，故为 400）
        def _boom(*a, **k):
            raise ipad_client.IPadProtocolError("x")

        monkeypatch.setattr(ipad_client, "search_contact", _boom)
        with self._client() as client:
            assert client.post(f"/api/channels/{account['id']}/contacts/search", json={"keyword": "139"}).status_code == 400

    def test_add_search_endpoint(self, backend, account, monkeypatch):
        monkeypatch.setattr(ipad_client, "add_search", lambda *a, **k: {"ok": True})
        with self._client() as client:
            r = client.post(
                f"/api/channels/{account['id']}/contacts/add-search",
                json={"vid": "u9", "openId": "o", "phone": "139", "content": "hi", "ticket": "t", "name": "张三"},
            )
            assert r.status_code == 200
            assert r.json()["ok"] is True

    def test_add_search_endpoint_404(self, backend, monkeypatch):
        with self._client() as client:
            assert client.post("/api/channels/nope/contacts/add-search", json={"vid": "u9"}).status_code == 404

    # ---- 已读 ----
    def test_mark_read_endpoint(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1"))
        monkeypatch.setattr(ipad_client, "mark_as_read", lambda *a, **k: {"server_id": "X"})
        with self._client() as client:
            r = client.post(f"/api/channels/{account['id']}/sessions/{account['id']}:s1/read")
            assert r.status_code == 200
            assert r.json()["ok"] is True

    def test_mark_read_endpoint_missing_session_400(self, backend, account, monkeypatch):
        monkeypatch.setattr(ipad_client, "mark_as_read", lambda *a, **k: {"server_id": "X"})
        with self._client() as client:
            assert client.post(f"/api/channels/{account['id']}/sessions/{account['id']}:missing/read").status_code == 400

    # ---- 历史回填 ----
    def test_backfill_endpoint_group(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1"))
        monkeypatch.setattr(
            ipad_client, "get_group_msg_list",
            lambda *a, **k: {"listdata": [{"id": "m1", "content": "hi"}]},
        )
        with self._client() as client:
            r = client.post(f"/api/channels/{account['id']}/sessions/{account['id']}:s1/messages/backfill")
            assert r.status_code == 200
            assert r.json()["upserted"] == 1

    def test_backfill_endpoint_missing_session_400(self, backend, account, monkeypatch):
        monkeypatch.setattr(ipad_client, "get_group_msg_list", lambda *a, **k: {"listdata": []})
        with self._client() as client:
            assert client.post(f"/api/channels/{account['id']}/sessions/{account['id']}:missing/messages/backfill").status_code == 400

    # ---- 富媒体发送 ----
    def test_send_media_endpoint(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_contact(_contact_row(account["id"], "u1"))
        monkeypatch.setattr(
            ipad_client, "cdn_upload_img",
            lambda *a, **k: {"cdn_key": "K", "aes_key": "A", "md5": "M", "width": 1, "height": 1, "size": 1},
        )
        monkeypatch.setattr(ipad_client, "send_cdn_img_msg", lambda *a, **k: {"server_id": "S", "msg_id": "M1"})
        with self._client() as client:
            r = client.post(
                f"/api/channels/{account['id']}/send-media",
                data={"targetType": "contact", "targetId": f"{account['id']}:u1", "mediaType": "image"},
                files={"file": ("a.png", b"img", "image/png")},
            )
            assert r.status_code == 200
            assert r.json()["contentType"] == "image"

    def test_send_media_endpoint_missing_account_404(self, backend, monkeypatch):
        with self._client() as client:
            r = client.post(
                "/api/channels/nope/send-media",
                data={"targetType": "contact", "targetId": "x", "mediaType": "image"},
                files={"file": ("a.png", b"x", "image/png")},
            )
            assert r.status_code == 404

    def test_send_media_endpoint_bad_media_type_400(self, backend, account, monkeypatch):
        with self._client() as client:
            r = client.post(
                f"/api/channels/{account['id']}/send-media",
                data={"targetType": "contact", "targetId": f"{account['id']}:u1", "mediaType": "video"},
                files={"file": ("a.png", b"x", "image/png")},
            )
            assert r.status_code == 400

    # ---- 消息列表 ----
    def test_messages_list_endpoint(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_message({"id": "chmsg-c1:m1", "conversation_id": "c1", "content": "hi", "server_id": "m1"})
        with self._client() as client:
            r = client.get(f"/api/channels/{account['id']}/messages", params={"conversationId": "c1"})
            assert r.status_code == 200
            assert r.json()[0]["content"] == "hi"

    def test_messages_list_missing_conversation_400(self, backend, account, monkeypatch):
        with self._client() as client:
            assert client.get(f"/api/channels/{account['id']}/messages").status_code == 400

    def test_messages_list_missing_account_404(self, backend, monkeypatch):
        with self._client() as client:
            assert client.get("/api/channels/nope/messages", params={"conversationId": "c1"}).status_code == 404

    # ---- 实时回调 ----
    def test_callback_endpoint_upserts(self, backend, account, monkeypatch):
        repo = ChannelMgmtRepository(backend)
        repo.upsert_channel_session(_session_row(account["id"], "s1", 1, remote_session_id="room1", unread_count=0))
        with self._client() as client:
            r = client.post(
                "/wxwork/callback",
                json={"uuid": account["ipadUuid"], "json": {"msg": [{"session_id": "room1", "content": "hello", "server_id": "s1"}]}, "type": "newmsg"},
            )
            assert r.status_code == 200
            assert r.json()["upserted"] == 1

    def test_callback_endpoint_invalid_payload_200(self, backend, account, monkeypatch):
        with self._client() as client:
            r = client.post("/wxwork/callback", json="not-an-object")
            assert r.status_code == 200
            assert r.json()["ok"] is False

    def test_callback_endpoint_unknown_uuid(self, backend, monkeypatch):
        with self._client() as client:
            r = client.post("/wxwork/callback", json={"uuid": "nope", "json": {"content": "x"}})
            assert r.status_code == 200
            assert r.json()["upserted"] == 0
